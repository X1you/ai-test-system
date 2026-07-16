#!/usr/bin/env python3
"""
认证 API 路由 — Phase 4

Endpoints:
  POST /api/auth/login    — 用户名密码登录，返回 JWT Token
  POST /api/auth/logout   — 登出（客户端清除 Token）
  GET  /api/auth/me       — 获取当前用户信息
"""


from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from db.repository import get_repository
from web.middleware.auth import create_token, require_user
from web.services.user_service import authenticate

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ─── 请求模型 ───

class LoginRequest(BaseModel):
    """登录请求"""
    username: str
    password: str


# ─── 路由 ───

@router.post("/login")
async def login(req: LoginRequest):
    """用户名密码登录，返回 JWT Token"""
    user = authenticate(req.username, req.password)
    if user is None:
        raise HTTPException(401, "用户名或密码错误")

    token = create_token(user.id, user.username, user.role)
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user.username,
        "role": user.role,
    }


@router.post("/logout")
async def logout():
    """登出 — JWT 无状态，客户端清除 Token 即可"""
    return {"message": "已登出"}


@router.get("/me")
async def get_me(payload: dict = Depends(require_user)):
    """获取当前用户信息（需携带 JWT）"""
    repo = get_repository()
    user = repo.get_user_by_username(payload.get("username", ""))
    if user is None:
        raise HTTPException(404, "用户不存在")
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
    }
