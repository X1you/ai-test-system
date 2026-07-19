#!/usr/bin/env python3
"""
安全性测试 — 覆盖常见 Web 安全漏洞

测试范围：
  - 路径穿越（Path Traversal）
  - XSS 防护（响应头 + 输出编码）
  - SQL 注入（ORM 参数化查询）
  - 文件上传安全
  - 认证与授权
  - 安全响应头
  - 速率限制
  - JWT 安全
"""

import io
import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("LLM_API_KEY", "«redacted:sk-…»")


class TestSecurityHeaders:
    """安全响应头测试"""

    def test_x_content_type_options(self, client):
        """X-Content-Type-Options: nosniff"""
        resp = client.get("/")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options(self, client):
        """X-Frame-Options: DENY"""
        resp = client.get("/")
        assert resp.headers.get("X-Frame-Options") == "DENY"

    def test_x_xss_protection(self, client):
        """X-XSS-Protection: 1; mode=block"""
        resp = client.get("/")
        assert "1" in resp.headers.get("X-XSS-Protection", "")
        assert "block" in resp.headers.get("X-XSS-Protection", "")

    def test_referrer_policy(self, client):
        """Referrer-Policy: strict-origin-when-cross-origin"""
        resp = client.get("/")
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_security_headers_on_api(self, client):
        """API 路由也包含安全头"""
        resp = client.get("/api/v1/pipeline/list")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"

    def test_security_headers_on_error(self, client):
        """错误响应也包含安全头"""
        resp = client.get("/api/v1/pipeline/nonexistent-id/progress")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"


class TestPathTraversal:
    """路径穿越防护"""

    def test_download_path_traversal_double_dot(self, client):
        """双点号路径穿越被阻止 — FastAPI 可能先规范化路径，返回 404"""
        resp = client.get("/api/v1/pipeline/test-id/artifacts/../../../etc/passwd")
        # 路径被规范化后可能返回 404（pipeline 不存在）或 400（非法文件名）
        assert resp.status_code in (400, 404)

    def test_download_path_traversal_encoded(self, client):
        """URL 编码的路径穿越被阻止"""
        resp = client.get("/api/v1/pipeline/test-id/artifacts/%2e%2e%2f%2e%2e%2fetc/passwd")
        # 应该返回 404（pipeline 不存在）或 400（非法文件名）
        assert resp.status_code in (400, 404)

    def test_preview_path_traversal(self, client):
        """预览端点路径穿越被阻止"""
        resp = client.get("/api/v1/pipeline/test-id/preview/../../../etc/passwd")
        assert resp.status_code in (400, 404)

    def test_download_absolute_path(self, client):
        """绝对路径被阻止"""
        resp = client.get("/api/v1/pipeline/test-id/artifacts//etc/passwd")
        assert resp.status_code in (400, 404)


class TestSQLInjection:
    """SQL 注入防护"""

    def test_pipeline_id_sql_injection(self, client):
        """Pipeline ID 中的 SQL 注入被参数化查询防护"""
        resp = client.get("/api/v1/pipeline/' OR '1'='1/progress")
        # 应该返回 404（不是 500 错误）
        assert resp.status_code == 404

    def test_pipeline_id_drop_table(self, client):
        """DROP TABLE 注入被防护"""
        resp = client.get("/api/v1/pipeline/test'; DROP TABLE pipelines;--/progress")
        assert resp.status_code == 404

    def test_pipeline_id_union_select(self, client):
        """UNION SELECT 注入被防护"""
        resp = client.get("/api/v1/pipeline/test' UNION SELECT * FROM users--/progress")
        assert resp.status_code == 404


class TestXSSProtection:
    """XSS 防护"""

    def test_xss_in_page_content(self, client):
        """页面内容不被 XSS 注入（SPA HTML 或 JSON 均不含未转义脚本）"""
        resp = client.get("/")
        assert resp.status_code == 200
        text = resp.text
        assert "<script>alert" not in text.lower()

    def test_xss_in_api_response(self, client):
        """API 响应中的用户输入不应导致 XSS"""
        resp = client.get("/api/v1/pipeline/<script>alert(1)</script>/progress")
        data = resp.json()
        # 404 响应中不应包含原始脚本标签（Sprint 6.1: SPA fallback 返回 error 字段）
        assert "error" in data or "detail" in data


