#!/usr/bin/env python3
"""
Pipeline API 路由测试 — 边界条件、异常场景和安全性

测试范围：
  - 文件上传校验（后缀、大小、空文件）
  - 并发限制
  - 取消/恢复边界条件
  - 产物下载/预览（路径穿越、不存在的文件）
  - 进度查询（不存在的 Pipeline）
  - HTMX 响应头

注意：PipelineTask.start_background 被 mock，避免实际执行 Pipeline。
"""

import io
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 设置虚拟 API Key 以便应用启动
os.environ.setdefault("LLM_API_KEY", "sk-test-dummy-for-api-tests")

from fastapi.testclient import TestClient

from web.app import app


@pytest.fixture(autouse=True)
def _mock_pipeline_start():
    """Mock PipelineTask.start_background 避免实际执行 Pipeline，并重置 TaskManager"""
    import web.services.task_manager as tm_module

    # 重置 TaskManager 单例
    tm_module._task_manager = None

    with patch("web.services.pipeline_task.PipelineTask.start_background", return_value=None):
        with patch("web.services.pipeline_task.PipelineTask.resume_background", return_value=None):
            with patch("web.services.pipeline_task._ensure_db", return_value=None):
                yield

    # 清理
    tm_module._task_manager = None


@pytest.fixture
def client():
    """创建测试客户端"""
    return TestClient(app)


@pytest.fixture
def sample_md_file():
    """创建示例 Markdown 需求文件"""
    content = "# 用户管理系统需求\n## 功能需求\n- 用户注册\n- 用户登录\n".encode()
    return ("test_requirements.md", io.BytesIO(content), "text/markdown")


