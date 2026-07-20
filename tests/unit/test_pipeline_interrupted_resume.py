#!/usr/bin/env python3
"""
Pipeline interrupted-resume 回归测试（方案 A）。

背景：服务重启后 ThreadPoolExecutor 中的任务全部丢失，DB 中标记为 interrupted。
原实现 resume 只接受 paused/done，74% 的任务无法恢复。
方案 A：resume 接受 interrupted + 从 DB 重建内存 task。

覆盖：
  - rebuild_task_from_db：DB 有记录 + requirements 存在 → 成功重建
  - rebuild_task_from_db：requirements 文件丢失 → 返回 None
  - resume interrupted：成功重建 + 启动执行
  - resume cancelled：即使 requirements 存在也被 400 拒绝
  - resume 不存在 ID：404
  - 重建后 completed_steps 从 DB 恢复（断点续跑依据）
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("LLM_API_KEY", "sk-test-dummy")


@pytest.fixture
def tmp_pipeline_record(tmp_path):
    """在 DB 中创建一条 interrupted Pipeline 记录 + requirements 文件。

    返回 (pipeline_id, requirements_path)。
    使用临时 DATABASE_PATH 隔离，不污染正式 DB。
    """
    db_path = tmp_path / "test_app.db"
    os.environ["DATABASE_PATH"] = str(db_path)

    # 重新导入让 session 模块拾取新的 DATABASE_PATH
    import importlib
    import db.session as session_mod
    importlib.reload(session_mod)
    import db.models as models_mod
    importlib.reload(models_mod)

    from db.session import init_db, session_scope
    init_db()

    req_file = tmp_path / "requirements.md"
    req_file.write_text("# 测试需求\n## 功能 A\n用户可以登录", encoding="utf-8")

    output_dir = tmp_path / "output" / "test-pipeline"
    output_dir.mkdir(parents=True, exist_ok=True)

    pipeline_id = "testresume001"
    from db.models import Pipeline
    with session_scope() as s:
        s.query(Pipeline).filter(Pipeline.id == pipeline_id).delete()
        p = Pipeline(
            id=pipeline_id,
            requirements_path=str(req_file),
            mode="semi",
            dimensions="basic",
            formats="excel",
            status="interrupted",
            output_dir=str(output_dir),
        )
        s.add(p)

    yield pipeline_id, str(req_file)

    # 清理
    os.environ.pop("DATABASE_PATH", None)
    importlib.reload(session_mod)
    importlib.reload(models_mod)


class TestRebuildTaskFromDB:
    """TaskManager.rebuild_task_from_db 单元测试。"""

    def test_rebuild_success_when_requirements_exist(self, tmp_pipeline_record):
        """DB 有记录 + requirements 存在 → 成功重建。"""
        pipeline_id, _ = tmp_pipeline_record
        from web.services.task_manager import TaskManager

        tm = TaskManager(output_base="./output")
        task = tm.rebuild_task_from_db(pipeline_id)

        assert task is not None
        assert task.pipeline_id == pipeline_id
        assert task.status == "interrupted"  # 保留 DB 原始状态
        assert task.mode == "semi"
        assert task in tm._tasks.values()  # 已注入内存

    def test_rebuild_returns_none_when_requirements_missing(self, tmp_pipeline_record):
        """requirements 文件被清理 → 返回 None。"""
        pipeline_id, req_path = tmp_pipeline_record
        Path(req_path).unlink()  # 删除需求文件

        from web.services.task_manager import TaskManager
        tm = TaskManager(output_base="./output")
        assert tm.rebuild_task_from_db(pipeline_id) is None

    def test_rebuild_returns_none_for_nonexistent_id(self, tmp_pipeline_record):
        """不存在的 pipeline_id → 返回 None。"""
        from web.services.task_manager import TaskManager
        tm = TaskManager(output_base="./output")
        assert tm.rebuild_task_from_db("nonexistent_xyz") is None

    def test_rebuild_restores_completed_steps(self, tmp_pipeline_record):
        """重建时从 DB 恢复已完成的步骤（断点续跑依据）。"""
        pipeline_id, _ = tmp_pipeline_record
        from db.session import session_scope
        from db.models import PipelineStep
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        # 写入两条已完成的 step 记录
        with session_scope() as s:
            for sid, name in [(1, "需求分析"), (2, "知识库检索")]:
                s.execute(
                    sqlite_insert(PipelineStep).values(
                        pipeline_id=pipeline_id, step_id=sid, name=name,
                        status="completed", detail="{}",
                    ).on_conflict_do_nothing()
                )

        from web.services.task_manager import TaskManager
        tm = TaskManager(output_base="./output")
        task = tm.rebuild_task_from_db(pipeline_id)

        assert task is not None
        assert sorted(task.completed_steps) == [1, 2]


class TestResumeEndpointStates:
    """resume 端点的状态校验（mock 执行层，只测状态流转）。"""

    def test_resume_interrupted_triggers_rebuild(self, tmp_pipeline_record):
        """interrupted 任务不在内存 → 触发 rebuild_task_from_db。"""
        pipeline_id, _ = tmp_pipeline_record
        from fastapi.testclient import TestClient
        from web.app import app

        client = TestClient(app)
        tm = app.dependency_overrides  # noqa — 仅用于文档说明

        # mock rebuild 返回一个 task，mock resume_background 不真跑
        mock_task = MagicMock()
        mock_task.status = "interrupted"
        mock_task.output_dir = "/tmp/output"

        with patch("web.services.task_manager.TaskManager.get_task", return_value=None), \
             patch("web.services.task_manager.TaskManager.rebuild_task_from_db", return_value=mock_task):
            resp = client.post(f"/api/v1/pipeline/{pipeline_id}/resume")

        # rebuild 成功 + 状态 interrupted 在允许列表 → 200
        assert resp.status_code == 200
        mock_task.resume_background.assert_called_once()

    def test_resume_cancelled_rejected_400(self, tmp_pipeline_record):
        """cancelled 状态即使 requirements 存在也被 400 拒绝。"""
        pipeline_id, _ = tmp_pipeline_record
        from fastapi.testclient import TestClient
        from web.app import app

        # 先把 DB 记录改成 cancelled
        from db.session import session_scope
        from db.models import Pipeline
        with session_scope() as s:
            s.query(Pipeline).filter(Pipeline.id == pipeline_id).update({"status": "cancelled"})

        client = TestClient(app)
        resp = client.post(f"/api/v1/pipeline/{pipeline_id}/resume")
        assert resp.status_code == 400
        assert "不允许" in resp.json()["detail"]

    def test_resume_nonexistent_returns_404(self, tmp_pipeline_record):
        """不存在的 pipeline_id → 404。"""
        from fastapi.testclient import TestClient
        from web.app import app

        client = TestClient(app)
        resp = client.post("/api/v1/pipeline/nonexistent_xyz/resume")
        assert resp.status_code == 404
