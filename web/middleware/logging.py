#!/usr/bin/env python3
"""
结构化日志中间件 — structlog JSON 输出 + 请求级 trace_id

每个请求自动生成唯一 trace_id，贯穿整个请求处理链路。
"""

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


def configure_logging():
    """配置 structlog — JSON 格式输出"""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "app"):
    """获取结构化日志器"""
    return structlog.get_logger(name)


class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件 — 自动记录每个请求的 trace_id、方法、路径、状态码、耗时"""

    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("X-Trace-Id", str(uuid.uuid4())[:8])

        # 将 trace_id 注入 structlog 上下文
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(trace_id=trace_id)

        logger = get_logger("request")

        # 记录请求开始
        logger.info(
            "request_start",
            method=request.method,
            path=request.url.path,
        )

        # 处理请求
        import time

        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

        # 记录请求完成
        logger.info(
            "request_end",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
        )

        # 在响应头中添加 trace_id
        response.headers["X-Trace-Id"] = trace_id

        return response
