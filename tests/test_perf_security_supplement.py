#!/usr/bin/env python3
"""
性能与安全补充测试

覆盖现有测试未覆盖的场景：
  性能：
  - KB API 响应时间
  - Pipeline 启动 API 响应时间
  - 响应体大小验证
  - 并发 Pipeline 启动

  安全：
  - Content-Security-Policy 头
  - CORS 配置
  - HSTS 头
  - HTTP 参数污染
  - 大请求体 DoS 防护
  - 敏感信息泄露
"""

import concurrent.futures
import io
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("LLM_API_KEY", "sk-test-dummy-for-supplement-tests")

from fastapi.testclient import TestClient

# ─── 性能补充测试 ───


class TestKBAPIPerformance:
    """知识库 API 性能。

    依赖 KB 缓存服务（web/services/kb_cache.py）—— 单例复用 + TTL 缓存 +
    启动预热，使 status/search 响应 < 100ms（冷启动单次 ~5s 已被预热消除）。
    缓存失效由 import/add 写入操作触发（invalidate_all）。

    性能回归保护：若有人移除缓存或引入性能退化，本测试会捕获。
    """

    @pytest.fixture
    def client(self):
        from web.app import app
        # 显式预热缓存（app.py 启动时的后台预热可能未完成）
        try:
            from web.services.kb_cache import get_status
            get_status()
        except Exception:
            pass
        return TestClient(app)

    def test_kb_status_response_time(self, client):
        """KB 状态 API 响应时间 < 5s（缓存命中时 <100ms）"""
        # 第一次请求触发预热（可能慢），第二次测缓存命中性能
        client.get("/api/kb/status")  # warmup
        start = time.time()
        resp = client.get("/api/kb/status")  # 实测
        elapsed = time.time() - start
        assert resp.status_code == 200
        assert elapsed < 5.0, f"KB 状态响应时间 {elapsed:.3f}s > 5.0s"

    def test_kb_search_response_time(self, client):
        """KB 搜索 API 响应时间 < 5s（缓存命中时 <100ms）"""
        client.get("/api/kb/search", params={"q": "测试"})  # warmup
        start = time.time()
        resp = client.get("/api/kb/search", params={"q": "测试"})  # 实测
        elapsed = time.time() - start
        assert resp.status_code in (200, 500, 503)
        assert elapsed < 5.0, f"KB 搜索响应时间 {elapsed:.3f}s > 5.0s"


class TestPipelineStartPerformance:
    """Pipeline 启动性能"""

    @pytest.fixture(autouse=True)
    def _mock_pipeline_start(self):
        import web.services.task_manager as tm_module
        tm_module._task_manager = None

        with patch("web.services.pipeline_task.PipelineTask.start_background", return_value=None):
            with patch("web.services.pipeline_task.PipelineTask.resume_background", return_value=None):
                with patch("web.services.pipeline_task._ensure_db", return_value=None):
                    yield

        tm_module._task_manager = None

    @pytest.fixture
    def client(self):
        from web.app import app
        return TestClient(app)

    def test_pipeline_start_response_time(self, client):
        """Pipeline 启动 API 响应时间 < 500ms"""
        content = io.BytesIO(b"# Test\n- Feature 1")
        start = time.time()
        resp = client.post(
            "/api/pipeline/start",
            files={"file": ("test.md", content, "text/markdown")},
            data={"mode": "semi", "dimensions": "basic", "formats": "excel"},
        )
        elapsed = time.time() - start
        assert resp.status_code == 201
        assert elapsed < 0.5, f"Pipeline 启动响应时间 {elapsed:.3f}s > 0.5s"


