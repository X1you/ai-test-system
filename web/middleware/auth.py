#!/usr/bin/env python3
"""
JWT 认证中间件 — Phase 4

提供：
  - create_token()        生成 JWT Token
  - require_user()        验证 JWT，返回 payload（FastAPI Depends）
  - require_admin()       验证管理员权限（FastAPI Depends）

配置：
  - JWT_SECRET            环境变量，密钥（生产环境必须 >= 32 字符）
  - AI_TEST_ENV           环境变量，值为 "production" 时启动密钥校验
"""

import logging
import os
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

logger = logging.getLogger("ai-test-system")

# ─── 配置 ───

SECRET_KEY = os.environ.get("JWT_SECRET", "change-me-in-production")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24

security = HTTPBearer()


def _validate_secret():
    """启动时校验：生产环境 JWT_SECRET 长度必须 >= 32"""
    env = os.environ.get("AI_TEST_ENV", "")
    if env == "production" and len(SECRET_KEY) < 32:
        raise RuntimeError(
            "生产环境（AI_TEST_ENV=production）JWT_SECRET 长度必须 >= 32 字符"
        )
    # 非生产环境使用默认密钥时发出警告
    if SECRET_KEY == "change-me-in-production" and env != "production":
        logger.warning(
            "JWT_SECRET 未配置，正在使用不安全的默认值。"
            "请设置环境变量 JWT_SECRET 以确保安全。"
        )


def validate_secret_on_startup():
    """应用启动时显式调用，校验 JWT_SECRET 配置 + 算法白名单"""
    _validate_secret()
    # 安全护栏：本项目仅使用 HS256（HMAC），严禁引入 ECDSA/RSA 等非对称算法。
    # python-jose 的 ecdsa 传递依赖存在 Minerva 时序攻击漏洞
    # (CVE-2024-23342 / PYSEC-2026-1325)，上游 won't fix。
    # 此断言确保未来若误改 ALGORITHM 引入 ECDSA 会被立即拦截。
    assert ALGORITHM == "HS256", (
        f"安全策略违规：本项目仅允许 HS256 算法，当前 ALGORITHM={ALGORITHM!r}。"
        "引入 ECDSA 会触发 ecdsa 库的 Minerva 时序攻击漏洞 (CVE-2024-23342)。"
    )


# ─── 核心函数 ───

def create_token(user_id: int, username: str, role: str) -> str:
    """生成 JWT Token"""
    now = datetime.utcnow()
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": now + timedelta(hours=TOKEN_EXPIRE_HOURS),
        "iat": now,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


async def require_user(
    creds: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """验证 JWT，返回 payload；无效则抛 401"""
    try:
        payload = jwt.decode(creds.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_admin(user: dict = Depends(require_user)) -> dict:
    """验证管理员权限，非 admin 抛 403"""
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return user
