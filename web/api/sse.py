#!/usr/bin/env python3
"""
SSE 端点 — Server-Sent Events 实时推送

路由：
  GET /api/pipeline/{pipeline_id}/stream

特性：
  - 基于 EventBus 订阅事件流
  - 15s 心跳保活（防止代理超时断开连接）
  - 终止事件（done / error / cancelled）后自动关闭流
"""

import asyncio
import json

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from web.middleware.auth import require_user
from web.services.event_bus import get_event_bus

router = APIRouter(prefix="/api/pipeline", tags=["sse"])

# 心跳间隔（秒）
HEARTBEAT_INTERVAL = 15.0

# 终止事件类型 — 收到后关闭流
TERMINAL_EVENTS = ("done", "error", "cancelled")


@router.get("/{pipeline_id}/stream")
async def stream_progress(
    pipeline_id: str, request: Request, user: dict = Depends(require_user)
):
    """SSE 实时推送 Pipeline 进度事件

    客户端使用 EventSource 连接此端点即可接收实时事件。
    事件格式：
        event: step_done
        data: {"step_id": 1, "name": "需求分析", ...}
    """
    bus = get_event_bus()
    queue = await bus.subscribe(pipeline_id)

    async def event_generator():
        try:
            while True:
                # 客户端断开连接时退出
                if await request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(
                        queue.get(), timeout=HEARTBEAT_INTERVAL
                    )
                    yield {
                        "event": event.get("type", "message"),
                        "data": json.dumps(
                            event.get("data", {}), ensure_ascii=False
                        ),
                    }
                    # 终止事件 — 关闭流
                    if event.get("type") in TERMINAL_EVENTS:
                        break
                except TimeoutError:
                    # 心跳保活
                    yield {"event": "ping", "data": "{}"}
        finally:
            await bus.unsubscribe(pipeline_id, queue)

    return EventSourceResponse(event_generator())