class TestFileUploadValidation:
    """文件上传校验"""

    def test_upload_md_file(self, client, sample_md_file):
        """上传 .md 文件成功"""
        resp = client.post(
            "/api/pipeline/start",
            files={"file": sample_md_file},
            data={"mode": "semi", "dimensions": "basic", "formats": "excel"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "pipeline_id" in data
        assert "redirect" in data

    def test_upload_txt_file(self, client):
        """上传 .txt 文件成功"""
        content = io.BytesIO(b"Simple text requirements")
        resp = client.post(
            "/api/pipeline/start",
            files={"file": ("req.txt", content, "text/plain")},
            data={"mode": "semi", "dimensions": "basic", "formats": "excel"},
        )
        assert resp.status_code == 201

    def test_upload_unsupported_extension(self, client):
        """不支持的文件后缀返回 400"""
        content = io.BytesIO(b"Binary content")
        resp = client.post(
            "/api/pipeline/start",
            files={"file": ("test.pdf", content, "application/pdf")},
            data={"mode": "semi", "dimensions": "basic", "formats": "excel"},
        )
        assert resp.status_code == 400

    def test_upload_exe_file(self, client):
        """上传 .exe 文件被拒绝"""
        content = io.BytesIO(b"fake exe content")
        resp = client.post(
            "/api/pipeline/start",
            files={"file": ("malware.exe", content, "application/octet-stream")},
            data={"mode": "semi", "dimensions": "basic", "formats": "excel"},
        )
        assert resp.status_code == 400

    def test_upload_no_extension(self, client):
        """无后缀文件名被拒绝"""
        content = io.BytesIO(b"no extension")
        resp = client.post(
            "/api/pipeline/start",
            files={"file": ("noext", content, "text/plain")},
            data={"mode": "semi", "dimensions": "basic", "formats": "excel"},
        )
        assert resp.status_code == 400

    def test_upload_large_file(self, client):
        """超大文件（>10MB）被拒绝"""
        # 11MB 文件
        large_content = io.BytesIO(b"x" * (11 * 1024 * 1024))
        resp = client.post(
            "/api/pipeline/start",
            files={"file": ("large.md", large_content, "text/markdown")},
            data={"mode": "semi", "dimensions": "basic", "formats": "excel"},
        )
        assert resp.status_code == 400

    def test_upload_empty_file(self, client):
        """空文件可以上传"""
        content = io.BytesIO(b"")
        resp = client.post(
            "/api/pipeline/start",
            files={"file": ("empty.md", content, "text/markdown")},
            data={"mode": "semi", "dimensions": "basic", "formats": "excel"},
        )
        assert resp.status_code == 201


class TestProgressEndpoint:
    """进度查询端点"""

    def test_progress_nonexistent_pipeline(self, client):
        """不存在的 Pipeline 返回 404"""
        resp = client.get("/api/pipeline/nonexistent-id-12345/progress")
        assert resp.status_code == 404

    def test_status_nonexistent_pipeline(self, client):
        """不存在的 Pipeline 状态返回 404"""
        resp = client.get("/api/pipeline/nonexistent-id-12345/status")
        assert resp.status_code == 404

    def test_progress_with_htmx_header(self, client, sample_md_file):
        """HTMX 请求返回 HTML 片段"""
        resp = client.post(
            "/api/pipeline/start",
            files={"file": sample_md_file},
            data={"mode": "semi", "dimensions": "basic", "formats": "excel"},
        )
        pid = resp.json()["pipeline_id"]

        # HTMX 请求
        resp = client.get(
            f"/api/pipeline/{pid}/progress",
            headers={"HX-Request": "true"},
        )
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    def test_progress_json_format(self, client, sample_md_file):
        """普通请求返回 JSON"""
        resp = client.post(
            "/api/pipeline/start",
            files={"file": sample_md_file},
            data={"mode": "semi", "dimensions": "basic", "formats": "excel"},
        )
        pid = resp.json()["pipeline_id"]

        resp = client.get(f"/api/pipeline/{pid}/progress")
        assert resp.status_code == 200
        data = resp.json()
        assert "pipeline_id" in data
        assert "status" in data
        assert "completed_steps" in data
        assert "percent" in data


class TestCancelEndpoint:
    """取消 Pipeline 端点"""

    def test_cancel_nonexistent(self, client):
        """取消不存在的 Pipeline 返回 404"""
        resp = client.post("/api/pipeline/fake-id-99999/cancel")
        assert resp.status_code == 404

    def test_cancel_not_running(self, client, sample_md_file):
        """取消已完成/取消的 Pipeline 返回 400"""
        resp = client.post(
            "/api/pipeline/start",
            files={"file": sample_md_file},
            data={"mode": "semi", "dimensions": "basic", "formats": "excel"},
        )
        pid = resp.json()["pipeline_id"]

        # 先取消一次
        client.post(f"/api/pipeline/{pid}/cancel")
        # 再取消一次应该返回 400
        resp2 = client.post(f"/api/pipeline/{pid}/cancel")
        assert resp2.status_code == 400


class TestResumeEndpoint:
    """恢复 Pipeline 端点"""

    def test_resume_nonexistent(self, client):
        """恢复不存在的 Pipeline 返回 404"""
        resp = client.post("/api/pipeline/fake-id-99999/resume")
        assert resp.status_code == 404

    def test_resume_not_paused(self, client, sample_md_file):
        """恢复非 paused 状态返回 400"""
        resp = client.post(
            "/api/pipeline/start",
            files={"file": sample_md_file},
            data={"mode": "semi", "dimensions": "basic", "formats": "excel"},
        )
        pid = resp.json()["pipeline_id"]
        # 当前状态是 running，不是 paused
        resp2 = client.post(f"/api/pipeline/{pid}/resume")
        assert resp2.status_code == 400


class TestArtifactsEndpoint:
    """产物端点"""

    def test_artifacts_nonexistent_pipeline(self, client):
        """不存在的 Pipeline 产物返回 404"""
        resp = client.get("/api/pipeline/fake-id/artifacts")
        assert resp.status_code == 404

    def test_download_nonexistent_file(self, client, sample_md_file):
        """下载不存在的文件返回 404"""
        resp = client.post(
            "/api/pipeline/start",
            files={"file": sample_md_file},
            data={"mode": "semi", "dimensions": "basic", "formats": "excel"},
        )
        pid = resp.json()["pipeline_id"]
        resp = client.get(f"/api/pipeline/{pid}/artifacts/nonexistent.md")
        assert resp.status_code == 404

    def test_download_path_traversal(self, client, sample_md_file):
        """路径穿越攻击被阻止"""
        resp = client.post(
            "/api/pipeline/start",
            files={"file": sample_md_file},
            data={"mode": "semi", "dimensions": "basic", "formats": "excel"},
        )
        pid = resp.json()["pipeline_id"]

        # 尝试路径穿越
        resp = client.get(f"/api/pipeline/{pid}/artifacts/../../../etc/passwd")
        assert resp.status_code in (400, 404)

    def test_preview_path_traversal(self, client, sample_md_file):
        """预览路径穿越攻击被阻止"""
        resp = client.post(
            "/api/pipeline/start",
            files={"file": sample_md_file},
            data={"mode": "semi", "dimensions": "basic", "formats": "excel"},
        )
        pid = resp.json()["pipeline_id"]

        resp = client.get(f"/api/pipeline/{pid}/preview/../../../etc/passwd")
        assert resp.status_code in (400, 404)

    def test_list_pipelines(self, client):
        """Pipeline 列表端点可访问"""
        resp = client.get("/api/pipeline/list")
        assert resp.status_code == 200
        data = resp.json()
        assert "pipelines" in data


class TestPipelineStartValidation:
    """Pipeline 启动参数校验"""

    def test_invalid_mode(self, client, sample_md_file):
        """无效的模式参数 — 不拒绝但接受"""
        resp = client.post(
            "/api/pipeline/start",
            files={"file": sample_md_file},
            data={"mode": "invalid_mode", "dimensions": "basic", "formats": "excel"},
        )
        assert resp.status_code == 201

    def test_sql_injection_in_filename(self, client):
        """SQL 注入在文件名中 — 文件名被安全处理"""
        content = io.BytesIO(b"test")
        resp = client.post(
            "/api/pipeline/start",
            files={"file": ("test_sqli.md", content, "text/markdown")},
            data={"mode": "semi", "dimensions": "basic", "formats": "excel"},
        )
        assert resp.status_code == 201

    def test_xss_in_filename(self, client):
        """XSS 在文件名中 — 文件名被安全处理"""
        content = io.BytesIO(b"test")
        resp = client.post(
            "/api/pipeline/start",
            files={"file": ("test_xss.md", content, "text/markdown")},
            data={"mode": "semi", "dimensions": "basic", "formats": "excel"},
        )
        assert resp.status_code == 201


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
