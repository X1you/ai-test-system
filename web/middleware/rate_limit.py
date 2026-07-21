#!/usr/bin/env python3
"""
速率限制中间件 — slowapi 集成

防止 API 被滥用。
- 全局默认：每分钟 60 次请求（按 IP）
- Pipeline 重操作（start/resume/cancel）：每分钟 5 次（按 IP）
  这些接口触发 LLM 调用链，资源消耗远高于普通查询。
"""

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# 全局限速器：每分钟 60 次（按 IP）
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

# Pipeline 重操作限流：每分钟 5 次
# start/resume/cancel 触发完整 LLM 调用链，需更严格限制
PIPELINE_HEAVY_LIMIT = "5/minute"


def get_limiter() -> Limiter:
    """获取全局限速器"""
    return limiter


def setup_rate_limiting(app):
    """将限速器挂载到 FastAPI 应用

    必须在所有路由注册之后、启动前调用。
    """
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
