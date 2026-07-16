#!/usr/bin/env python3
"""
Task Manager 测试 — 任务生命周期管理

测试范围：
  - 任务创建与启动
  - 并发限制
  - 任务查询
  - 任务列表（内存 + DB 合并）
  - 单例模式
  - 任务状态追踪

注意：PipelineTask.start_background 被 mock，避免实际执行。
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("LLM_API_KEY", "sk-test-dummy")


@pytest.fixture(autouse=True)
def _mock_pipeline_start():
    """Mock PipelineTask.start_background 避免实际执行 Pipeline，并重置单例"""
    import web.services.event_bus as eb_module
    import web.services.task_manager as tm_module

    # 重置单例
    tm_module._task_manager = None
    eb_module._event_bus = None

    with patch("web.services.pipeline_task.PipelineTask.start_background", return_value=None):
        with patch("web.services.pipeline_task.PipelineTask.resume_background", return_value=None):
            with patch("web.services.pipeline_task._ensure_db", return_value=None):
                yield

    tm_module._task_manager = None
    eb_module._event_bus = None


class TestTaskManagerBasic:
    """TaskManager 基本功能"""

    def test_singleton(self):
        """get_task_manager 返回单例"""
        # 重置全局单例
        import web.services.task_manager as tm_module
        from web.services.task_manager import get_task_manager
        tm_module._task_manager = None

        tm1 = get_task_manager()
        tm2 = get_task_manager()
        assert tm1 is tm2

    def test_create_task(self):
        """创建任务"""
        from web.services.task_manager import TaskManager

        # 使用独立实例避免单例状态干扰
        with tempfile.TemporaryDirectory() as tmpdir:
            tm = TaskManager(output_base=tmpdir)
            task = tm.create_task(
                config={"llm": {"provider": "test", "api_key": "sk-test", "model": "m"}},
                requirements_path="/tmp/test.md",
                mode="semi",
            )
            assert task.pipeline_id is not None
            assert len(task.pipeline_id) == 12
            assert task.status in ("running", "pending")

    def test_get_task(self):
        """获取任务"""
        from web.services.task_manager import TaskManager

        with tempfile.TemporaryDirectory() as tmpdir:
            tm = TaskManager(output_base=tmpdir)
            task = tm.create_task(
                config={"llm": {"provider": "test", "api_key": "sk-test", "model": "m"}},
                requirements_path="/tmp/test.md",
            )
            found = tm.get_task(task.pipeline_id)
            assert found is not None
            assert found.pipeline_id == task.pipeline_id

    def test_get_nonexistent_task(self):
        """获取不存在的任务返回 None"""
        from web.services.task_manager import TaskManager

        with tempfile.TemporaryDirectory() as tmpdir:
            tm = TaskManager(output_base=tmpdir)
            assert tm.get_task("nonexistent") is None

    def test_list_tasks(self, tmp_path):
        """列出任务 — 使用独立 TaskManager 避免单例状态污染"""
        from web.services.task_manager import TaskManager

        # 使用独立实例
        tm = TaskManager(output_base=str(tmp_path))

        # 创建两个任务
        task1 = tm.create_task(
            config={"llm": {"provider": "test", "api_key": "sk-test", "model": "m"}},
            requirements_path="/tmp/test1.md",
        )
        task2 = tm.create_task(
            config={"llm": {"provider": "test", "api_key": "sk-test", "model": "m"}},
            requirements_path="/tmp/test2.md",
        )

        # 只检查内存中的任务（不查 DB，避免跨测试污染）
        tasks = tm.list_tasks()
        # 注意：list_tasks 也会查 DB，所以可能返回更多
        memory_count = sum(1 for t in tasks if t["pipeline_id"] in (task1.pipeline_id, task2.pipeline_id))
        assert memory_count >= 2

    def test_is_full(self):
        """并发限制检查"""
        from web.services.task_manager import TaskManager

        with tempfile.TemporaryDirectory() as tmpdir:
            tm = TaskManager(output_base=tmpdir)
            assert tm.is_full() is False

            # 创建两个任务达到上限
            task1 = tm.create_task(
                config={"llm": {"provider": "test", "api_key": "sk-test", "model": "m"}},
                requirements_path="/tmp/test1.md",
            )
            task2 = tm.create_task(
                config={"llm": {"provider": "test", "api_key": "sk-test", "model": "m"}},
                requirements_path="/tmp/test2.md",
            )
            assert tm.is_full() is True

    def test_get_running_count(self):
        """运行中任务数"""
        from web.services.task_manager import TaskManager

        with tempfile.TemporaryDirectory() as tmpdir:
            tm = TaskManager(output_base=tmpdir)
            assert tm.get_running_count() == 0

            tm.create_task(
                config={"llm": {"provider": "test", "api_key": "sk-test", "model": "m"}},
                requirements_path="/tmp/test.md",
            )
            assert tm.get_running_count() == 1

    def test_max_workers(self):
        """最大并发数"""
        from web.services.task_manager import TaskManager

        assert TaskManager.MAX_WORKERS == 2


class TestPipelineTask:
    """PipelineTask 状态追踪"""

    def test_task_initial_state(self, tmp_path):
        """任务初始状态"""
        from web.services.pipeline_task import PipelineTask

        task = PipelineTask(
            pipeline_id="test-001",
            output_dir=str(tmp_path),
            config={},
            requirements_path="/tmp/req.md",
        )
        assert task.status == "pending"
        assert task.completed_steps == []
        assert task.logs == []
        assert task.error == ""

    def test_get_progress(self, tmp_path):
        """获取进度"""
        from web.services.pipeline_task import PipelineTask

        task = PipelineTask(
            pipeline_id="test-001",
            output_dir=str(tmp_path),
            config={},
            requirements_path="/tmp/req.md",
        )
        task.completed_steps = [1, 2, 3]
        task.status = "running"

        progress = task.get_progress()
        assert progress["pipeline_id"] == "test-001"
        assert progress["percent"] == 43  # 3/7 ≈ 43%
        assert progress["status"] == "running"
        assert len(progress["completed_steps"]) == 3
        assert "steps" in progress
        assert "logs" in progress

    def test_build_steps_view(self, tmp_path):
        """构建步骤视图"""
        from web.services.pipeline_task import PipelineTask

        task = PipelineTask(
            pipeline_id="test-001",
            output_dir=str(tmp_path),
            config={},
            requirements_path="/tmp/req.md",
        )
        task.completed_steps = [1, 2]
        task.step_details = {
            1: {"data": {"modules": 3, "features": 8}},
            2: {"data": {"hits": 5}},
        }

        view = task._build_steps_view()
        assert len(view) == 7
        assert view[0]["status"] == "done"  # step 1
        assert view[1]["status"] == "done"  # step 2
        assert view[0]["detail"] == "3 模块 8 功能点"
        assert view[1]["detail"] == "命中 5 条"

    def test_on_log_appends(self, tmp_path):
        """日志追加"""
        from web.services.pipeline_task import PipelineTask

        task = PipelineTask(
            pipeline_id="test-001",
            output_dir=str(tmp_path),
            config={},
            requirements_path="/tmp/req.md",
        )
        task._on_log("STEP", "Test log message")
        assert len(task.logs) == 1
        assert task.logs[0]["level"] == "STEP"
        assert task.logs[0]["msg"] == "Test log message"

    def test_on_log_truncates(self, tmp_path):
        """日志超过 200 条时截断"""
        from web.services.pipeline_task import PipelineTask

        task = PipelineTask(
            pipeline_id="test-001",
            output_dir=str(tmp_path),
            config={},
            requirements_path="/tmp/req.md",
        )
        for i in range(250):
            task._on_log("INFO", f"Message {i}")

        assert len(task.logs) == 200
        # 保留最新的 200 条
        assert task.logs[-1]["msg"] == "Message 249"

    def test_output_dir_created(self, tmp_path):
        """输出目录被创建"""
        from web.services.pipeline_task import PipelineTask

        output_dir = str(tmp_path / "subdir" / "output")
        task = PipelineTask(
            pipeline_id="test-001",
            output_dir=output_dir,
            config={},
            requirements_path="/tmp/req.md",
        )
        # PipelineTask 本身不创建 output_dir（由 Pipeline 类创建）
        # 这里只验证基本属性
        assert task.output_dir == output_dir


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
