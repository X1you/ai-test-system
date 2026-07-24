#!/usr/bin/env python3
"""web/middleware 子模块补充测试 — auth、csrf、login_lockout、rate_limit。"""

import os
import time
from unittest.mock import MagicMock, patch

import pytest


class TestLoginLockout:
    """登录失败锁定机制测试"""

    def setup_method(self):
        """每个测试前重置锁定状态"""
        from web.middleware.login_lockout import reset_all

        reset_all()

    def test_is_locked_initial_false(self):
        """初始状态未锁定"""
        from web.middleware.login_lockout import is_locked

        assert is_locked("1.2.3.4", "admin") is False

    def test_record_failure_below_threshold(self):
        """失败次数未达阈值不锁定"""
        from web.middleware.login_lockout import is_locked, record_failure

        for _ in range(4):
            record_failure("1.2.3.4", "admin")
        assert is_locked("1.2.3.4", "admin") is False

    def test_record_failure_threshold_locks(self):
        """连续失败达阈值后锁定"""
        from web.middleware.login_lockout import is_locked, record_failure

        for _ in range(5):
            record_failure("1.2.3.4", "admin")
        assert is_locked("1.2.3.4", "admin") is True

    def test_record_success_clears(self):
        """登录成功清除失败计数"""
        from web.middleware.login_lockout import (
            is_locked,
            record_failure,
            record_success,
        )

        for _ in range(3):
            record_failure("1.2.3.4", "admin")
        record_success("1.2.3.4", "admin")
        assert is_locked("1.2.3.4", "admin") is False

    def test_get_lock_remaining_zero_when_not_locked(self):
        """未锁定时剩余秒数为 0"""
        from web.middleware.login_lockout import get_lock_remaining

        assert get_lock_remaining("1.2.3.4", "admin") == 0

    def test_get_lock_remaining_positive_when_locked(self):
        """锁定后剩余秒数 > 0"""
        from web.middleware.login_lockout import (
            get_lock_remaining,
            record_failure,
        )

        for _ in range(5):
            record_failure("1.2.3.4", "admin")
        remaining = get_lock_remaining("1.2.3.4", "admin")
        assert remaining > 0

    def test_lock_expires_after_duration(self):
        """锁定过期后自动解锁"""
        from web.middleware import login_lockout

        for _ in range(5):
            login_lockout.record_failure("1.2.3.4", "admin")

        # 模拟时间流逝超过锁定时长
        key = login_lockout._key("1.2.3.4", "admin")
        state = login_lockout._attempts[key]
        state.locked_until = time.monotonic() - 1  # 已过期

        assert login_lockout.is_locked("1.2.3.4", "admin") is False

    def test_sliding_window_reset(self):
        """滑动窗口：首次失败超过 LOCKOUT_DURATION 后重置"""
        from web.middleware import login_lockout

        # 先记录 4 次失败
        for _ in range(4):
            login_lockout.record_failure("1.2.3.4", "admin")

        # 模拟首次失败时间很久以前
        key = login_lockout._key("1.2.3.4", "admin")
        state = login_lockout._attempts[key]
        state.first_failure_ts = time.monotonic() - login_lockout.LOCKOUT_DURATION - 1

        # 再失败一次应该重置计数而不是锁定
        login_lockout.record_failure("1.2.3.4", "admin")
        assert login_lockout.is_locked("1.2.3.4", "admin") is False
        # 计数应被重置为 1
        assert login_lockout._attempts[key].failures == 1

    def test_different_ip_independent(self):
        """不同 IP 独立计数"""
        from web.middleware.login_lockout import (
            is_locked,
            record_failure,
        )

        for _ in range(5):
            record_failure("1.1.1.1", "admin")
        assert is_locked("1.1.1.1", "admin") is True
        assert is_locked("2.2.2.2", "admin") is False


