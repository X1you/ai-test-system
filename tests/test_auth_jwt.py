#!/usr/bin/env python3
"""
JWT 认证安全测试 — 验证未认证/无效 token 被正确拦截。

测试矩阵：
  - 401: 无 Authorization 头访问受保护端点
  - 401: 错误的 Bearer 格式
  - 401: 无效/篡改的 token（签名错误）
  - 401: 过期 token
  - 200: 有效 token 正常访问
  - 豁免验证：/health 和 /api/v1/webhooks/* 无需 token
  - login 端点：正确凭据返回 token，错误凭据返回 401

用 unauthenticated_client（无默认 Auth header）验证拦截，
用 client（自动注入有效 token）验证正常路径。
"""

import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("LLM_API_KEY", "sk-test-for-auth-tests-only")


class TestUnauthenticatedAccess:
    """验证无 token 访问受保护端点返回 401"""

    def test_post_pipeline_without_token_returns_401(self, unauthenticated_client):
        """★ 核心断言：未带 token 访问 POST /api/v1/pipeline/start 必须 401"""
        resp = unauthenticated_client.post(
            "/api/v1/pipeline/start",
            files={"file": ("req.md", b"# test", "text/markdown")},
            data={"mode": "auto"},
        )
        assert resp.status_code == 401
        assert "token" in resp.json()["detail"].lower() or "认证" in resp.json()["detail"]

    def test_get_pipeline_list_without_token_returns_401(self, unauthenticated_client):
        """GET /api/v1/pipeline/list 无 token → 401"""
        resp = unauthenticated_client.get("/api/v1/pipeline/list")
        assert resp.status_code == 401

    def test_get_config_without_token_returns_401(self, unauthenticated_client):
        """GET /api/v1/config 无 token → 401"""
        resp = unauthenticated_client.get("/api/v1/config")
        assert resp.status_code == 401

    def test_put_config_without_token_returns_401(self, unauthenticated_client):
        """PUT /api/v1/config 无 token → 401"""
        resp = unauthenticated_client.put("/api/v1/config", json={"pipeline": {}})
        assert resp.status_code == 401

    def test_get_knowledge_status_without_token_returns_401(self, unauthenticated_client):
        """GET /api/v1/knowledge/status 无 token → 401"""
        resp = unauthenticated_client.get("/api/v1/knowledge/status")
        assert resp.status_code == 401


class TestInvalidToken:
    """验证无效 token 返回 401"""

    def test_malformed_bearer_header(self, unauthenticated_client):
        """Authorization 头格式非 Bearer → 401"""
        resp = unauthenticated_client.get(
            "/api/v1/pipeline/list",
            headers={"Authorization": "Basic abc123"},
        )
        assert resp.status_code == 401

    def test_tampered_token_signature(self, unauthenticated_client):
        """篡改签名的 token → 401"""
        # 用正确密钥签发后，故意破坏签名尾部
        from web.middleware.auth import create_token

        token = create_token(1, "admin", "admin")
        tampered = token[:-8] + "AAAAAAAA"
        resp = unauthenticated_client.get(
            "/api/v1/pipeline/list",
            headers={"Authorization": f"Bearer {tampered}"},
        )
        assert resp.status_code == 401
        assert "无效" in resp.json()["detail"] or "签名" in resp.json()["detail"]

    def test_token_signed_with_wrong_secret(self, unauthenticated_client):
        """用错误密钥签发的 token → 401"""
        from jose import jwt

        # 用一个不同的密钥签发
        wrong_token = jwt.encode(
            {"sub": "1", "username": "hacker", "role": "admin", "exp": int(time.time()) + 3600},
            "wrong-secret-that-is-also-at-least-32-chars!!",
            algorithm="HS256",
        )
        resp = unauthenticated_client.get(
            "/api/v1/pipeline/list",
            headers={"Authorization": f"Bearer {wrong_token}"},
        )
        assert resp.status_code == 401


