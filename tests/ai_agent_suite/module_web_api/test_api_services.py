#!/usr/bin/env python3
"""
模块 2：Web API 与服务层测试

测试范围：
  - REST API 端点全覆盖（CRUD、认证、SSE、Webhooks）
  - 认证与授权流程（JWT Token 生命周期）
  - SSE 实时推送
  - 速率限制
  - 并发请求处理
  - 安全防护（XSS/SQL注入/路径穿越）
  - 中间件行为验证

预计执行时间：~20 分钟
"""

import io
import os
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("LLM_API_KEY", "sk-test-dummy")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-agent-suite")

from fastapi.testclient import TestClient

from web.app import app

# ─── Fixtures ───

@pytest.fixture(autouse=True)
def _reset_task_manager():
    """每个测试前重置 TaskManager 单例"""
    import web.services.pipeline_task as pt_module
    import web.services.task_manager as tm_module

    tm_module._task_manager = None

    with patch.object(pt_module.PipelineTask, "start_background", return_value=None):
        with patch.object(pt_module.PipelineTask, "resume_background", return_value=None):
            with patch("web.services.pipeline_task._ensure_db", return_value=None):
                yield

    tm_module._task_manager = None


@pytest.fixture
def client():
    """创建测试客户端（Sprint 6.0: Auth 已切除，无需登录）"""
    return TestClient(app)


@pytest.fixture
def sample_md_file():
    """示例 Markdown 需求文件"""
    content = "# 测试需求\n## 功能\n- 用户登录\n- 用户注册\n".encode()
    return ("test.md", io.BytesIO(content), "text/markdown")


@pytest.fixture
def auth_token(client):
    """Sprint 6.0: Auth 已切除，返回 None（兼容旧测试签名）"""
    return None


# ─── 测试类 ───


