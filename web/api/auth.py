#!/usr/bin/env python3
"""
认证 API 路由

Endpoints:
  POST /login   — 用户名密码登录，返回 JWT
  GET  /me      — 查看当前登录用户信息（需 token）

login 端点本身不挂 verify_token（否则无法获取 token）。
本 router 在 app.py 中注册时带 /api/v1/auth 前缀。

安全措施：
  - 独立限流：5 次/分钟（比全局限流更严格，防暴力破解）
  - 失败锁定：连续失败 5 次 → 锁定 15 分钟
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from web.middleware.auth import create_token, verify_token
from web.middleware.login_lockout import (
    get_lock_remaining,
    is_locked,
    record_failure,
    record_success,
)
from web.services.user_service import authenticate

router = APIRouter(tags=["auth"])

# 登录端点独立限流（比全局 60/min 更严格）
LOGIN_RATE_LIMIT = "5/minute"

# 尝试导入 slowapi limiter（未安装时跳过限流装饰器）
try:
    from web.middleware.rate_limit import limiter

    _limiter_available = True
except ImportError:
    _limiter_available = False


class LoginRequest(BaseModel):
    """登录请求体。"""
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class LoginResponse(BaseModel):
    """登录成功响应。"""
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


if _limiter_available:
    # slowapi 装饰器必须叠加在 @router.post 之上（路由注册时即绑定），
    # 不能在函数定义后再用 limiter.limit()(login) 装饰 —
    # 否则 router 内部存的 endpoint 仍是原始函数，装饰器永远不执行。
    _login_decorator = limiter.limit(LOGIN_RATE_LIMIT)  # type: ignore[possibly-undefined]
else:
    # slowapi 未安装时用透传装饰器（no-op）
    def _login_decorator(func):
        return func


@router.post("/login", response_model=LoginResponse)
@_login_decorator
async def login(body: LoginRequest, request: Request):
    """用户名密码登录，签发 JWT。

    安全措施：
      1. 独立限流 5/min（slowapi 装饰器，防暴力破解）
      2. 失败锁定 — 连续失败 5 次的 IP+用户名 被锁定 15 分钟
      3. 认证失败统一返回 401（不区分用户名错误还是密码错误，防信息泄露）
      4. 登录成功清除失败计数
    """
    client_ip = request.client.host if request.client else "unknown"

    # 1. 检查是否被锁定
    if is_locked(client_ip, body.username):
        remaining = get_lock_remaining(client_ip, body.username)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"登录失败次数过多，请 {remaining} 秒后重试",
            headers={"Retry-After": str(remaining)},
        )

    # 2. 认证
    user = authenticate(body.username, body.password)
    if not user:
        record_failure(client_ip, body.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. 登录成功，清除失败计数
    record_success(client_ip, body.username)

    token = create_token(user.id, user.username, user.role)
    return LoginResponse(
        access_token=token,
        username=user.username,
        role=user.role,
    )


@router.get("/me")
async def me(payload: dict = Depends(verify_token)):
    """查看当前登录用户信息（验证 token 有效性）。"""
    return {
        "user_id": payload.get("sub"),
        "username": payload.get("username"),
        "role": payload.get("role"),
    }
