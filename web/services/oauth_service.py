#!/usr/bin/env python3
"""
OAuth2 认证服务 — 支持 GitHub / Google / 企业 SSO

提供：
  - OAuth2 授权码流程
  - 访问令牌刷新
  - 令牌撤销
  - 企业 SSO（SAML/OIDC）支持
"""

import logging
import os
import secrets
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import requests
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, OAuth2PasswordBearer

logger = logging.getLogger("ai-test-system.auth")

# ─── 配置 ───

OAUTH2_PROVIDERS = {
    "github": {
        "auth_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "user_info_url": "https://api.github.com/user",
        "scope": "read:user user:email",
    },
    "google": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "user_info_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "scope": "openid email profile",
    },
}


# ─── 令牌存储 ───

@dataclass
class OAuthToken:
    """OAuth2 令牌"""
    token_id: str
    provider: str
    access_token: str
    refresh_token: str = ""
    expires_at: int = 0
    user_id: str = ""
    scopes: list[str] = None
    created_at: str = ""

    def __post_init__(self):
        if self.scopes is None:
            self.scopes = []
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def is_expired(self) -> bool:
        """检查令牌是否过期"""
        return time.time() > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（隐藏敏感信息）"""
        return {
            "token_id": self.token_id,
            "provider": self.provider,
            "expires_at": datetime.fromtimestamp(self.expires_at).isoformat(),
            "user_id": self.user_id,
            "scopes": self.scopes,
            "created_at": self.created_at,
        }


class TokenStore:
    """令牌存储（内存 + 可持久化）"""

    _lock = threading.RLock()
    _tokens: dict[str, OAuthToken] = {}
    _user_tokens: dict[str, list[str]] = {}  # user_id -> [token_id, ...]

    @classmethod
    def store(cls, token: OAuthToken):
        """存储令牌"""
        with cls._lock:
            cls._tokens[token.token_id] = token

            if token.user_id:
                if token.user_id not in cls._user_tokens:
                    cls._user_tokens[token.user_id] = []
                cls._user_tokens[token.user_id].append(token.token_id)

            logger.info(f"Token stored: {token.token_id} (provider={token.provider})")

    @classmethod
    def get(cls, token_id: str) -> OAuthToken | None:
        """获取令牌"""
        with cls._lock:
            return cls._tokens.get(token_id)

    @classmethod
    def revoke(cls, token_id: str) -> bool:
        """撤销令牌"""
        with cls._lock:
            if token_id in cls._tokens:
                token = cls._tokens[token_id]

                # 从用户令牌列表中移除
                if token.user_id and token.user_id in cls._user_tokens:
                    cls._user_tokens[token.user_id] = [
                        tid for tid in cls._user_tokens[token.user_id] if tid != token_id
                    ]

                del cls._tokens[token_id]
                logger.info(f"Token revoked: {token_id}")
                return True
            return False

    @classmethod
    def revoke_all_for_user(cls, user_id: str) -> int:
        """撤销用户的所有令牌"""
        with cls._lock:
            if user_id not in cls._user_tokens:
                return 0

            count = 0
            for token_id in list(cls._user_tokens[user_id]):
                if cls.revoke(token_id):
                    count += 1

            del cls._user_tokens[user_id]
            logger.info(f"Revoked {count} tokens for user: {user_id}")
            return count

    @classmethod
    def list_user_tokens(cls, user_id: str) -> list[dict[str, Any]]:
        """列出用户的所有令牌"""
        with cls._lock:
            if user_id not in cls._user_tokens:
                return []

            return [
                cls._tokens[tid].to_dict()
                for tid in cls._user_tokens[user_id]
                if tid in cls._tokens
            ]


# ─── OAuth2 流程 ───

class OAuth2Service:
    """OAuth2 认证服务"""

    @staticmethod
    def get_authorization_url(provider: str, redirect_uri: str,
                             state: str = None) -> str:
        """获取授权 URL"""
        if provider not in OAUTH2_PROVIDERS:
            raise ValueError(f"不支持的 provider: {provider}")

        config = OAUTH2_PROVIDERS[provider]
        client_id = os.environ.get(f"{provider.upper()}_CLIENT_ID")
        if not client_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"{provider} 未配置 CLIENT_ID"
            )

        if state is None:
            state = secrets.token_urlsafe(16)

        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": config["scope"],
            "state": state,
            "response_type": "code",
        }

        from urllib.parse import urlencode
        return f"{config['auth_url']}?{urlencode(params)}"

    @staticmethod
    def exchange_code_for_token(provider: str, code: str,
                               redirect_uri: str) -> OAuthToken:
        """用授权码换取访问令牌"""
        if provider not in OAUTH2_PROVIDERS:
            raise ValueError(f"不支持的 provider: {provider}")

        config = OAUTH2_PROVIDERS[provider]
        client_id = os.environ.get(f"{provider.upper()}_CLIENT_ID")
        client_secret = os.environ.get(f"{provider.upper()}_CLIENT_SECRET")

        if not client_id or not client_secret:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"{provider} 未配置 CLIENT_ID 或 CLIENT_SECRET"
            )

        # 调用令牌端点
        response = requests.post(
            config["token_url"],
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
        )

        if response.status_code != 200:
            logger.error(f"Token exchange failed: {response.text}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="授权码无效或已过期"
            )

        token_data = response.json()

        # 获取用户信息
        user_info = OAuth2Service._get_user_info(provider, token_data["access_token"])

        # 创建令牌对象
        expires_in = token_data.get("expires_in", 3600)
        token = OAuthToken(
            token_id=uuid.uuid4().hex[:16],
            provider=provider,
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token", ""),
            expires_at=int(time.time()) + expires_in,
            user_id=str(user_info.get("id", "")),
            scopes=token_data.get("scope", "").split(),
        )

        TokenStore.store(token)
        return token

    @staticmethod
    def _get_user_info(provider: str, access_token: str) -> dict[str, Any]:
        """获取用户信息"""
        config = OAUTH2_PROVIDERS[provider]
        response = requests.get(
            config["user_info_url"],
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code == 200:
            return response.json()
        return {}

    @staticmethod
    def refresh_token(token_id: str) -> OAuthToken:
        """刷新访问令牌"""
        token = TokenStore.get(token_id)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="令牌不存在"
            )

        if not token.refresh_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无刷新令牌"
            )

        config = OAUTH2_PROVIDERS[token.provider]
        client_id = os.environ.get(f"{token.provider.upper()}_CLIENT_ID")
        client_secret = os.environ.get(f"{token.provider.upper()}_CLIENT_SECRET")

        response = requests.post(
            config["token_url"],
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": token.refresh_token,
                "grant_type": "refresh_token",
            },
            headers={"Accept": "application/json"},
        )

        if response.status_code != 200:
            # 刷新失败，撤销令牌
            TokenStore.revoke(token_id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="刷新令牌无效，请重新授权"
            )

        token_data = response.json()

        # 更新令牌
        expires_in = token_data.get("expires_in", 3600)
        token.access_token = token_data["access_token"]
        token.expires_at = int(time.time()) + expires_in

        TokenStore.store(token)
        return token


# ─── API Key 管理 ───

class APIKeyManager:
    """API Key 管理器"""

    _lock = threading.RLock()
    _keys: dict[str, dict[str, Any]] = {}
    _user_keys: dict[str, list[str]] = {}

    @staticmethod
    def generate(user_id: str, name: str = "",
                 expires_in: int | None = None) -> str:
        """生成 API Key"""
        key = f"atk_{secrets.token_urlsafe(32)}"

        with APIKeyManager._lock:
            expires_at = None
            if expires_in:
                expires_at = (datetime.now() + timedelta(seconds=expires_in)).isoformat()

            APIKeyManager._keys[key] = {
                "key_id": uuid.uuid4().hex[:16],
                "user_id": user_id,
                "name": name,
                "created_at": datetime.now().isoformat(),
                "expires_at": expires_at,
                "last_used": None,
            }

            if user_id not in APIKeyManager._user_keys:
                APIKeyManager._user_keys[user_id] = []
            APIKeyManager._user_keys[user_id].append(key)

            logger.info(f"API key generated: {APIKeyManager._keys[key]['key_id']}")

        return key

    @staticmethod
    def validate(key: str) -> dict[str, Any] | None:
        """验证 API Key"""
        with APIKeyManager._lock:
            if key not in APIKeyManager._keys:
                return None

            key_data = APIKeyManager._keys[key]

            # 检查过期
            if key_data["expires_at"]:
                expires = datetime.fromisoformat(key_data["expires_at"])
                if datetime.now() > expires:
                    APIKeyManager.revoke(key)
                    return None

            # 更新最后使用时间
            key_data["last_used"] = datetime.now().isoformat()

            return key_data

    @staticmethod
    def revoke(key: str) -> bool:
        """撤销 API Key"""
        with APIKeyManager._lock:
            if key in APIKeyManager._keys:
                user_id = APIKeyManager._keys[key]["user_id"]

                if user_id in APIKeyManager._user_keys:
                    APIKeyManager._user_keys[user_id] = [
                        k for k in APIKeyManager._user_keys[user_id] if k != key
                    ]

                del APIKeyManager._keys[key]
                logger.info("API key revoked")
                return True
            return False

    @staticmethod
    def list_user_keys(user_id: str) -> list[dict[str, Any]]:
        """列出用户的所有 API Key"""
        with APIKeyManager._lock:
            if user_id not in APIKeyManager._user_keys:
                return []

            return [
                {**APIKeyManager._keys[k], "key": k}
                for k in APIKeyManager._user_keys[user_id]
                if k in APIKeyManager._keys
            ]


# ─── FastAPI 依赖 ───

# HTTP Basic Auth
security_basic = HTTPBasic()

# OAuth2 Password Bearer（用于 JWT）
security_bearer = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user_from_basic(
    credentials: tuple = Depends(security_basic)
) -> str:
    """从 HTTP Basic Auth 获取用户"""
    username, password = credentials
    # TODO: 验证用户名密码（从数据库或 LDAP）
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的凭据",
            headers={"WWW-Authenticate": "Basic"},
        )
    return username


async def get_current_user_from_api_key(
    api_key: str = Depends(security_bearer)
) -> str:
    """从 API Key 获取用户"""
    key_data = APIKeyManager.validate(api_key)
    if not key_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的 API Key",
        )
    return key_data["user_id"]


async def get_current_user_from_oauth(
    token: str = Depends(security_bearer)
) -> str:
    """从 OAuth2 令牌获取用户"""
    # 假设 token 是 token_id（实际应从 JWT header 解析）
    oauth_token = TokenStore.get(token)
    if not oauth_token or oauth_token.is_expired():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌无效或已过期",
        )
    return oauth_token.user_id


# ─── 企业 SSO（SAML/OIDC）占位 ───

class SSOProvider:
    """企业 SSO 提供商（占位实现）"""

    @staticmethod
    def handle_saml_response(saml_response: str) -> dict[str, Any]:
        """处理 SAML 响应（占位）"""
        # TODO: 解析 SAML 断言，提取用户信息
        logger.warning("SAML SSO 未实现")
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="SAML SSO 尚未实现"
        )

    @staticmethod
    def handle_oidc_callback(code: str, redirect_uri: str) -> OAuthToken:
        """处理 OIDC 回调（占位）"""
        # TODO: 使用 OAuth2Service.exchange_code_for_token，但使用企业配置
        logger.warning("企业 OIDC SSO 未实现")
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="企业 OIDC SSO 尚未实现"
        )
