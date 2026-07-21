#!/usr/bin/env python3
"""
认证 API 路由

Endpoints:
  POST /login   — 用户名密码登录，返回 JWT
  GET  /me      — 查看当前登录用户信息（需 token）

login 端点本身不挂 verify_token（否则无法获取 token）。
本 router 在 app.py 中注册时带 /api/v1/auth 前缀。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from web.middleware.auth import create_token, verify_token
from web.services.user_service import authenticate

router = APIRouter(tags=["auth"])


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


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    """用户名密码登录，签发 JWT。

    认证失败统一返回 401（不区分用户名错误还是密码错误，防信息泄露）。
    """
    user = authenticate(body.username, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
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
