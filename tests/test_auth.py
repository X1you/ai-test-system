#!/usr/bin/env python3
"""
Phase 4 认证与安全测试

验证：JWT Token 生成/验证 → 密码哈希 → 用户认证 → API 路由
"""

import sys
from pathlib import Path

import pytest

# 设置项目根路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    """每个测试使用独立的临时数据库"""
    db_path = tmp_path / "test_auth.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))

    from db.session import init_db, reset_engine
    reset_engine()
    init_db()

    yield

    reset_engine()


class TestPasswordHashing:
    """密码哈希测试"""

    def test_hash_password(self):
        """密码可哈希"""
        from web.services.user_service import hash_password
        h = hash_password("mypassword123")
        assert h != "mypassword123"
        assert len(h) > 0

    def test_hash_password_unique(self):
        """相同密码每次哈希结果不同（salt 随机）"""
        from web.services.user_service import hash_password
        h1 = hash_password("samepass")
        h2 = hash_password("samepass")
        assert h1 != h2

    def test_verify_password_correct(self):
        """正确密码验证通过"""
        from web.services.user_service import hash_password, verify_password
        h = hash_password("correctpass")
        assert verify_password("correctpass", h) is True

    def test_verify_password_wrong(self):
        """错误密码验证失败"""
        from web.services.user_service import hash_password, verify_password
        h = hash_password("correctpass")
        assert verify_password("wrongpass", h) is False


class TestJWTToken:
    """JWT Token 测试"""

    def test_create_token(self):
        """Token 可生成"""
        from web.middleware.auth import create_token
        token = create_token(1, "admin", "admin")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_token(self):
        """Token 可解码且 payload 正确"""
        from jose import jwt

        from web.middleware.auth import ALGORITHM, SECRET_KEY, create_token
        token = create_token(42, "testuser", "user")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "42"
        assert payload["username"] == "testuser"
        assert payload["role"] == "user"

    def test_token_has_expiry(self):
        """Token 包含过期时间"""
        from jose import jwt

        from web.middleware.auth import ALGORITHM, SECRET_KEY, create_token
        token = create_token(1, "admin", "admin")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in payload
        assert "iat" in payload


class TestUserService:
    """用户服务测试"""

    def test_authenticate_success(self):
        """用户认证成功"""
        from db.repository import get_repository
        from web.services.user_service import (
            authenticate,
            hash_password,
        )
        repo = get_repository()
        repo.create_user("testuser", hash_password("pass123"), "user")

        user = authenticate("testuser", "pass123")
        assert user is not None
        assert user.username == "testuser"

    def test_authenticate_wrong_password(self):
        """密码错误返回 None"""
        from db.repository import get_repository
        from web.services.user_service import (
            authenticate,
            hash_password,
        )
        repo = get_repository()
        repo.create_user("testuser", hash_password("correct"), "user")

        user = authenticate("testuser", "wrong")
        assert user is None

    def test_authenticate_nonexistent_user(self):
        """用户不存在返回 None"""
        from web.services.user_service import authenticate
        user = authenticate("ghost", "anything")
        assert user is None

    def test_create_admin_if_not_exists(self):
        """首次创建管理员"""
        from web.services.user_service import create_admin_if_not_exists
        created = create_admin_if_not_exists("admin", "admin123")
        assert created is True

        # 第二次不创建
        created_again = create_admin_if_not_exists("admin", "newpass")
        assert created_again is False

    def test_generate_api_key(self):
        """API Key 生成"""
        from web.services.user_service import generate_api_key
        key1 = generate_api_key()
        key2 = generate_api_key()
        assert len(key1) == 32  # token_hex(16) = 32 chars
        assert key1 != key2  # 每次不同


class TestAuthAPI:
    """认证 API 路由测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from fastapi.testclient import TestClient

        from web.app import app
        return TestClient(app)

    def test_login_success(self, client):
        """登录成功返回 Token"""
        from db.repository import get_repository
        from web.services.user_service import hash_password
        repo = get_repository()
        repo.create_user("apiuser", hash_password("pass123"), "user")

        resp = client.post("/api/auth/login", json={
            "username": "apiuser",
            "password": "pass123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["username"] == "apiuser"
        assert data["role"] == "user"

    def test_login_wrong_password(self, client):
        """密码错误返回 401"""
        from db.repository import get_repository
        from web.services.user_service import hash_password
        repo = get_repository()
        repo.create_user("apiuser", hash_password("correct"), "user")

        resp = client.post("/api/auth/login", json={
            "username": "apiuser",
            "password": "wrong",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        """用户不存在返回 401"""
        resp = client.post("/api/auth/login", json={
            "username": "nobody",
            "password": "pass",
        })
        assert resp.status_code == 401

    def test_logout(self, client):
        """登出返回成功"""
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 200

    def test_me_without_token(self, client):
        """无 Token 访问 /me 返回 401"""
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_me_with_valid_token(self, client):
        """有效 Token 访问 /me 返回用户信息"""
        from db.repository import get_repository
        from web.services.user_service import hash_password
        repo = get_repository()
        repo.create_user("meuser", hash_password("pass123"), "user")

        # 登录获取 token
        resp = client.post("/api/auth/login", json={
            "username": "meuser",
            "password": "pass123",
        })
        token = resp.json()["access_token"]

        # 用 token 访问 /me
        resp = client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {token}",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "meuser"
        assert data["role"] == "user"

    def test_login_page(self, client):
        """登录页可访问"""
        resp = client.get("/login")
        assert resp.status_code == 200
        assert "登录" in resp.text or "login" in resp.text.lower()
