#!/usr/bin/env python3
"""
速率限制中间件 — slowapi 集成

防止 API 被滥用。
- 全局默认：每分钟 60 次请求（按 IP）
- Pipeline 重操作（start/resume/cancel）：每分钟 5 次（按 IP）
  这些接口触发 LLM 调用链，资源消耗远高于普通查询。
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

# 全局限速器：每分钟 60 次（按 IP）
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


async def rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:
    """自定义限流异常处理器。

    slowapi 自带的 _rate_limit_exceeded_handler 假设收到的异常一定是
    RateLimitExceeded（有 .detail 属性）。但 SlowAPIMiddleware 内部在
    sync_check_limits 遇到非预期异常时，会把该异常透传给已注册的异常处理器，
    导致 AttributeError: 'AttributeError' object has no attribute 'detail'。

    本处理器对非 RateLimitExceeded 异常做防御性兜底，返回 500 而非崩溃。
    """
    if isinstance(exc, RateLimitExceeded):
        retry_after = getattr(exc, "retry_after", None) or 60
        return JSONResponse(
            status_code=429,
            content={"detail": f"请求过于频繁，请 {int(retry_after)} 秒后重试"},
            headers={"Retry-After": str(int(retry_after))},
        )
    # 非 RateLimitExceeded — 不应走到这里，防御性返回 500
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误"},
    )

# Pipeline 重操作限流：每分钟 5 次
# start/resume/cancel 触发完整 LLM 调用链，需更严格限制
PIPELINE_HEAVY_LIMIT = "5/minute"


def get_limiter() -> Limiter:
    """获取全局限速器"""
    return limiter


def setup_rate_limiting(app):
    """将限速器挂载到 FastAPI 应用

    必须在所有路由注册之后、启动前调用。
    SlowAPIMiddleware 是 @limiter.limit() 装饰器生效的必要条件 —
    没有它，装饰器静默失效（路由正常执行但不拦截超限请求）。
    """
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    app.add_middleware(SlowAPIMiddleware)