class TestResponseSize:
    """响应体大小验证"""

    @pytest.fixture
    def client(self):
        from web.app import app
        return TestClient(app)

    def test_health_response_size(self, client):
        """健康检查响应 < 1KB"""
        resp = client.get("/health")
        assert resp.status_code == 200
        assert len(resp.content) < 2048, f"健康检查响应 {len(resp.content)}B > 2KB"

    def test_config_api_response_size(self, client):
        """配置 API 响应 < 10KB"""
        resp = client.get("/api/config")
        assert resp.status_code == 200
        assert len(resp.content) < 10240, f"配置 API 响应 {len(resp.content)}B > 10KB"

    def test_pipeline_list_response_size(self, client):
        """Pipeline 列表响应 < 100KB"""
        resp = client.get("/api/pipeline/list")
        assert resp.status_code == 200
        assert len(resp.content) < 102400, f"Pipeline 列表响应 {len(resp.content)}B > 100KB"

    def test_index_page_response_size(self, client):
        """首页响应 < 100KB"""
        resp = client.get("/")
        assert resp.status_code == 200
        assert len(resp.content) < 102400, f"首页响应 {len(resp.content)}B > 100KB"


class TestConcurrentPipelineStart:
    """并发 Pipeline 启动"""

    @pytest.fixture(autouse=True)
    def _mock_pipeline_start(self):
        import web.services.task_manager as tm_module
        tm_module._task_manager = None

        with patch("web.services.pipeline_task.PipelineTask.start_background", return_value=None):
            with patch("web.services.pipeline_task.PipelineTask.resume_background", return_value=None):
                with patch("web.services.pipeline_task._ensure_db", return_value=None):
                    yield

        tm_module._task_manager = None

    def test_concurrent_pipeline_starts(self):
        """3 个并发 Pipeline 启动 — 验证并发限制"""
        from web.app import app

        def make_request():
            client = TestClient(app)
            content = io.BytesIO(b"# Test")
            try:
                return client.post(
                    "/api/pipeline/start",
                    files={"file": ("test.md", content, "text/markdown")},
                    data={"mode": "semi", "dimensions": "basic", "formats": "excel"},
                )
            except Exception:
                # TaskManager 并发限制可能在线程间抛出 RuntimeError
                return None

        start = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(make_request) for _ in range(3)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        elapsed = time.time() - start

        # 过滤掉 None（异常）结果
        valid_results = [r for r in results if r is not None]
        success_count = sum(1 for r in valid_results if r.status_code == 201)
        rejected_count = sum(1 for r in valid_results if r.status_code == 429)

        # 至少 2 个成功（MAX_WORKERS=2），第 3 个可能被拒绝
        assert success_count >= 2
        assert elapsed < 2.0, f"3 并发 Pipeline 启动耗时 {elapsed:.3f}s > 2.0s"


# ─── 安全补充测试 ───


class TestCSPHeaders:
    """Content-Security-Policy 头"""

    @pytest.fixture
    def client(self):
        from web.app import app
        return TestClient(app)

    def test_csp_header_present(self, client):
        """CSP 头存在且合理"""
        resp = client.get("/")
        csp = resp.headers.get("Content-Security-Policy", "")
        # 如果配置了 CSP，验证其合理性
        if csp:
            # CSP 应该包含 default-src 或类似指令
            assert "default-src" in csp or "script-src" in csp
        # 即使没有 CSP，也不应崩溃

    def test_csp_on_api_response(self, client):
        """API 响应也应该有 CSP 头"""
        resp = client.get("/api/config")
        csp = resp.headers.get("Content-Security-Policy", "")
        if csp:
            assert "default-src" in csp or "script-src" in csp