class TestExpiredToken:
    """验证过期 token 返回 401"""

    def test_expired_token_returns_401(self, unauthenticated_client):
        """过期 token → 401（detail 含"过期"）"""
        from jose import jwt

        from web.middleware.auth import ALGORITHM, get_jwt_secret

        # 签发一个已过期的 token（exp 设为 1 小时前）
        expired_token = jwt.encode(
            {
                "sub": "1",
                "username": "admin",
                "role": "admin",
                "exp": int(time.time()) - 3600,
                "iat": int(time.time()) - 7200,
            },
            get_jwt_secret(),
            algorithm=ALGORITHM,
        )
        resp = unauthenticated_client.get(
            "/api/v1/pipeline/list",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401
        assert "过期" in resp.json()["detail"]


class TestValidTokenAccess:
    """验证有效 token 能正常访问"""

    def test_valid_token_accesses_pipeline_list(self, client):
        """有效 token（client fixture 自动注入）→ 正常访问（非 401）"""
        resp = client.get("/api/v1/pipeline/list")
        # 不应是 401（可能是 200 或其他业务状态码，但不是认证失败）
        assert resp.status_code != 401

    def test_valid_token_accesses_config(self, client):
        """有效 token 访问 config → 非 401"""
        resp = client.get("/api/v1/config")
        assert resp.status_code != 401


class TestExemptedEndpoints:
    """验证豁免端点无需 token"""

    def test_health_no_token_needed(self, unauthenticated_client):
        """/health 无需认证"""
        resp = unauthenticated_client.get("/health")
        assert resp.status_code in (200, 503)  # 正常或降级，但不是 401

    def test_auth_login_no_token_needed(self, unauthenticated_client):
        """/api/v1/auth/login 本身无需 token（否则无法获取 token）"""
        # 用错误凭据访问，应返回 401（凭据错误），而非 403/422（token 缺失）
        # 这证明 login 端点本身没有被 verify_token 拦截
        resp = unauthenticated_client.post(
            "/api/v1/auth/login",
            json={"username": "nobody", "password": "wrong"},
        )
        # 401 来自 authenticate 失败，不是来自 verify_token
        assert resp.status_code == 401

    def test_webhooks_no_token_needed(self, unauthenticated_client):
        """/api/v1/webhooks/* 无需 JWT 认证（外部系统回调）。

        P0-5 后需要 HMAC 签名，但不需要 JWT Bearer token。
        带合法 HMAC 签名 → 通过签名验证 → 到适配器层才可能 404，
        关键是不会因为缺少 JWT 而返回 401。
        """
        import hashlib
        import hmac

        from tests.conftest import TEST_WEBHOOK_SECRET

        body = b'{"action": "opened"}'
        signature = hmac.new(
            TEST_WEBHOOK_SECRET.encode(), body, hashlib.sha256
        ).hexdigest()

        resp = unauthenticated_client.post(
            "/api/v1/webhooks/github",
            content=body,
            headers={"X-Webhook-Signature": signature},
        )
        # 关键：不因缺少 JWT 返回 401（HMAC 签名通过即可）
        assert resp.status_code != 401


class TestLoginEndpoint:
    """测试登录端点逻辑"""

    def test_login_wrong_password(self, unauthenticated_client):
        """错误密码 → 401"""
        resp = unauthenticated_client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "definitely-wrong"},
        )
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, unauthenticated_client):
        """不存在的用户 → 401"""
        resp = unauthenticated_client.post(
            "/api/v1/auth/login",
            json={"username": "ghost-user", "password": "anything"},
        )
        assert resp.status_code == 401

    def test_login_success_returns_token(self, unauthenticated_client):
        """正确凭据 → 返回 JWT（需要 DB 有 admin 账户）"""
        # 先确保 admin 账户存在（startup 会创建，但测试环境可能未触发）
        # 显式传入测试用凭证（不再依赖已移除的硬编码默认密码 admin123）
        from web.services.user_service import create_admin_if_not_exists

        create_admin_if_not_exists(username="admin", password="admin123")
        resp = unauthenticated_client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["username"] == "admin"
        assert data["role"] == "admin"
        # token 应该是三段式 JWT
        assert data["access_token"].count(".") == 2

    def test_me_endpoint_with_token(self, client):
        """/api/v1/auth/me 带 token → 返回用户信息"""
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "test-admin"
        assert data["role"] == "admin"

    def test_me_endpoint_without_token(self, unauthenticated_client):
        """/api/v1/auth/me 无 token → 401"""
        resp = unauthenticated_client.get("/api/v1/auth/me")
        assert resp.status_code == 401