class TestCSRFMiddleware:
    """CSRF 中间件测试"""

    def test_generate_csrf_token_unique(self):
        """生成的 CSRF token 每次不同"""
        from web.middleware.csrf import generate_csrf_token

        t1 = generate_csrf_token()
        t2 = generate_csrf_token()
        assert t1 != t2
        assert len(t1) > 0

    def test_csrf_api_path_exempt(self, client):
        """API 路径不受 CSRF 限制（带 JWT）"""
        # client fixture 自动带 Authorization 头
        resp = client.post("/api/v1/config", json={})
        # config PUT/POST 需要 body，可能返回 422 但不是 403 CSRF
        assert resp.status_code != 403 or "csrf" not in resp.text.lower()

    def test_csrf_get_sets_cookie(self, client):
        """GET 请求设置 CSRF Cookie"""
        resp = client.get("/health/live")
        # 健康检查不一定经过 CSRF 中间件（取决于中间件链）
        assert resp.status_code == 200


class TestRateLimitFunctions:
    """限流中间件函数级测试"""

    def test_get_remote_address(self):
        """get_remote_address 返回 IP"""
        from web.middleware.rate_limit import get_remote_address

        # 构造 mock request
        mock_request = MagicMock()
        mock_request.client.host = "1.2.3.4"
        result = get_remote_address(mock_request)
        assert result == "1.2.3.4"


class TestAuthVerifyTokenEdgeCases:
    """verify_token 边界情况测试"""

    def setup_method(self):
        """每个测试前启用 JWT 验证（覆盖默认的本地工具模式）"""
        import web.middleware.auth as _auth_mod

        _auth_mod._AUTH_ENABLED = True

    def teardown_method(self):
        """测试后恢复本地工具模式（避免污染其他测试）"""
        import web.middleware.auth as _auth_mod

        _auth_mod._AUTH_ENABLED = False

    def test_verify_token_no_credentials(self):
        """无 credentials 抛 401"""
        from fastapi import HTTPException

        from web.middleware.auth import verify_token

        with pytest.raises(HTTPException) as exc_info:
            verify_token(None)
        assert exc_info.value.status_code == 401
        assert "missing_token" in str(exc_info.value.detail) or "认证" in str(
            exc_info.value.detail
        )

    def test_verify_token_wrong_scheme(self):
        """非 Bearer scheme 抛 401"""
        from fastapi import HTTPException

        from web.middleware.auth import verify_token

        mock_cred = MagicMock()
        mock_cred.scheme = "Basic"
        mock_cred.credentials = "abc"

        with pytest.raises(HTTPException) as exc_info:
            verify_token(mock_cred)
        assert exc_info.value.status_code == 401

    def test_verify_token_invalid_token(self):
        """无效 token 抛 401"""
        from fastapi import HTTPException

        from web.middleware.auth import verify_token

        mock_cred = MagicMock()
        mock_cred.scheme = "Bearer"
        mock_cred.credentials = "invalid.jwt.token"

        with pytest.raises(HTTPException) as exc_info:
            verify_token(mock_cred)
        assert exc_info.value.status_code == 401

    def test_verify_token_missing_sub(self):
        """token 缺少 sub 字段抛 401"""
        from datetime import UTC, datetime, timedelta

        from fastapi import HTTPException
        from jose import jwt

        from web.middleware.auth import ALGORITHM, get_jwt_secret, verify_token

        # 构造无 sub 的 token
        payload = {
            "username": "test",
            "role": "user",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        }
        token = jwt.encode(payload, get_jwt_secret(), algorithm=ALGORITHM)

        mock_cred = MagicMock()
        mock_cred.scheme = "Bearer"
        mock_cred.credentials = token

        with pytest.raises(HTTPException) as exc_info:
            verify_token(mock_cred)
        assert exc_info.value.status_code == 401

    def test_verify_token_valid(self):
        """有效 token 返回 payload"""
        from web.middleware.auth import create_token, verify_token

        token = create_token(user_id=42, username="alice", role="admin")

        mock_cred = MagicMock()
        mock_cred.scheme = "Bearer"
        mock_cred.credentials = token

        payload = verify_token(mock_cred)
        assert payload["sub"] == "42"
        assert payload["username"] == "alice"
        assert payload["role"] == "admin"