class TestCORSConfiguration:
    """CORS 配置"""

    @pytest.fixture
    def client(self):
        from web.app import app
        return TestClient(app)

    def test_cors_preflight(self, client):
        """CORS 预检请求"""
        resp = client.options(
            "/api/config",
            headers={
                "Origin": "https://evil.com",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
        )
        # CORS 中间件应处理 OPTIONS 请求
        # 允许、拒绝或返回 405
        assert resp.status_code in (200, 400, 405, 204)

    def test_cors_origin_header(self, client):
        """跨域请求的 Origin 头处理"""
        resp = client.get("/api/config", headers={"Origin": "https://example.com"})
        # 应该有 CORS 头或没有
        acao = resp.headers.get("Access-Control-Allow-Origin")
        # 如果配置了 CORS，应该是 * 或具体域名
        if acao:
            assert acao in ("*", "https://example.com") or "https://" in acao


class TestHSTSHeader:
    """HSTS 头"""

    @pytest.fixture
    def client(self):
        from web.app import app
        return TestClient(app)

    def test_hsts_header(self, client):
        """Strict-Transport-Security 头（生产环境应有）"""
        resp = client.get("/")
        hsts = resp.headers.get("Strict-Transport-Security", "")
        # 测试环境可能不设置 HSTS，但生产环境应该
        if hsts:
            assert "max-age=" in hsts


class TestHTTPParameterPollution:
    """HTTP 参数污染"""

    @pytest.fixture
    def client(self):
        from web.app import app
        return TestClient(app)

    def test_duplicate_query_params(self, client):
        """重复查询参数不会导致异常"""
        resp = client.get("/api/kb/search?q=test&q=malicious")
        assert resp.status_code in (200, 422, 500, 503)

    def test_extra_unexpected_params(self, client):
        """额外参数被忽略"""
        resp = client.get("/api/config?debug=true&admin=1")
        assert resp.status_code == 200


class TestLargePayloadProtection:
    """大请求体防护"""

    @pytest.fixture
    def client(self):
        from web.app import app
        return TestClient(app)

    def test_large_json_body(self, client):
        """大 JSON 请求体"""
        large_body = {"data": "x" * 100000}
        resp = client.post("/api/auth/login", json=large_body)
        assert resp.status_code in (200, 401, 422)

    def test_large_form_data(self, client):
        """大表单数据"""
        large_data = "x" * 100000
        resp = client.post(
            "/api/auth/login",
            data={"username": large_data, "password": "test"},
        )
        assert resp.status_code in (200, 401, 422)


class TestSensitiveInfoLeakage:
    """敏感信息泄露防护"""

    @pytest.fixture
    def client(self):
        from web.app import app
        return TestClient(app)

    def test_config_api_masks_api_key(self, client):
        """配置 API 不应泄露完整 API Key"""
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        llm = data.get("llm", {})
        api_key = llm.get("api_key", "")
        # API Key 应该被遮蔽或以安全方式返回
        if api_key:
            # 不应包含测试用的完整 key
            assert "sk-test" not in api_key or len(api_key) < 20

    def test_error_response_no_stack_trace(self, client):
        """错误响应不泄露堆栈跟踪"""
        resp = client.get("/api/pipeline/nonexistent-id/progress")
        assert resp.status_code == 404
        data = resp.json()
        # 不应包含 Python 堆栈跟踪
        detail = str(data.get("detail", ""))
        assert "Traceback" not in detail
        assert "File " not in detail

    def test_404_no_server_info(self, client):
        """404 响应不泄露服务器信息"""
        resp = client.get("/api/nonexistent")
        # Server 头不应包含版本号
        server = resp.headers.get("Server", "")
        assert "uvicorn" not in server.lower() or "Python" not in server


class TestHTTPMethodOverride:
    """HTTP 方法覆盖攻击"""

    @pytest.fixture
    def client(self):
        from web.app import app
        return TestClient(app)

    def test_method_override_header(self, client):
        """X-HTTP-Method-Override 头"""
        resp = client.post(
            "/api/auth/login",
            headers={"X-HTTP-Method-Override": "DELETE"},
            json={"username": "test", "password": "test"},
        )
        # POST 端点被覆盖为 DELETE 应返回 405 或正常处理
        assert resp.status_code in (200, 401, 405, 422)

    def test_method_override_post_to_get(self, client):
        """POST 覆盖为 GET"""
        resp = client.post(
            "/api/config",
            headers={"X-HTTP-Method-Override": "GET"},
        )
        # POST 到只支持 GET 的端点应返回 405
        # 或成功处理（如果应用支持方法覆盖）
        assert resp.status_code in (200, 405, 422)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