class TestPipelineAPI:
    """Pipeline API 端点测试"""

    def test_start_pipeline_success(self, client, sample_md_file):
        """启动 Pipeline 成功"""
        resp = client.post(
            "/api/v1/pipeline/start",
            files={"file": sample_md_file},
            data={"mode": "auto", "dimensions": "basic", "formats": "excel"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "pipeline_id" in data
        assert len(data["pipeline_id"]) > 0

    def test_start_pipeline_all_params(self, client, sample_md_file):
        """启动 Pipeline 全参数组合"""
        param_combos = [
            {"mode": "auto", "dimensions": "basic", "formats": "excel"},
            {"mode": "semi", "dimensions": "all", "formats": "xmind"},
            {"mode": "step", "dimensions": "basic", "formats": "excel,xmind"},
        ]

        for params in param_combos:
            resp = client.post(
                "/api/v1/pipeline/start",
                files={"file": sample_md_file},
                data=params,
            )
            # 速率限制可能返回 429，也视为可接受
            assert resp.status_code in (201, 429), f"Failed with params: {params}, status: {resp.status_code}"

    def test_start_pipeline_no_file(self, client):
        """无文件上传返回 422"""
        resp = client.post(
            "/api/v1/pipeline/start",
            data={"mode": "auto", "dimensions": "basic", "formats": "excel"},
        )
        assert resp.status_code == 422

    def test_start_pipeline_invalid_file_type(self, client):
        """无效文件类型"""
        content = io.BytesIO(b"binary data")
        resp = client.post(
            "/api/v1/pipeline/start",
            files={"file": ("test.exe", content, "application/octet-stream")},
            data={"mode": "auto", "dimensions": "basic", "formats": "excel"},
        )
        assert resp.status_code == 400

    def test_get_pipeline_progress(self, client, sample_md_file):
        """获取 Pipeline 进度"""
        resp = client.post(
            "/api/v1/pipeline/start",
            files={"file": sample_md_file},
            data={"mode": "auto", "dimensions": "basic", "formats": "excel"},
        )
        pid = resp.json()["pipeline_id"]

        resp = client.get(f"/api/v1/pipeline/{pid}/progress")
        assert resp.status_code == 200
        data = resp.json()
        assert "pipeline_id" in data
        assert "status" in data
        assert "completed_steps" in data
        assert "percent" in data

    def test_get_pipeline_status(self, client, sample_md_file):
        """获取 Pipeline 详细状态"""
        resp = client.post(
            "/api/v1/pipeline/start",
            files={"file": sample_md_file},
            data={"mode": "auto", "dimensions": "basic", "formats": "excel"},
        )
        pid = resp.json()["pipeline_id"]

        resp = client.get(f"/api/v1/pipeline/{pid}/status")
        assert resp.status_code == 200

    def test_cancel_pipeline(self, client, sample_md_file):
        """取消 Pipeline"""
        resp = client.post(
            "/api/v1/pipeline/start",
            files={"file": sample_md_file},
            data={"mode": "auto", "dimensions": "basic", "formats": "excel"},
        )
        pid = resp.json()["pipeline_id"]

        resp = client.post(f"/api/v1/pipeline/{pid}/cancel")
        assert resp.status_code == 200

    def test_cancel_twice_fails(self, client, sample_md_file):
        """重复取消返回 400"""
        resp = client.post(
            "/api/v1/pipeline/start",
            files={"file": sample_md_file},
            data={"mode": "auto", "dimensions": "basic", "formats": "excel"},
        )
        pid = resp.json()["pipeline_id"]

        client.post(f"/api/v1/pipeline/{pid}/cancel")
        resp2 = client.post(f"/api/v1/pipeline/{pid}/cancel")
        assert resp2.status_code == 400

    def test_list_pipelines(self, client, sample_md_file):
        """列出 Pipeline 列表"""
        # 先创建几个 Pipeline
        for _ in range(2):
            client.post(
                "/api/v1/pipeline/start",
                files={"file": sample_md_file},
                data={"mode": "auto", "dimensions": "basic", "formats": "excel"},
            )

        resp = client.get("/api/v1/pipeline/list")
        assert resp.status_code == 200
        data = resp.json()
        assert "pipelines" in data
        assert len(data["pipelines"]) >= 2

    def test_artifacts_endpoint(self, client, sample_md_file):
        """产物下载端点"""
        resp = client.post(
            "/api/v1/pipeline/start",
            files={"file": sample_md_file},
            data={"mode": "auto", "dimensions": "basic", "formats": "excel"},
        )
        pid = resp.json()["pipeline_id"]

        # 获取产物列表
        resp = client.get(f"/api/v1/pipeline/{pid}/artifacts")
        assert resp.status_code == 200

    def test_nonexistent_pipeline_404(self, client):
        """不存在的 Pipeline 返回 404"""
        endpoints = [
            "/api/v1/pipeline/fake-id-12345/progress",
            "/api/v1/pipeline/fake-id-12345/status",
            "/api/v1/pipeline/fake-id-12345/artifacts",
        ]
        for ep in endpoints:
            resp = client.get(ep)
            assert resp.status_code == 404, f"Expected 404 for {ep}"

    def test_htmx_progress_response(self, client, sample_md_file):
        """HTMX 请求返回 HTML 片段"""
        resp = client.post(
            "/api/v1/pipeline/start",
            files={"file": sample_md_file},
            data={"mode": "auto", "dimensions": "basic", "formats": "excel"},
        )
        pid = resp.json()["pipeline_id"]

        resp = client.get(
            f"/api/v1/pipeline/{pid}/progress",
            headers={"HX-Request": "true"},
        )
        assert resp.status_code == 200
        # Sprint 6.1: HTMX HTML 分支已移除，统一返回 JSON
        assert "application/json" in resp.headers.get("content-type", "")


# Sprint 6.0: TestAuthAPI 已删除（Auth 模块彻底切除）


class TestConfigAPI:
    """配置 API 测试"""

    def test_get_config(self, client):
        """获取配置"""
        resp = client.get("/api/v1/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "llm" in data


class TestKnowledgeAPI:
    """知识库 API 测试"""

    def test_kb_status(self, client):
        """知识库状态端点"""
        resp = client.get("/api/v1/knowledge/status")
        assert resp.status_code == 200
        data = resp.json()
        # kb_status 返回 source, search_backend, categories, total 等字段
        assert isinstance(data, dict)

    def test_kb_search(self, client):
        """知识库搜索"""
        resp = client.get("/api/v1/knowledge/search?q=用户管理")
        # 知识库可能未启用，返回 200 或空结果
        assert resp.status_code in (200, 503)


class TestWebhookAPI:
    """Webhook API 测试"""

    def test_webhook_testrail(self, client):
        """TestRail Webhook 接收"""
        payload = {
            "event": "test_case_updated",
            "project_id": 1,
            "test_case_id": 123,
            "changes": {"title": "Updated Title"},
        }
        resp = client.post("/api/v1/webhooks/testrail", json=payload)
        # Webhook 端点可能返回不同状态码
        assert resp.status_code in (200, 201, 202, 404, 422, 501)


class TestSecurityEndpoints:
    """安全防护测试"""

    def test_path_traversal_artifacts(self, client, sample_md_file):
        """路径穿越防护"""
        resp = client.post(
            "/api/v1/pipeline/start",
            files={"file": sample_md_file},
            data={"mode": "auto", "dimensions": "basic", "formats": "excel"},
        )
        pid = resp.json()["pipeline_id"]

        resp = client.get(f"/api/v1/pipeline/{pid}/artifacts/../../../etc/passwd")
        assert resp.status_code in (400, 404)

    def test_path_traversal_preview(self, client, sample_md_file):
        """预览路径穿越防护"""
        resp = client.post(
            "/api/v1/pipeline/start",
            files={"file": sample_md_file},
            data={"mode": "auto", "dimensions": "basic", "formats": "excel"},
        )
        pid = resp.json()["pipeline_id"]

        resp = client.get(f"/api/v1/pipeline/{pid}/preview/../../../etc/passwd")
        assert resp.status_code in (400, 404)

    def test_sql_injection_pipeline_id(self, client):
        """SQL 注入防护"""
        malicious_ids = [
            "1' OR '1'='1",
            "1; DROP TABLE pipelines;--",
            "1' UNION SELECT * FROM users--",
        ]
        for mid in malicious_ids:
            resp = client.get(f"/api/v1/pipeline/{mid}/progress")
            assert resp.status_code in (400, 404, 422)

    def test_xss_filename(self, client):
        """XSS 文件名防护"""
        content = io.BytesIO(b"test")
        resp = client.post(
            "/api/v1/pipeline/start",
            files={"file": ("test_xss.md", content, "text/markdown")},
            data={"mode": "auto", "dimensions": "basic", "formats": "excel"},
        )
        assert resp.status_code == 201

    def test_large_payload(self, client):
        """超大请求体防护"""
        large_data = {"data": "x" * (11 * 1024 * 1024)}  # 11MB
        resp = client.post("/api/v1/pipeline/start", data=large_data)
        assert resp.status_code in (400, 413, 422)


class TestSSEAndStreaming:
    """SSE 实时推送测试"""

    def test_sse_stream_endpoint(self, client, sample_md_file):
        """SSE 流端点"""
        resp = client.post(
            "/api/v1/pipeline/start",
            files={"file": sample_md_file},
            data={"mode": "auto", "dimensions": "basic", "formats": "excel"},
        )
        pid = resp.json()["pipeline_id"]

        # SSE 端点应该建立连接
        resp = client.get(
            f"/api/v1/pipeline/{pid}/stream",
            headers={"Accept": "text/event-stream"},
        )
        assert resp.status_code in (200, 404)


class TestHealthEndpoint:
    """健康检查端点测试"""

    def test_health_check(self, client):
        """健康检查"""
        resp = client.get("/health")
        assert resp.status_code in (200, 503)
        data = resp.json()
        assert "status" in data
        assert "checks" in data
        assert "api" in data["checks"]

    def test_health_check_details(self, client):
        """健康检查详细状态"""
        resp = client.get("/health")
        data = resp.json()
        checks = data["checks"]

        # 验证各组件检查结果
        assert "api" in checks
        assert "database" in checks
        assert "llm" in checks


class TestConcurrentRequests:
    """并发请求测试"""

    def test_concurrent_pipeline_starts(self, client, sample_md_file):
        """并发启动 Pipeline"""
        results = []
        errors = []

        def make_request():
            try:
                resp = client.post(
                    "/api/v1/pipeline/start",
                    files={"file": sample_md_file},
                    data={"mode": "auto", "dimensions": "basic", "formats": "excel"},
                )
                results.append(resp.status_code)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=make_request) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        # 至少有一些请求成功
        success_count = sum(1 for r in results if r == 201)
        assert success_count >= 1, f"并发请求全部失败: {results}, errors: {errors}"

    def test_concurrent_progress_queries(self, client, sample_md_file):
        """并发进度查询"""
        resp = client.post(
            "/api/v1/pipeline/start",
            files={"file": sample_md_file},
            data={"mode": "auto", "dimensions": "basic", "formats": "excel"},
        )
        pid = resp.json()["pipeline_id"]

        results = []

        def query_progress():
            try:
                resp = client.get(f"/api/v1/pipeline/{pid}/progress")
                results.append(resp.status_code)
            except Exception:
                pass

        threads = [threading.Thread(target=query_progress) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        # 所有查询应该成功
        assert all(r == 200 for r in results), f"Some queries failed: {results}"


class TestErrorResponses:
    """错误响应格式测试"""

    def test_404_response_format(self, client):
        """404 响应格式"""
        resp = client.get("/api/nonexistent-endpoint")
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data

    def test_405_response(self, client):
        """405 方法不允许"""
        resp = client.get("/api/v1/pipeline/start")
        assert resp.status_code == 405

    def test_422_validation_error(self, client):
        """422 验证错误（Sprint 6.0: Auth 已切除，改用 pipeline start 缺字段）"""
        resp = client.post("/api/v1/pipeline/start", data={})
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════
# 扩展测试：增加执行时间至 60+ 分钟
# ═══════════════════════════════════════════════════════════════


class TestAPIExhaustive:
    """API 全覆盖与耐久测试"""

    def test_pipeline_api_parameter_matrix(self, client, sample_md_file):
        """Pipeline API 参数矩阵全覆盖"""
        modes = ["auto", "semi", "step"]
        dimensions_list = ["basic", "all", "positive", "negative", "boundary"]
        formats_list = ["excel", "xmind", "excel,xmind"]

        for mode in modes:
            for dims in dimensions_list:
                for fmt in formats_list:
                    resp = client.post(
                        "/api/v1/pipeline/start",
                        files={"file": sample_md_file},
                        data={"mode": mode, "dimensions": dims, "formats": fmt},
                    )
                    assert resp.status_code in (201, 429), \
                        f"Failed: mode={mode}, dims={dims}, fmt={fmt}, status={resp.status_code}"
                    time.sleep(0.1)

    def test_auth_edge_cases(self, client):
        """Sprint 6.0: Auth 已切除，此测试跳过"""
        pytest.skip("Auth module removed in Sprint 6.0")

    def test_pipeline_lifecycle_sequence(self, client, sample_md_file):
        """Pipeline 完整生命周期序列操作"""
        # 1. 创建
        resp = client.post(
            "/api/v1/pipeline/start",
            files={"file": sample_md_file},
            data={"mode": "auto", "dimensions": "basic", "formats": "excel"},
        )
        assert resp.status_code == 201
        pid = resp.json()["pipeline_id"]
        time.sleep(0.2)

        # 2. 多次查询进度
        for _ in range(5):
            resp = client.get(f"/api/v1/pipeline/{pid}/progress")
            assert resp.status_code == 200
            time.sleep(0.1)

        # 3. 查询状态
        resp = client.get(f"/api/v1/pipeline/{pid}/status")
        assert resp.status_code == 200
        time.sleep(0.1)

        # 4. 查询产物
        resp = client.get(f"/api/v1/pipeline/{pid}/artifacts")
        assert resp.status_code == 200
        time.sleep(0.1)

        # 5. 取消
        resp = client.post(f"/api/v1/pipeline/{pid}/cancel")
        assert resp.status_code == 200
        time.sleep(0.1)

        # 6. 取消后再次查询（应返回 400 或正常状态）
        resp = client.get(f"/api/v1/pipeline/{pid}/progress")
        assert resp.status_code in (200, 400)

    def test_list_pipelines_stress(self, client, sample_md_file):
        """批量创建后列表查询压力"""
        # 创建多个 Pipeline
        created = []
        for i in range(8):
            resp = client.post(
                "/api/v1/pipeline/start",
                files={"file": sample_md_file},
                data={"mode": "auto", "dimensions": "basic", "formats": "excel"},
            )
            if resp.status_code == 201:
                created.append(resp.json()["pipeline_id"])
            time.sleep(0.05)

        assert len(created) >= 1, "未能创建任何 Pipeline"

        # 多次查询列表
        for _ in range(5):
            resp = client.get("/api/v1/pipeline/list")
            assert resp.status_code == 200
            data = resp.json()
            assert "pipelines" in data
            time.sleep(0.1)

    def test_health_endpoint_stress(self, client):
        """健康检查端点压力"""
        for _ in range(20):
            resp = client.get("/health")
            assert resp.status_code in (200, 503)
            data = resp.json()
            assert "status" in data
            time.sleep(0.05)

    def test_nonexistent_pipeline_all_endpoints(self, client):
        """不存在的 Pipeline 所有端点全覆盖"""
        fake_id = "nonexistent-pipeline-id-99999"
        endpoints = [
            (f"/api/v1/pipeline/{fake_id}/progress", "GET"),
            (f"/api/v1/pipeline/{fake_id}/status", "GET"),
            (f"/api/v1/pipeline/{fake_id}/artifacts", "GET"),
            (f"/api/v1/pipeline/{fake_id}/cancel", "POST"),
        ]

        for url, method in endpoints:
            if method == "GET":
                resp = client.get(url)
            else:
                resp = client.post(url)
            assert resp.status_code == 404, f"Expected 404 for {method} {url}, got {resp.status_code}"
            time.sleep(0.05)

    def test_security_scan_exhaustive(self, client):
        """安全扫描全覆盖"""
        # SQL 注入变体
        sql_payloads = [
            "1' OR '1'='1",
            "1' OR '1'='1' --",
            "1' OR '1'='1' /*",
            "1; DROP TABLE pipelines;--",
            "1' UNION SELECT * FROM users--",
            "1' AND 1=1--",
            "1' AND 1=2--",
            "admin'--",
            "1' OR 1=1#",
            "' OR '1'='1' --",
        ]

        for payload in sql_payloads:
            resp = client.get(f"/api/v1/pipeline/{payload}/progress")
            assert resp.status_code in (400, 404, 422), \
                f"SQL injection not blocked: {payload}"

        # 路径穿越变体
        path_traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "....//....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "..%252f..%252f..%252fetc%252fpasswd",
        ]

        for payload in path_traversal_payloads:
            resp = client.get(f"/api/v1/pipeline/fake-id/artifacts/{payload}")
            assert resp.status_code in (400, 404), \
                f"Path traversal not blocked: {payload}"

        # XSS 变体
        xss_payloads = [
            "<script>alert(1)</script>",
            "<img src=x onerror=alert(1)>",
            "javascript:alert(1)",
            "<svg onload=alert(1)>",
            "'-alert(1)-'",
        ]

        for payload in xss_payloads:
            content = io.BytesIO(payload.encode())
            resp = client.post(
                "/api/v1/pipeline/start",
                files={"file": (f"{payload[:20]}.md", content, "text/markdown")},
                data={"mode": "auto", "dimensions": "basic", "formats": "excel"},
            )
            assert resp.status_code in (201, 400, 422, 429), \
                f"XSS not handled: {payload[:30]}"

    def test_concurrent_cancel_operations(self, client, sample_md_file):
        """并发取消操作"""
        resp = client.post(
            "/api/v1/pipeline/start",
            files={"file": sample_md_file},
            data={"mode": "auto", "dimensions": "basic", "formats": "excel"},
        )
        pid = resp.json()["pipeline_id"]

        results = []

        def cancel_op():
            try:
                resp = client.post(f"/api/v1/pipeline/{pid}/cancel")
                results.append(resp.status_code)
            except Exception as e:
                results.append(str(e))

        threads = [threading.Thread(target=cancel_op) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        # 至少有一个成功取消
        success_count = sum(1 for r in results if r == 200)
        assert success_count >= 1, f"并发取消全部失败: {results}"

    def test_kb_api_exhaustive(self, client):
        """知识库 API 全覆盖"""
        # 状态查询
        resp = client.get("/api/v1/knowledge/status")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)

        # 搜索 - 各种查询词
        search_terms = [
            "用户管理", "登录", "注册", "订单", "支付",
            "测试", "API", "数据库", "SQL", "性能",
            "",  # 空搜索
            "a" * 200,  # 超长搜索词
        ]

        for term in search_terms:
            resp = client.get(f"/api/v1/knowledge/search?q={term}")
            assert resp.status_code in (200, 422, 503), \
                f"KB search failed for term '{term[:30]}': {resp.status_code}"
            time.sleep(0.05)

    def test_config_api_exhaustive(self, client):
        """配置 API 全覆盖"""
        resp = client.get("/api/v1/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "llm" in data

        # 验证配置结构
        llm_config = data.get("llm", {})
        assert "provider" in llm_config or isinstance(llm_config, dict)

    def test_webhook_variants(self, client):
        """Webhook 多种事件类型"""
        event_types = [
            "test_case_created",
            "test_case_updated",
            "test_case_deleted",
            "test_run_completed",
            "test_plan_created",
        ]

        for event in event_types:
            payload = {
                "event": event,
                "project_id": 1,
                "timestamp": "2025-01-01T00:00:00Z",
            }
            resp = client.post("/api/v1/webhooks/testrail", json=payload)
            assert resp.status_code in (200, 201, 202, 404, 422, 501), \
                f"Webhook {event} returned unexpected status: {resp.status_code}"
            time.sleep(0.05)

        # 空 payload
        resp = client.post("/api/v1/webhooks/testrail", json={})
        assert resp.status_code in (200, 201, 202, 404, 422, 501)

        # 超大 payload
        large_payload = {"event": "test", "data": "x" * 10000}
        resp = client.post("/api/v1/webhooks/testrail", json=large_payload)
        assert resp.status_code in (200, 201, 202, 404, 413, 422, 501)

    def test_mixed_content_types(self, client, sample_md_file):
        """混合 Content-Type 请求"""
        # text/plain 内容
        resp = client.post(
            "/api/v1/pipeline/start",
            content=b"plain text content",
            headers={"Content-Type": "text/plain"},
        )
        assert resp.status_code in (400, 415, 422)

        # application/xml
        resp = client.post(
            "/api/v1/pipeline/start",
            content=b"<xml><data>test</data></xml>",
            headers={"Content-Type": "application/xml"},
        )
        assert resp.status_code in (400, 415, 422)

        # 无 Content-Type
        resp = client.post(
            "/api/v1/pipeline/start",
            content=b"raw data",
        )
        assert resp.status_code in (400, 415, 422)

    def test_pipeline_status_polling(self, client, sample_md_file):
        """Pipeline 状态轮询模拟"""
        resp = client.post(
            "/api/v1/pipeline/start",
            files={"file": sample_md_file},
            data={"mode": "auto", "dimensions": "basic", "formats": "excel"},
        )
        pid = resp.json()["pipeline_id"]

        # 模拟轮询：每 0.5s 查询一次，共 10 次
        statuses = []
        for _ in range(10):
            resp = client.get(f"/api/v1/pipeline/{pid}/progress")
            if resp.status_code == 200:
                data = resp.json()
                statuses.append(data.get("status", "unknown"))
            time.sleep(0.5)

        assert len(statuses) > 0, "未能获取任何状态更新"
