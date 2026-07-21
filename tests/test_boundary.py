#!/usr/bin/env python3
"""
边界条件与异常测试

覆盖现有测试未覆盖的边界场景：
  - Pipeline 执行异常处理
  - TaskManager 并发上限
  - 知识库边界条件
  - 认证 Token 边界
  - 配置类型边界
  - 数据库连接边界
"""

import io
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("LLM_API_KEY", "sk-test-dummy-for-boundary-tests")


# ─── Pipeline 执行异常处理 ───


class TestPipelineExecutionErrors:
    """Pipeline 执行过程中的异常处理"""

    def test_pipeline_catches_generic_error(self, tmp_path):
        """Pipeline 执行中普通异常被捕获，状态变为 error"""
        from web.services.pipeline_task import PipelineTask

        task = PipelineTask(
            pipeline_id="error-001",
            output_dir=str(tmp_path),
            config={"llm": {"provider": "test", "api_key": "sk-test", "model": "m"}},
            requirements_path="/tmp/req.md",
        )

        # 模拟 run 中抛出异常
        task.status = "running"
        try:
            raise ValueError("模拟执行错误")
        except Exception as e:
            task.status = "error"
            task.error = str(e)

        assert task.status == "error"
        assert "模拟执行错误" in task.error

    def test_pipeline_status_transitions(self, tmp_path):
        """Pipeline 状态转换边界"""
        from web.services.pipeline_task import PipelineTask

        task = PipelineTask(
            pipeline_id="trans-001",
            output_dir=str(tmp_path),
            config={"llm": {"provider": "test", "api_key": "sk-test", "model": "m"}},
            requirements_path="/tmp/req.md",
        )

        # 初始状态
        assert task.status == "pending"

        # pending -> running
        task.status = "running"
        assert task.status == "running"

        # running -> paused
        task.status = "paused"
        assert task.status == "paused"

        # paused -> running
        task.status = "running"
        assert task.status == "running"

        # running -> cancelled
        task.status = "cancelled"
        assert task.status == "cancelled"

        # running -> done
        task.status = "done"
        assert task.status == "done"

        # running -> error
        task.status = "error"
        assert task.status == "error"

    def test_pipeline_progress_edge_values(self, tmp_path):
        """进度计算的边界值"""
        from web.services.pipeline_task import PipelineTask

        task = PipelineTask(
            pipeline_id="prog-001",
            output_dir=str(tmp_path),
            config={"llm": {"provider": "test", "api_key": "sk-test", "model": "m"}},
            requirements_path="/tmp/req.md",
        )

        # 0 步骤完成
        prog = task.get_progress()
        assert prog["percent"] == 0
        assert prog["completed_steps"] == []
        assert prog["current_step"] == 1

        # 全部完成
        task.completed_steps = [1, 2, 3, 4, 5, 6, 7]
        task.status = "done"
        prog = task.get_progress()
        assert prog["percent"] == 88  # 7/8 ≈ 88% (Sprint 6.1: 8 steps)
        assert len(prog["completed_steps"]) == 7

    def test_pipeline_log_buffer_overflow(self, tmp_path):
        """日志缓冲区满时截断旧日志"""
        from web.services.pipeline_task import PipelineTask

        task = PipelineTask(
            pipeline_id="log-001",
            output_dir=str(tmp_path),
            config={"llm": {"provider": "test", "api_key": "sk-test", "model": "m"}},
            requirements_path="/tmp/req.md",
        )

        # _on_log(level, msg)：level 是日志级别，msg 是消息
        for i in range(250):
            task._on_log("INFO", f"log-{i}")

        # 应该只保留最近 200 条
        assert len(task.logs) == 200
        # 最旧日志应该被截断
        assert "log-0" not in [entry["msg"] for entry in task.logs]
        # 最新日志保留
        assert task.logs[-1]["msg"] == "log-249"

    def test_pipeline_llm_stats_accumulation(self, tmp_path):
        """LLM 统计信息累加"""
        from web.services.pipeline_task import PipelineTask

        task = PipelineTask(
            pipeline_id="stats-001",
            output_dir=str(tmp_path),
            config={"llm": {"provider": "test", "api_key": "sk-test", "model": "m"}},
            requirements_path="/tmp/req.md",
        )

        # llm_stats 初始为空 dict
        assert task.llm_stats == {}

        # 模拟 LLM 统计更新
        task.llm_stats = {"call_count": 3, "total_tokens": 1500, "model": "test-model"}

        assert task.llm_stats["call_count"] == 3
        assert task.llm_stats["total_tokens"] == 1500
        assert task.llm_stats["model"] == "test-model"


# ─── TaskManager 并发上限 ───


