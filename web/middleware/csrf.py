#!/usr/bin/env python3
"""
CSRF 防护中间件 — 双重提交 Cookie 模式

保护所有 POST/PUT/DELETE/PATCH 端点免受跨站请求伪造攻击。
GET/HEAD/OPTIONS 请求豁免。

工作原理：
  1. GET 请求响应中设置 csrf_token Cookie
  2. 前端 JS 读取 Cookie，在后续请求的 X-CSRF-Token 头中携带
  3. 服务端校验 Cookie 中的 token 与 Header 中的 token 一致
"""

import os
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

UNSAFE_METHODS = {"POST", "PUT", "DELETE", "PATCH"}


def generate_csrf_token() -> str:
    """生成随机 CSRF Token"""
    return secrets.token_urlsafe(32)


class CSRFMiddleware(BaseHTTPMiddleware):
    """CSRF 双重提交 Cookie 中间件"""

    def __init__(self, app, cookie_name: str = "csrf_token", header_name: str = "X-CSRF-Token"):
        super().__init__(app)
        self.cookie_name = cookie_name
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next):
        # 对不安全的方法进行 CSRF 校验
        # 豁免条件（双重提交 Cookie 模型下，CSRF 只对浏览器 Cookie 会话有意义）：
        #   1. API 路径（/api/*）— 纯 JSON API，前端用 fetch 携带 Authorization
        #      Bearer 头认证，不依赖浏览器自动发送的 Cookie，CSRF 攻击模型不适用。
        #      （JWT 认证由 FastAPI Depends(verify_token) 独立强制，与 CSRF 无关。）
        #   2. 携带 Authorization Header 的请求 — 即使是页面路由，带 Bearer token
        #      说明是程序化请求，跨站脚本无法伪造自定义 Header。
        #   3. 没有 CSRF Cookie — 不存在可被伪造的浏览器会话（首次访问）。
        has_api_path = request.url.path.startswith("/api/")
        has_auth_header = bool(request.headers.get("authorization"))
        needs_csrf = (
            request.method in UNSAFE_METHODS
            and not has_api_path
            and not has_auth_header
        )

        if needs_csrf:
            cookie_token = request.cookies.get(self.cookie_name, "")

            if cookie_token:
                header_token = request.headers.get(self.header_name, "")
                if not header_token or not secrets.compare_digest(cookie_token, header_token):
                    from starlette.responses import JSONResponse
                    return JSONResponse(
                        status_code=403,
                        content={"error": "csrf_token_invalid", "detail": "CSRF Token 不匹配"},
                    )

        response = await call_next(request)

        # 对 GET 请求（首次访问）设置 CSRF Cookie
        existing_token = request.cookies.get(self.cookie_name)
        if not existing_token:
            response.set_cookie(
                key=self.cookie_name,
                value=generate_csrf_token(),
                httponly=False,  # 前端 JS 需要读取
                samesite="lax",
                secure=os.environ.get("AI_TEST_ENV") == "production",
                path="/",
            )

        return response