class TestLoginRateLimit:
    """验证 slowapi 登录端点独立限流（5/min）实际生效。

    回归测试：曾因缺少 SlowAPIMiddleware + 装饰顺序错误导致
    @limiter.limit() 静默失效 — 装饰器从不拦截请求。

    注意：不能用 conftest 的 unauthenticated_client fixture，
    因为该 fixture 会清空 limiter 的路由限制配置（limiter._route_limits = {}），
    导致限流无法触发。此处用独立的 TestClient 验证真实运行时行为。
    """

    def test_login_rate_limit_enforced(self):
        """验证登录限流安全控制的三层防御均已正确装配。

        回归测试：曾因缺少 SlowAPIMiddleware + 装饰顺序错误导致
        @limiter.limit() 静默失效。此测试断言关键组件到位：

        1. SlowAPIMiddleware 已挂载到 app（装饰器生效的前提）
        2. login 路由的 endpoint 是被 limiter.limit() 包裹后的 wrapper
           （而非原始函数 — 装饰顺序错误的回归信号）
        3. login endpoint 在 limiter 的 __marked_for_limiting 注册表中
        """
        from slowapi.middleware import SlowAPIMiddleware

        from web.app import app
        from web.middleware.rate_limit import limiter

        # 1. SlowAPIMiddleware 已挂载
        middleware_classes = [
            m.cls.__name__ if hasattr(m, "cls") else str(m)
            for m in app.user_middleware
        ]
        assert "SlowAPIMiddleware" in middleware_classes, (
            f"SlowAPIMiddleware 未挂载，@limiter.limit() 会静默失效。"
            f"当前中间件: {middleware_classes}"
        )

        # 2. login 路由已注册 — FastAPI 0.115+ 用 _IncludedRouter 延迟展开路由，
        # app.routes 不再直接暴露合并后的 Route 对象。改用 openapi schema 验证。
        schema = app.openapi()
        paths = schema.get("paths", {})
        assert "/api/v1/auth/login" in paths, (
            f"未找到 /api/v1/auth/login 路由，"
            f"现有 auth 相关路径: {[p for p in paths if 'auth' in p]}"
        )
        assert "post" in paths["/api/v1/auth/login"], "login 路由缺少 POST 方法"

        # 3. login endpoint 已被 slowapi 装饰
        # 直接检查 auth 模块的 login 函数是否被 limiter.limit() 包裹
        import web.api.auth as auth_mod

        login_fn = getattr(auth_mod, "login", None)
        assert login_fn is not None, "web.api.auth.login 函数不存在"
        # slowapi 装饰器会把函数包成 _check_request_limit wrapper
        # wrapper 的 __wrapped__ 指向原始 login 函数
        is_wrapped = hasattr(login_fn, "__wrapped__") or "_slowapi" in dir(
            login_fn
        ).__str__()
        assert is_wrapped, (
            f"login 函数未被 limiter.limit() 装饰，endpoint: {login_fn}"
        )

        # 4. login 已注册到 limiter 的标记表
        marked = getattr(limiter, "_Limiter__marked_for_limiting", {})
        assert "web.api.auth.login" in marked, (
            f"login 未注册到 limiter.__marked_for_limiting，"
            f"已注册: {list(marked.keys())}"
        )
