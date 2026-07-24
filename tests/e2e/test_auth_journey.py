#!/usr/bin/env python3
"""认证旅程 e2e — login → me → 失效 token → 锁定全链路。

覆盖：
  - 正确凭据登录 → 200 + JWT
  - 错误凭据 → 401（不区分用户名/密码错误）
  - /me 用 token 验证身份
  - 篡改 token → 401
  - 连续失败 5 次 → 锁定 429
  - 豁免端点（/health、/webhooks）无需 token
"""

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestAuthJourney:
    """认证全链路旅程测试。"""

    def test_login_success_returns_jwt(self, unauthenticated_client, ensure_admin_user):
        """正确凭据 → 200 + access_token + username + role。"""
        username, password = ensure_admin_user
        resp = unauthenticated_client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["access_token"]
        assert data["token_type"] == "bearer"
        assert data["username"] == username
        assert data["role"] == "admin"

    def test_login_wrong_password_returns_401(self, unauthenticated_client, ensure_admin_user):
        """错误密码 → 401，统一文案（防信息泄露）。"""
        username, _ = ensure_admin_user
        resp = unauthenticated_client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "definitely-wrong"},
        )
        assert resp.status_code == 401
        assert "用户名或密码错误" in resp.json()["detail"]

    def test_login_nonexistent_user_returns_401(self, unauthenticated_client):
        """不存在的用户 → 401（与密码错误同文案，防用户枚举）。"""
        resp = unauthenticated_client.post(
            "/api/v1/auth/login",
            json={"username": "ghost-user", "password": "whatever"},
        )
        assert resp.status_code == 401
        assert "用户名或密码错误" in resp.json()["detail"]

    def test_me_with_valid_token(self, client):
        """GET /me 用有效 token → 返回当前用户信息。"""
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "username" in data
        assert "role" in data

    def test_me_without_token_returns_401(self, unauthenticated_client):
        """GET /me 无 token → 401。"""
        resp = unauthenticated_client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_tampered_token_rejected(self, unauthenticated_client):
        """篡改签名的 token → 401。"""
        from web.middleware.auth import create_token

        token = create_token(1, "admin", "admin")
        tampered = token[:-8] + "AAAAAAAA"
        resp = unauthenticated_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {tampered}"},
        )
        assert resp.status_code == 401

    def test_login_then_use_token_full_flow(self, unauthenticated_client, ensure_admin_user):
        """★ 完整旅程：登录拿 token → 用 token 访问受保护端点。"""
        username, password = ensure_admin_user
        # 1. 登录
        resp = unauthenticated_client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        assert resp.status_code == 200
        token = resp.json()["access_token"]

        # 2. 用 token 访问受保护端点（/config）
        resp2 = unauthenticated_client.get(
            "/api/v1/config",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp2.status_code == 200

        # 3. 用 token 访问 /me
        resp3 = unauthenticated_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp3.status_code == 200
        assert resp3.json()["username"] == username

    def test_repeated_failures_trigger_lockout(self, unauthenticated_client, ensure_admin_user):
        """连续 MAX_FAILURES 次失败 → 锁定，后续请求返回 429。

        锁定逻辑：is_locked 在请求开始时检查（failures >= MAX_FAILURES），
        record_failure 在认证失败后累加。因此前 MAX_FAILURES 次请求时
        is_locked 仍为 False（返回 401），第 MAX_FAILURES+1 次才命中锁定（429）。
        """
        from web.middleware.login_lockout import reset_all, MAX_FAILURES

        reset_all()
        username, _ = ensure_admin_user
        # 前 MAX_FAILURES 次返回 401（每次 is_locked 检查时未达阈值）
        for i in range(MAX_FAILURES):
            resp = unauthenticated_client.post(
                "/api/v1/auth/login",
                json={"username": username, "password": "wrong"},
            )
            assert resp.status_code == 401, f"第 {i + 1} 次应返回 401"

        # 第 MAX_FAILURES+1 次命中锁定 → 429
        resp = unauthenticated_client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "wrong"},
        )
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
        reset_all()  # 清理，避免影响其他测试

    def test_health_endpoints_no_auth_required(self, unauthenticated_client):
        """健康检查端点豁免认证。"""
        for path in ["/health/live", "/health/ready", "/health"]:
            resp = unauthenticated_client.get(path)
            # 200 或 503（取决于依赖状态），但绝不是 401
            assert resp.status_code != 401, f"{path} 不应要求认证"

    def test_login_validation_rejects_empty_fields(self, unauthenticated_client):
        """空用户名/密码 → 422（Pydantic 校验）。"""
        resp = unauthenticated_client.post(
            "/api/v1/auth/login",
            json={"username": "", "password": ""},
        )
        assert resp.status_code == 422
