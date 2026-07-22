#!/usr/bin/env python3
"""
web/api/pipeline.py 单元测试。

目标：将 Pipeline API 路由的覆盖率提升到 90%+。
覆盖所有端点：start / progress / status / list / cancel / resume /
artifacts / download / preview / export_pytest_project，以及辅助函数。
"""

import io
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("LLM_API_KEY", "test-key")


# ═══════════════════════════════════════════════════════════════
# 辅助：构造 mock TaskManager / PipelineTask
# ═══════════════════════════════════════════════════════════════


def _make_mock_task(status="running", pipeline_id="pid-test",
                    output_dir="/tmp/output", completed=None):
    """构造 mock PipelineTask。"""
    task = MagicMock()
    task.pipeline_id = pipeline_id
    task.status = status
    task.output_dir = output_dir
    task.completed_steps = completed or [1, 2, 3]
    task.get_progress.return_value = {
        "pipeline_id": pipeline_id,
        "percent": 50,
        "status": status,
        "mode": "semi",
        "completed_steps": task.completed_steps,
        "current_step": 4,
        "steps": [],
        "logs": [],
        "kb_ingest": {"cases": 0, "pitfalls": 0},
        "llm_stats": {},
        "error": "",
        "started_at": "2026-07-22T10:00:00",
    }
    task._on_log = MagicMock()
    task.resume_background = MagicMock()
    task.cancel = MagicMock()
    return task


def _make_mock_tm(task=None, tasks_list=None, is_full=False):
    """构造 mock TaskManager。"""
    tm = MagicMock()
    tm.get_task.return_value = task
    tm.is_full.return_value = is_full
    tm.list_tasks.return_value = tasks_list or []
    tm.create_task.return_value = _make_mock_task(status="running")
    tm.rebuild_task_from_db.return_value = None
    return tm


# ═══════════════════════════════════════════════════════════════
# 纯函数 _detect_file_type
# ═══════════════════════════════════════════════════════════════


class TestDetectFileType:
    """测试文件类型推断函数。"""

    def test_detect_markdown(self):
        """后缀 .md → markdown。"""
        from web.api.pipeline import _detect_file_type
        assert _detect_file_type("report.md") == "markdown"

    def test_detect_excel(self):
        """后缀 .xlsx → excel。"""
        from web.api.pipeline import _detect_file_type
        assert _detect_file_type("cases.xlsx") == "excel"

    def test_detect_xmind(self):
        """其他后缀 → xmind。"""
        from web.api.pipeline import _detect_file_type
        assert _detect_file_type("map.xmind") == "xmind"


# ═══════════════════════════════════════════════════════════════
# POST /start — 上传需求 + 启动
# ═══════════════════════════════════════════════════════════════


class TestStartPipeline:
    """测试启动 Pipeline 端点。"""

    def test_start_invalid_extension(self, client):
        """不允许的文件后缀 → 400。"""
        resp = client.post("/api/v1/pipeline/start",
                           files={"file": ("test.pdf", b"x", "application/pdf")})
        assert resp.status_code == 400

    def test_start_file_too_large(self, client):
        """文件超过 10MB → 400。"""
        big = b"x" * (10 * 1024 * 1024 + 1)
        resp = client.post("/api/v1/pipeline/start",
                           files={"file": ("test.md", big, "text/plain")})
        assert resp.status_code == 400

    def test_start_concurrent_full(self, client):
        """并发任务已达上限 → 429。"""
        tm = _make_mock_tm(is_full=True)
        with patch("web.api.pipeline.get_task_manager", return_value=tm):
            resp = client.post("/api/v1/pipeline/start",
                               files={"file": ("test.md", "# requirement".encode(),
                                       "text/plain")})
        assert resp.status_code == 429

    def test_start_success(self, client, tmp_path):
        """正常启动 → 201。"""
        tm = _make_mock_tm(task=_make_mock_task())
        with patch("web.api.pipeline.get_task_manager", return_value=tm), \
             patch("web.api.pipeline.load_config", return_value={}):
            resp = client.post("/api/v1/pipeline/start",
                               files={"file": ("req.md", "# 需求文档".encode(),
                                       "text/plain")})
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "running"
        assert "pipeline_id" in data

    def test_start_filename_sanitization(self, client):
        """文件名含特殊字符时被清理（不崩溃）。"""
        tm = _make_mock_tm(task=_make_mock_task())
        with patch("web.api.pipeline.get_task_manager", return_value=tm), \
             patch("web.api.pipeline.load_config", return_value={}):
            resp = client.post("/api/v1/pipeline/start",
                               files={"file": ("需../../求.md", b"# test",
                                       "text/plain")})
        assert resp.status_code == 201


