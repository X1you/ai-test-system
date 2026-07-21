#!/usr/bin/env python3
"""
JWT 认证中间件 — FastAPI Depends 模式

核心组件：
  - get_jwt_secret(): 安全加载 JWT_SECRET（弱密钥警告 + 启动校验钩子）
  - create_token(): 签发 JWT（含 sub/role/exp）
  - verify_token(): FastAPI 依赖，校验 Authorization: Bearer <token>

豁免由路由层控制（不在 verify_token 内做路径判断）：
  - /health, /api/v1/webhooks/* 不挂 verify_token 依赖
  - /api/v1/auth/login 本身不挂（否则无法获取 token）
"""

import os
import sys
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

# ─── JWT 配置常量 ───
ALGORITHM = "HS256"
DEFAULT_TOKEN_EXPIRE_MINUTES = 60 * 24  # 默认 24 小时

# 弱密钥检测：少于 32 字符的 secret 视为不安全
_MIN_SECRET_LEN = 32
_INSECURE_DEFAULT = "change-me-to-a-random-string-of-at-least-32-chars"

# HTTPBearer scheme —— 从 Authorization: Bearer <token> 提取 token
# auto_error=False 让 verify_token 自己控制 401 的错误格式
_bearer_scheme = HTTPBearer(auto_error=False)


def get_jwt_secret() -> str:
    """加载 JWT_SECRET 环境变量。

    优先级：JWT_SECRET 环境变量 > .env > 不安全默认值（仅非生产环境）。

    生产环境（AI_TEST_ENV=production）若未配置或为弱密钥，会触发 SystemExit，
    避免用默认密钥上生产。
    """
    secret = os.environ.get("JWT_SECRET", "").strip()
    is_production = os.environ.get("AI_TEST_ENV") == "production"

    if not secret:
        if is_production:
            sys.stderr.write(
                "❌ 生产环境必须配置 JWT_SECRET 环境变量（>=32 字符）。拒绝启动。\n"
            )
            raise SystemExit(1)
        # 非生产环境用不安全默认值，但打警告
        _warn_insecure_secret()
        return _INSECURE_DEFAULT

    # 弱密钥检测
    if len(secret) < _MIN_SECRET_LEN or secret == _INSECURE_DEFAULT:
        if is_production:
            sys.stderr.write(
                f"❌ 生产环境 JWT_SECRET 不安全（< {_MIN_SECRET_LEN} 字符或为默认值）。拒绝启动。\n"
            )
            raise SystemExit(1)
        _warn_insecure_secret()

    return secret


def _warn_insecure_secret():
    """非生产环境使用弱密钥时打警告。"""
    print(
        "⚠️  [SECURITY] JWT_SECRET 未配置或为弱密钥，使用不安全默认值。"
        "生产环境部署前必须设置 JWT_SECRET 环境变量（>=32 字符随机串）。",
        file=sys.stderr,
    )


def validate_secret_on_startup():
    """应用启动时校验密钥安全性（由 app.py startup 事件调用）。

    与 get_jwt_secret 分离：get_jwt_secret 每次请求都调用（只读检查），
    本函数只在启动时做一次完整校验并记录日志。
    """
    get_jwt_secret()  # 触发弱密钥警告/生产拒绝


def create_token(
    user_id: int,
    username: str,
    role: str = "user",
    expires_minutes: int | None = None,
) -> str:
    """签发 JWT。

    Claims:
        sub: 用户 ID（字符串）
        username: 用户名（便于日志/审计）
        role: 角色（user/admin）
        exp: 过期时间（UTC）
        iat: 签发时间（UTC）
    """
    expire_delta = timedelta(minutes=expires_minutes or DEFAULT_TOKEN_EXPIRE_MINUTES)
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": now + expire_delta,
        "iat": now,
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=ALGORITHM)


def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict:
    """FastAPI 依赖：校验 JWT 并返回 payload。

    用法（路由层）：
        @router.post("/start", dependencies=[Depends(verify_token)])

    失败场景：
        - 无 Authorization 头 → 401 missing_token
        - Bearer 格式错误 → 401 invalid_token_format
        - 签名错误/篡改 → 401 invalid_signature
        - 已过期 → 401 token_expired
        - 其他解析错误 → 401 invalid_token

    Returns:
        payload dict（含 sub/username/role/exp/iat）
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少认证 token，请先登录获取 JWT",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # HTTPBearer 已提取 scheme/token，校验 scheme 是否 Bearer
    if credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证方案必须是 Bearer",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 已过期，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效或签名错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 基础完整性校验：sub 必须存在
    if not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 缺少必要字段 sub",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


def require_admin(payload: dict = Depends(verify_token)) -> dict:
    """FastAPI 依赖：要求管理员角色（在 verify_token 基础上加角色校验）。

    用法：@router.delete("/users/{id}", dependencies=[Depends(require_admin)])
    """
    if payload.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return payload