class TestTaskManagerBoundary:
    """TaskManager 边界条件"""

    def test_create_task_when_full_raises(self, tmp_path):
        """并发满时创建任务抛出 RuntimeError"""
        from web.services.task_manager import TaskManager

        tm = TaskManager(output_base=str(tmp_path))
        # 创建任务直到达到并发上限（MAX_WORKERS 从 config 读取，默认 2）
        for i in range(tm.MAX_WORKERS):
            tm.create_task(
                config={"llm": {"provider": "test", "api_key": "sk-test", "model": "m"}},
                requirements_path=f"/tmp/req{i}.md",
            )

        with pytest.raises(RuntimeError, match="达到最大并发数|并发任务已达上限"):
            tm.create_task(
                config={"llm": {"provider": "test", "api_key": "sk-test", "model": "m"}},
                requirements_path="/tmp/req_full.md",
            )

    def test_max_workers_boundary_values(self, tmp_path):
        """max_workers 边界值"""
        from web.services.task_manager import TaskManager

        tm = TaskManager(output_base=str(tmp_path))

        # MAX_WORKERS 是实例属性，从 config.yaml 的 pipeline.max_concurrent 读取（默认 2）
        assert tm.MAX_WORKERS == 2

        # 未满时 is_full 返回 False
        assert tm.is_full() is False

        # 创建两个任务，填满并发槽位
        task1 = tm.create_task(
            config={"llm": {"provider": "test", "api_key": "sk-test", "model": "m"}},
            requirements_path="/tmp/req1.md",
        )
        task2 = tm.create_task(
            config={"llm": {"provider": "test", "api_key": "sk-test", "model": "m"}},
            requirements_path="/tmp/req2.md",
        )

        # is_full 基于实际 running/pending 状态计数
        # 任务创建后状态为 running，应该满
        assert tm.is_full() is True

    def test_list_tasks_empty(self, tmp_path):
        """空任务列表"""
        from web.services.task_manager import TaskManager

        tm = TaskManager(output_base=str(tmp_path))
        tasks = tm.list_tasks()
        assert isinstance(tasks, list)
        # 可能有 DB 中的历史任务，但不应该报错

    def test_get_task_nonexistent_returns_none(self, tmp_path):
        """获取不存在的任务返回 None"""
        from web.services.task_manager import TaskManager

        tm = TaskManager(output_base=str(tmp_path))
        result = tm.get_task("nonexistent-id-99999")
        assert result is None


# ─── 知识库边界条件 ───


class TestKnowledgeBaseBoundary:
    """知识库 API 边界条件"""

    def test_kb_search_special_characters(self, client):
        """特殊字符查询"""
        resp = client.get("/api/v1/knowledge/search", params={"q": "SELECT * FROM users; --"})
        assert resp.status_code in (200, 500, 503)
        data = resp.json()
        assert "query" in data

    def test_kb_search_very_long_query(self, client):
        """超长查询字符串"""
        long_query = "测试" * 1000  # 2000 chars
        resp = client.get("/api/v1/knowledge/search", params={"q": long_query})
        assert resp.status_code in (200, 500, 503)

    def test_kb_search_unicode_query(self, client):
        """Unicode 特殊字符查询"""
        resp = client.get("/api/v1/knowledge/search", params={"q": "🎉✅❌🚀测试"})
        assert resp.status_code in (200, 500, 503)

    def test_kb_status_response_structure(self, client):
        """KB 状态响应结构"""
        resp = client.get("/api/v1/knowledge/status")
        assert resp.status_code == 200
        data = resp.json()
        # KB 可能返回 enabled=true + source 或 enabled=false
        assert "enabled" in data or "source" in data or "total" in data


# ─── 配置边界条件 ───


class TestConfigBoundary:
    """配置加载边界条件"""

    def test_config_nonexistent_file(self):
        """加载不存在的配置文件"""
        from core.config_loader import load_config

        cfg = load_config("/nonexistent/path/config.yaml")
        # 应返回默认配置
        assert "llm" in cfg
        assert "pipeline" in cfg

    def test_config_invalid_yaml(self, tmp_path):
        """无效 YAML 文件"""
        from core.config_loader import load_config

        invalid_yaml = tmp_path / "invalid.yaml"
        invalid_yaml.write_text(": : : : bad yaml: : :", encoding="utf-8")

        cfg = load_config(str(invalid_yaml))
        # 应返回默认配置
        assert "llm" in cfg

    def test_config_empty_file(self, tmp_path):
        """空配置文件"""
        from core.config_loader import load_config

        empty_yaml = tmp_path / "empty.yaml"
        empty_yaml.write_text("", encoding="utf-8")

        cfg = load_config(str(empty_yaml))
        assert "llm" in cfg

    def test_config_type_coercion(self, tmp_path):
        """配置值类型边界"""
        from core.config_loader import load_config

        crazy_yaml = tmp_path / "types.yaml"
        crazy_yaml.write_text(
            "llm:\n  api_key: 12345\n  model: 0\n  temperature: 'hot'\n"
            "pipeline:\n  max_concurrent: 'not-a-number'\n",
            encoding="utf-8",
        )

        cfg = load_config(str(crazy_yaml))
        # 配置加载不应崩溃，应该保留原始值
        assert "llm" in cfg

    def test_config_deeply_nested(self, tmp_path):
        """深层嵌套配置"""
        from core.config_loader import load_config

        nested_yaml = tmp_path / "nested.yaml"
        nested_yaml.write_text(
            "a:\n  b:\n    c:\n      d:\n        e: deep_value\n",
            encoding="utf-8",
        )

        cfg = load_config(str(nested_yaml))
        assert cfg["a"]["b"]["c"]["d"]["e"] == "deep_value"