# ═══════════════════════════════════════════════════════════════
# GET /progress — 获取进度
# ═══════════════════════════════════════════════════════════════


class TestGetProgress:
    """测试获取进度端点。"""

    def test_progress_in_memory_task(self, client):
        """内存中存在的任务 → 返回 task.get_progress()。"""
        task = _make_mock_task()
        tm = _make_mock_tm(task=task)
        with patch("web.api.pipeline.get_task_manager", return_value=tm):
            resp = client.get("/api/v1/pipeline/pid-1/progress")
        assert resp.status_code == 200
        assert resp.json()["pipeline_id"] == "pid-test"

    def test_progress_db_fallback(self, client):
        """内存无任务 → 回退 DB 进度视图。"""
        tm = _make_mock_tm(task=None)
        db_data = {"pipeline_id": "pid-db", "status": "done", "percent": 100}
        with patch("web.api.pipeline.get_task_manager", return_value=tm), \
             patch("web.api.pipeline._db_progress", return_value=db_data):
            resp = client.get("/api/v1/pipeline/pid-db/progress")
        assert resp.status_code == 200
        assert resp.json()["pipeline_id"] == "pid-db"

    def test_progress_db_exception(self, client):
        """DB 回退查询抛非 HTTPException → 404。"""
        tm = _make_mock_tm(task=None)
        with patch("web.api.pipeline.get_task_manager", return_value=tm), \
             patch("web.api.pipeline._db_progress",
                   side_effect=ValueError("corrupt")):
            resp = client.get("/api/v1/pipeline/pid-x/progress")
        assert resp.status_code == 404

    def test_progress_not_found(self, client):
        """DB 也无记录 → 404。"""
        from fastapi import HTTPException
        tm = _make_mock_tm(task=None)
        with patch("web.api.pipeline.get_task_manager", return_value=tm), \
             patch("web.api.pipeline._db_progress",
                   side_effect=HTTPException(404, "不存在")):
            resp = client.get("/api/v1/pipeline/pid-x/progress")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════
# GET /status — 详细状态
# ═══════════════════════════════════════════════════════════════


class TestGetStatus:
    """测试获取详细状态端点。"""

    def test_status_in_memory(self, client):
        """内存任务状态。"""
        tm = _make_mock_tm(task=_make_mock_task())
        with patch("web.api.pipeline.get_task_manager", return_value=tm):
            resp = client.get("/api/v1/pipeline/pid-1/status")
        assert resp.status_code == 200

    def test_status_db_fallback(self, client):
        """内存无 → DB 回退。"""
        tm = _make_mock_tm(task=None)
        with patch("web.api.pipeline.get_task_manager", return_value=tm), \
             patch("web.api.pipeline._db_progress",
                   return_value={"pipeline_id": "x", "status": "done"}):
            resp = client.get("/api/v1/pipeline/pid-1/status")
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════
# GET /list — 任务列表
# ═══════════════════════════════════════════════════════════════