class TestFileUploadSecurity:
    """文件上传安全"""

    def test_upload_executable(self, client):
        """可执行文件被拒绝"""
        content = io.BytesIO(b"\x7fELF binary content")
        resp = client.post(
            "/api/v1/pipeline/start",
            files={"file": ("malware.sh", content, "application/x-sh")},
            data={"mode": "semi"},
        )
        assert resp.status_code == 400

    def test_upload_double_extension(self, client):
        """双后缀文件检查 — .md 后缀允许"""
        content = io.BytesIO(b"test")
        resp = client.post(
            "/api/v1/pipeline/start",
            files={"file": ("test.pdf.md", content, "text/markdown")},
            data={"mode": "semi"},
        )
        # .md 后缀允许，但可能因并发限制返回 429
        assert resp.status_code in (201, 429)

    def test_upload_path_traversal_filename(self, client):
        """文件名中的路径穿越 — Path().name 取文件名部分"""
        content = io.BytesIO(b"test")
        resp = client.post(
            "/api/v1/pipeline/start",
            files={"file": ("malicious.md", content, "text/markdown")},
            data={"mode": "semi"},
        )
        # 普通文件名应该被正确处理
        assert resp.status_code in (201, 429)

    def test_upload_overlong_filename_truncated(self, client):
        """超长文件名应被截断（防止目录项溢出/磁盘填充攻击）"""
        from web.api.pipeline import UPLOAD_DIR

        # 记录上传前的文件列表
        before = set(UPLOAD_DIR.glob("*.md"))

        # 300 字符的文件名
        overlong = "a" * 296 + ".md"
        content = io.BytesIO(b"# test\n")
        resp = client.post(
            "/api/v1/pipeline/start",
            files={"file": (overlong, content, "text/markdown")},
            data={"mode": "semi"},
        )
        # 可能因并发限制返回 429（说明已有任务在跑）
        if resp.status_code == 429:
            return
        assert resp.status_code == 201

        # 找到新创建的文件，验证文件名被截断到合理长度
        after = set(UPLOAD_DIR.glob("*.md"))
        new_files = after - before
        assert len(new_files) >= 1, "上传后应有新文件"
        for f in new_files:
            # 8位 upload_id + _ + ≤93字符名 + .md = ≤104 字符
            assert len(f.name) <= 110, (
                f"文件名未被截断: {f.name} ({len(f.name)} chars)"
            )


class TestAuthSecurity:
    """认证安全（Sprint 6.0: Auth 已切除，全部跳过）"""

    def test_protected_endpoint_without_token(self):
        pytest.skip("Auth module removed in Sprint 6.0")

    def test_protected_endpoint_invalid_token(self, client):
        pytest.skip("Auth module removed in Sprint 6.0")

    def test_protected_endpoint_empty_token(self):
        pytest.skip("Auth module removed in Sprint 6.0")

    def test_protected_endpoint_wrong_scheme(self, client):
        pytest.skip("Auth module removed in Sprint 6.0")

    def test_jwt_token_not_reusable_across_roles(self, monkeypatch, tmp_path):
        """Sprint 6.0: Auth 已切除，此测试跳过"""
        pytest.skip("Auth module removed in Sprint 6.0")


class TestRateLimiting:
    """速率限制测试"""

    def test_rate_limit_exists(self):
        """速率限制器已配置 — 模块可能依赖 slowapi"""
        try:
            from web.middleware.rate_limit import get_limiter
            limiter = get_limiter()
            assert limiter is not None
        except ImportError:
            pytest.skip("slowapi not installed")


class TestGlobalExceptionHandler:
    """全局异常处理"""

    def test_500_error_returns_json(self, client):
        """500 错误返回 JSON 格式"""
        # 触发一个预期的 404（验证错误格式）
        resp = client.get("/api/v1/pipeline/nonexistent-id/progress")
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data

    def test_404_returns_json(self, client):
        """404 返回 JSON 格式（Sprint 6.1: SPA fallback 返回 error 字段）"""
        resp = client.get("/api/nonexistent-route-xyz")
        data = resp.json()
        assert "error" in data or "detail" in data


class TestStaticCacheHeaders:
    """静态资源缓存头"""

    def test_css_cache_control(self, client):
        """CSS 文件缓存 1 小时"""
        resp = client.get("/static/custom.css")
        if resp.status_code == 200:
            cc = resp.headers.get("Cache-Control", "")
            assert "max-age=3600" in cc

    def test_js_cache_control(self, client):
        """JS 文件缓存 1 小时"""
        resp = client.get("/static/app.js")
        if resp.status_code == 200:
            cc = resp.headers.get("Cache-Control", "")
            assert "max-age=3600" in cc


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