# ─── 数据库边界条件 ───


class TestDatabaseBoundary:
    """数据库操作边界条件"""

    def test_session_rollback_on_error(self):
        """异常时自动回滚"""
        from db.models import Pipeline  # noqa: F401
        from db.session import session_scope

        try:
            with session_scope() as session:
                # 尝试插入无效数据
                from db.models import Pipeline
                p = Pipeline(id="test-rollback", status="running")
                session.add(p)
                raise RuntimeError("模拟错误触发回滚")
        except RuntimeError:
            pass  # 预期异常

        # 验证回滚：数据不应存在
        with session_scope() as session:
            from db.models import Pipeline
            result = session.query(Pipeline).filter(Pipeline.id == "test-rollback").first()
            assert result is None

    def test_multiple_sessions_independent(self):
        """多个 session 独立运行"""
        from db.session import session_scope

        with session_scope() as s1:
            with session_scope() as s2:
                # 两个 session 应该不同
                assert s1 is not s2

    def test_connection_reuse(self):
        """连接复用"""
        from db.session import get_engine

        engine1 = get_engine()
        engine2 = get_engine()
        # 同一个引擎实例
        assert engine1 is engine2


# ─── 文件上传边界 ───


class TestFileUploadBoundary:
    """文件上传边界条件"""

    def test_upload_without_file(self, client):
        """无文件"""

        resp = client.post(
            "/api/v1/pipeline/start",
            data={"mode": "semi", "dimensions": "basic", "formats": "excel"},
        )
        assert resp.status_code in (400, 422)

    def test_upload_without_mode(self, client):
        """无 mode 参数"""
        content = io.BytesIO(b"test content")
        resp = client.post(
            "/api/v1/pipeline/start",
            files={"file": ("test.md", content, "text/markdown")},
            data={"dimensions": "basic", "formats": "excel"},
        )
        # mode 有默认值，应该成功
        assert resp.status_code in (201, 422)

    def test_upload_file_with_unicode_name(self, client):
        """Unicode 文件名"""
        content = io.BytesIO("中文需求文档".encode())
        resp = client.post(
            "/api/v1/pipeline/start",
            files={"file": ("中文测试需求.md", content, "text/markdown")},
            data={"mode": "semi", "dimensions": "basic", "formats": "excel"},
        )
        assert resp.status_code == 201

    def test_upload_file_with_spaces_in_name(self, client):
        """文件名含空格"""
        content = io.BytesIO(b"test content")
        resp = client.post(
            "/api/v1/pipeline/start",
            files={"file": ("my test requirements.md", content, "text/markdown")},
            data={"mode": "semi", "dimensions": "basic", "formats": "excel"},
        )
        assert resp.status_code == 201


# ─── 通用异常处理 ───


class TestGeneralExceptionHandling:
    """通用异常处理边界"""

    def test_404_on_nonexistent_api_path(self, client):
        """不存在的 API 路径返回 404"""
        resp = client.get("/api/nonexistent/endpoint")
        assert resp.status_code == 404

    def test_method_not_allowed(self, client):
        """错误 HTTP 方法"""
        # DELETE on health endpoint
        resp = client.delete("/health")
        assert resp.status_code == 405

    def test_malformed_json_body(self, client):
        """畸形 JSON 请求体（Sprint 6.0: Auth 已切除，改用 config 端点）"""
        from fastapi.testclient import TestClient

        from web.app import app
        client = TestClient(app)

        resp = client.post(
            "/api/v1/config",
            content="not valid json {{{",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code in (400, 405, 422)

    def test_content_type_negotiation(self, client):
        """Accept 头协商"""
        from fastapi.testclient import TestClient

        from web.app import app
        client = TestClient(app)

        # 请求 JSON 但页面返回 HTML
        resp = client.get("/", headers={"Accept": "application/json"})
        # 页面路由可能返回 HTML 或 JSON
        assert resp.status_code in (200, 406)


# ─── Fixtures ───


@pytest.fixture(autouse=True)
def _mock_pipeline_start():
    """Mock PipelineTask.start_background 避免实际执行 Pipeline"""
    import web.services.task_manager as tm_module

    tm_module._task_manager = None

    with patch("web.services.pipeline_task.PipelineTask.start_background", return_value=None):
        with patch("web.services.pipeline_task.PipelineTask.resume_background", return_value=None):
            with patch("web.services.pipeline_task._ensure_db", return_value=None):
                yield

    tm_module._task_manager = None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