class TestListPipelines:
    """测试任务列表端点（分页 + 搜索 + 统计）。"""

    def test_list_with_pagination(self, client):
        """分页参数正确返回。"""
        tasks = [
            {"pipeline_id": f"pid-{i}", "status": "done",
             "requirements": f"req{i}.md", "mode": "semi"}
            for i in range(5)
        ]
        tm = _make_mock_tm(tasks_list=tasks)
        with patch("web.api.pipeline.get_task_manager", return_value=tm):
            resp = client.get("/api/v1/pipeline/list?page=1&page_size=3")
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 3
        assert data["pages"] == 2
        assert data["all_stats"]["done"] == 5

    def test_list_keyword_filter(self, client):
        """关键词搜索过滤。"""
        tasks = [
            {"pipeline_id": "pid-abc", "status": "running",
             "requirements": "req1.md", "mode": "semi"},
            {"pipeline_id": "pid-xyz", "status": "done",
             "requirements": "req2.md", "mode": "auto"},
        ]
        tm = _make_mock_tm(tasks_list=tasks)
        with patch("web.api.pipeline.get_task_manager", return_value=tm):
            resp = client.get("/api/v1/pipeline/list?keyword=abc")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["pipeline_id"] == "pid-abc"

    def test_list_status_filter(self, client):
        """状态精确过滤。"""
        tasks = [
            {"pipeline_id": "p1", "status": "running",
             "requirements": "a.md", "mode": "semi"},
            {"pipeline_id": "p2", "status": "done",
             "requirements": "b.md", "mode": "semi"},
            {"pipeline_id": "p3", "status": "done",
             "requirements": "c.md", "mode": "semi"},
        ]
        tm = _make_mock_tm(tasks_list=tasks)
        with patch("web.api.pipeline.get_task_manager", return_value=tm):
            resp = client.get("/api/v1/pipeline/list?status=done")
        data = resp.json()
        assert data["total"] == 2
        assert all(t["status"] == "done" for t in data["items"])

    def test_list_invalid_pagination(self, client):
        """非法分页参数被钳制到默认值。"""
        tm = _make_mock_tm(tasks_list=[])
        with patch("web.api.pipeline.get_task_manager", return_value=tm):
            resp = client.get("/api/v1/pipeline/list?page=0&page_size=200")
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 20

    def test_list_running_stats(self, client):
        """统计 running/pending 计数。"""
        tasks = [
            {"pipeline_id": "p1", "status": "running",
             "requirements": "a.md", "mode": "semi"},
            {"pipeline_id": "p2", "status": "pending",
             "requirements": "b.md", "mode": "semi"},
            {"pipeline_id": "p3", "status": "error",
             "requirements": "c.md", "mode": "semi"},
        ]
        tm = _make_mock_tm(tasks_list=tasks)
        with patch("web.api.pipeline.get_task_manager", return_value=tm):
            resp = client.get("/api/v1/pipeline/list")
        stats = resp.json()["all_stats"]
        assert stats["running"] == 2  # running + pending
        assert stats["other"] == 1   # error


# ═══════════════════════════════════════════════════════════════
# POST /cancel — 取消 Pipeline
# ═══════════════════════════════════════════════════════════════


class TestCancelPipeline:
    """测试取消 Pipeline 端点。"""

    def test_cancel_success(self, client):
        """running 状态任务取消成功。"""
        task = _make_mock_task(status="running")
        tm = _make_mock_tm(task=task)
        with patch("web.api.pipeline.get_task_manager", return_value=tm):
            resp = client.post("/api/v1/pipeline/pid-1/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"
        task.cancel.assert_called_once()

    def test_cancel_wrong_status(self, client):
        """done 状态不允许取消 → 400。"""
        task = _make_mock_task(status="done")
        tm = _make_mock_tm(task=task)
        with patch("web.api.pipeline.get_task_manager", return_value=tm):
            resp = client.post("/api/v1/pipeline/pid-1/cancel")
        assert resp.status_code == 400

    def test_cancel_not_found(self, client):
        """任务不存在 → 404。"""
        tm = _make_mock_tm(task=None)
        with patch("web.api.pipeline.get_task_manager", return_value=tm):
            resp = client.post("/api/v1/pipeline/pid-x/cancel")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════
# POST /resume — 断点继续
# ═══════════════════════════════════════════════════════════════


class TestResumePipeline:
    """测试断点继续端点。"""

    def test_resume_in_memory_task(self, client):
        """内存中 paused 状态任务继续执行。"""
        task = _make_mock_task(status="paused")
        tm = _make_mock_tm(task=task)
        with patch("web.api.pipeline.get_task_manager", return_value=tm):
            resp = client.post("/api/v1/pipeline/pid-1/resume")
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"
        task.resume_background.assert_called_once()

    def test_resume_with_excel_file(self, client, tmp_path):
        """继续时上传 Excel → 覆盖旧文件。"""
        out_dir = tmp_path / "output"
        out_dir.mkdir()
        task = _make_mock_task(status="paused", output_dir=str(out_dir))
        tm = _make_mock_tm(task=task)
        with patch("web.api.pipeline.get_task_manager", return_value=tm):
            resp = client.post("/api/v1/pipeline/pid-1/resume",
                               files={"file": ("result.xlsx", b"fake-excel",
                                       "application/vnd.ms-excel")})
        assert resp.status_code == 200
        # 验证文件被写入
        assert (out_dir / "testcases.xlsx").exists()

    def test_resume_oversized_excel(self, client):
        """继续时上传超大 Excel → 400。"""
        task = _make_mock_task(status="paused")
        tm = _make_mock_tm(task=task)
        big = b"x" * (10 * 1024 * 1024 + 1)
        with patch("web.api.pipeline.get_task_manager", return_value=tm):
            resp = client.post("/api/v1/pipeline/pid-1/resume",
                               files={"file": ("big.xlsx", big,
                                       "application/vnd.ms-excel")})
        assert resp.status_code == 400

    def test_resume_rebuild_from_db(self, client):
        """interrupted 任务从 DB 重建。"""
        task = _make_mock_task(status="interrupted")
        tm = _make_mock_tm(task=None)
        tm.rebuild_task_from_db.return_value = task
        with patch("web.api.pipeline.get_task_manager", return_value=tm):
            resp = client.post("/api/v1/pipeline/pid-1/resume")
        assert resp.status_code == 200
        tm.rebuild_task_from_db.assert_called_once_with("pid-1")

    def test_resume_not_found(self, client):
        """任务不存在且 DB 无记录 → 404。"""
        tm = _make_mock_tm(task=None)
        tm.rebuild_task_from_db.return_value = None
        with patch("web.api.pipeline.get_task_manager", return_value=tm):
            resp = client.post("/api/v1/pipeline/pid-x/resume")
        assert resp.status_code == 404

    def test_resume_wrong_status(self, client):
        """running 状态不允许继续 → 400。"""
        task = _make_mock_task(status="running")
        tm = _make_mock_tm(task=task)
        with patch("web.api.pipeline.get_task_manager", return_value=tm):
            resp = client.post("/api/v1/pipeline/pid-1/resume")
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════
# GET /artifacts — 产物列表
# ═══════════════════════════════════════════════════════════════


class TestListArtifacts:
    """测试产物列表端点。"""

    def test_artifacts_list(self, client, tmp_path):
        """列出存在的产物文件。"""
        # 创建一些产物文件
        (tmp_path / "testpoints.md").write_text("# 测试点")
        (tmp_path / "testcases.xlsx").write_bytes(b"fake")
        task = _make_mock_task(output_dir=str(tmp_path))
        tm = _make_mock_tm(task=task)
        with patch("web.api.pipeline.get_task_manager", return_value=tm):
            resp = client.get("/api/v1/pipeline/pid-1/artifacts")
        assert resp.status_code == 200
        data = resp.json()
        names = [a["name"] for a in data["artifacts"]]
        assert "testpoints.md" in names
        assert "testcases.xlsx" in names

    def test_artifacts_not_found(self, client):
        """任务不存在（内存和 DB 都无）→ 404。"""
        tm = _make_mock_tm(task=None)
        with patch("web.api.pipeline.get_task_manager", return_value=tm):
            with patch("db.repository.get_repository") as mock_repo:
                repo = MagicMock()
                repo.get_pipeline.return_value = None
                mock_repo.return_value = repo
                resp = client.get("/api/v1/pipeline/pid-x/artifacts")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════
# GET /artifacts/{name} — 下载产物
# ═══════════════════════════════════════════════════════════════


class TestDownloadArtifact:
    """测试下载产物端点。"""

    def test_download_success(self, client, tmp_path):
        """成功下载产物文件。"""
        (tmp_path / "report.md").write_text("# 报告内容")
        task = _make_mock_task(output_dir=str(tmp_path))
        tm = _make_mock_tm(task=task)
        with patch("web.api.pipeline.get_task_manager", return_value=tm):
            resp = client.get("/api/v1/pipeline/pid-1/artifacts/report.md")
        assert resp.status_code == 200

    def test_download_path_traversal(self, client, tmp_path):
        """路径穿越攻击 → 400。"""
        task = _make_mock_task(output_dir=str(tmp_path))
        tm = _make_mock_tm(task=task)
        with patch("web.api.pipeline.get_task_manager", return_value=tm):
            resp = client.get("/api/v1/pipeline/pid-1/artifacts/..%2Fetc%2Fpasswd")
        assert resp.status_code in (400, 404)

    def test_download_not_exist(self, client, tmp_path):
        """文件不存在 → 404。"""
        task = _make_mock_task(output_dir=str(tmp_path))
        tm = _make_mock_tm(task=task)
        with patch("web.api.pipeline.get_task_manager", return_value=tm):
            resp = client.get("/api/v1/pipeline/pid-1/artifacts/nonexistent.md")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════
# GET /preview/{name} — 预览产物
# ═══════════════════════════════════════════════════════════════


class TestPreviewArtifact:
    """测试预览产物端点。"""

    def test_preview_markdown(self, client, tmp_path):
        """预览 Markdown → HTML 渲染。"""
        (tmp_path / "testpoints.md").write_text("# 标题\n\n正文内容")
        task = _make_mock_task(output_dir=str(tmp_path))
        tm = _make_mock_tm(task=task)
        with patch("web.api.pipeline.get_task_manager", return_value=tm):
            resp = client.get("/api/v1/pipeline/pid-1/preview/testpoints.md")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "markdown"
        assert "<h1>" in data["html"] or "标题" in data["html"]

    def test_preview_excel(self, client, tmp_path):
        """预览 Excel → 二维数组。"""
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(["用例ID", "标题"])
        ws.append(["TC-001", "登录测试"])
        xlsx_path = tmp_path / "testcases.xlsx"
        wb.save(str(xlsx_path))

        task = _make_mock_task(output_dir=str(tmp_path))
        tm = _make_mock_tm(task=task)
        with patch("web.api.pipeline.get_task_manager", return_value=tm):
            resp = client.get("/api/v1/pipeline/pid-1/preview/testcases.xlsx")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "excel"
        assert len(data["rows"]) >= 2

    def test_preview_unsupported_format(self, client, tmp_path):
        """不支持预览的格式 → 400。"""
        (tmp_path / "file.xmind").write_bytes(b"binary")
        task = _make_mock_task(output_dir=str(tmp_path))
        tm = _make_mock_tm(task=task)
        with patch("web.api.pipeline.get_task_manager", return_value=tm):
            resp = client.get("/api/v1/pipeline/pid-1/preview/file.xmind")
        assert resp.status_code == 400

    def test_preview_not_found(self, client, tmp_path):
        """文件不存在 → 404。"""
        task = _make_mock_task(output_dir=str(tmp_path))
        tm = _make_mock_tm(task=task)
        with patch("web.api.pipeline.get_task_manager", return_value=tm):
            resp = client.get("/api/v1/pipeline/pid-1/preview/nonexistent.md")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════
# _preview_excel 异常处理
# ═══════════════════════════════════════════════════════════════


class TestPreviewExcelEdgeCases:
    """测试 Excel 预览的异常处理。"""

    def test_preview_excel_corrupt(self, tmp_path):
        """损坏的 Excel 文件 → HTTPException 500。"""
        from fastapi import HTTPException
        from web.api.pipeline import _preview_excel

        bad = tmp_path / "bad.xlsx"
        bad.write_bytes(b"not-an-excel")
        with pytest.raises(HTTPException) as exc:
            _preview_excel(bad)
        assert exc.value.status_code == 500


# ═══════════════════════════════════════════════════════════════
# _get_output_dir DB 回退
# ═══════════════════════════════════════════════════════════════


class TestGetOutputDirFallback:
    """测试 _get_output_dir 的 DB 回退逻辑。"""

    def test_output_dir_from_db(self, client):
        """内存无任务 → 从 DB 取 output_dir。"""
        tm = _make_mock_tm(task=None)
        with patch("web.api.pipeline.get_task_manager", return_value=tm):
            with patch("db.repository.get_repository") as mock_repo:
                repo = MagicMock()
                p = MagicMock()
                p.output_dir = "/data/output/123"
                repo.get_pipeline.return_value = p
                mock_repo.return_value = repo
                resp = client.get("/api/v1/pipeline/pid-1/artifacts")
        # /data/output/123 不存在 → 产物列表为空但 200
        assert resp.status_code == 200

    def test_output_dir_db_exception(self, client):
        """DB 查询异常 → 404。"""
        tm = _make_mock_tm(task=None)
        with patch("web.api.pipeline.get_task_manager", return_value=tm):
            with patch("db.repository.get_repository",
                       side_effect=RuntimeError("db error")):
                resp = client.get("/api/v1/pipeline/pid-x/artifacts")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════
# GET /export_pytest_project — 导出 PyTest 工程 ZIP
# ═══════════════════════════════════════════════════════════════


class TestExportPytestProject:
    """测试导出 PyTest 工程端点。"""

    def test_export_no_testcases_json(self, client, tmp_path):
        """testcases.json 不存在 → 404。"""
        task = _make_mock_task(output_dir=str(tmp_path))
        tm = _make_mock_tm(task=task)
        with patch("web.api.pipeline.get_task_manager", return_value=tm):
            resp = client.get("/api/v1/pipeline/pid-1/export_pytest_project")
        assert resp.status_code == 404

    def test_export_success(self, client, tmp_path):
        """成功导出 ZIP（mock export_project 生成文件）。"""
        # 创建 testcases.json
        json_data = [{"id": "TC-001", "title": "登录测试", "steps": ["打开页面"]}]
        (tmp_path / "testcases.json").write_text(json.dumps(json_data))

        task = _make_mock_task(output_dir=str(tmp_path))
        tm = _make_mock_tm(task=task)

        # mock export_project 生成临时工程目录
        def fake_export(json_path, project_dir, module_name="Tests"):
            proj = Path(project_dir)
            proj.mkdir(parents=True, exist_ok=True)
            (proj / "test_login.py").write_text("def test_login(): pass")
            return 1

        with patch("web.api.pipeline.get_task_manager", return_value=tm), \
             patch("scripts.export_pytest.export_project",
                   side_effect=fake_export):
            resp = client.get("/api/v1/pipeline/pid-1/export_pytest_project")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"

    def test_export_zero_cases(self, client, tmp_path):
        """export_project 返回 0（无可用用例）→ 500。"""
        (tmp_path / "testcases.json").write_text("[]")
        task = _make_mock_task(output_dir=str(tmp_path))
        tm = _make_mock_tm(task=task)
        with patch("web.api.pipeline.get_task_manager", return_value=tm), \
             patch("scripts.export_pytest.export_project", return_value=0):
            resp = client.get("/api/v1/pipeline/pid-1/export_pytest_project")
        assert resp.status_code == 500


# ═══════════════════════════════════════════════════════════════
# _preview_markdown — markdown 库缺失兜底
# ═══════════════════════════════════════════════════════════════


class TestPreviewMarkdownFallback:
    """测试 Markdown 预览的 markdown 库缺失兜底。"""

    def test_markdown_import_error_fallback(self, tmp_path):
        """markdown 库导入失败 → HTML 转义 + <pre> 兜底。"""
        from web.api.pipeline import _preview_markdown

        md_file = tmp_path / "test.md"
        md_file.write_text("# <script>alert(1)</script>")

        # 模拟 markdown 库不存在
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "markdown":
                raise ImportError("no module")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = _preview_markdown(md_file)

        assert result["type"] == "markdown"
        assert "<pre>" in result["html"]
        # XSS 防护：script 标签应被转义
        assert "&lt;script&gt;" in result["html"]


# ═══════════════════════════════════════════════════════════════
# _db_progress — DB 历史任务进度
# ═══════════════════════════════════════════════════════════════


class TestDBProgress:
    """测试从 DB 构建历史任务进度视图。"""

    def test_db_progress_success(self):
        """正常 DB 查询 → 构建进度视图。"""
        from web.api.pipeline import _db_progress

        # mock repo 返回
        with patch("db.repository.get_repository") as mock_repo:
            repo = MagicMock()
            p = MagicMock()
            p.id = "pid-db"
            p.status = "done"
            p.mode = "semi"
            p.error = ""
            p.started_at = datetime(2026, 7, 22, 10, 0, 0)
            p.output_dir = "/data/output"
            repo.get_pipeline.return_value = p
            repo.get_completed_step_ids.return_value = [0, 1, 2, 3, 4, 5, 6, 7]
            repo.get_steps.return_value = []
            mock_repo.return_value = repo

            result = _db_progress("pid-db")

        assert result["pipeline_id"] == "pid-db"
        assert result["status"] == "done"
        assert result["percent"] == 100

    def test_db_progress_not_found(self):
        """DB 无记录 → 404。"""
        from fastapi import HTTPException
        from web.api.pipeline import _db_progress

        with patch("db.repository.get_repository") as mock_repo:
            repo = MagicMock()
            repo.get_pipeline.return_value = None
            mock_repo.return_value = repo
            with pytest.raises(HTTPException) as exc:
                _db_progress("pid-x")
        assert exc.value.status_code == 404
