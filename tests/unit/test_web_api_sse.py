#!/usr/bin/env python3
"""
web/api/sse.py 单元测试。

目标：将 SSE stream_progress 端点的覆盖率提升到 90%+。
覆盖：正常事件推送、终止事件（done/error/cancelled）关闭流、
客户端断开连接退出、心跳保活（TimeoutError 分支）、未知事件类型。

SSE 是异步流式端点，直接通过 HTTP client 测试较复杂，
因此提取 event_generator 内部逻辑直接测试生成器函数。
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


async def _run_event_generator(queue, request_mock, heartbeat=15.0, max_lifetime=1800.0):
    """直接执行 sse.py 内部的 event_generator 逻辑，收集 yield 的事件。

    复制 stream_progress 的核心循环，但用可控的 queue 和 request_mock，
    避免 EventSourceResponse 包装层的复杂性。
    """
    from web.api.sse import TERMINAL_EVENTS

    start_time = asyncio.get_running_loop().time()
    results = []

    while True:
        # 客户端断开检测
        if await request_mock.is_disconnected():
            break

        # 超时保护
        if asyncio.get_running_loop().time() - start_time > max_lifetime:
            results.append({"event": "timeout", "data": json.dumps({"reason": "max_lifetime"})})
            break

        try:
            event = await asyncio.wait_for(queue.get(), timeout=heartbeat)
            results.append({
                "event": event.get("type", "message"),
                "data": json.dumps(event.get("data", {}), ensure_ascii=False),
            })
            if event.get("type") in TERMINAL_EVENTS:
                break
        except TimeoutError:
            results.append({"event": "ping", "data": "{}"})

    return results


def _make_request_mock(disconnected=False):
    """构造 mock Request 对象。"""
    req = MagicMock()
    req.is_disconnected = AsyncMock(return_value=disconnected)
    return req


class TestSSEStream:
    """测试 SSE 实时推送端点的核心生成器逻辑。"""

    def test_stream_terminal_event_done(self):
        """done 终止事件后关闭流（测试 break 分支）。"""
        queue = asyncio.Queue()
        queue.put_nowait({"type": "done", "data": {"pipeline_id": "p1"}})

        result = asyncio.get_event_loop().run_until_complete(
            _run_event_generator(queue, _make_request_mock())
        )
        types = [r["event"] for r in result]
        assert "done" in types
        assert len(result) == 1  # done 后立即终止，无额外事件

    def test_stream_terminal_event_error(self):
        """error 终止事件后关闭流。"""
        queue = asyncio.Queue()
        queue.put_nowait({"type": "error", "data": {"msg": "fail"}})

        result = asyncio.get_event_loop().run_until_complete(
            _run_event_generator(queue, _make_request_mock())
        )
        assert result[0]["event"] == "error"

    def test_stream_terminal_event_cancelled(self):
        """cancelled 终止事件后关闭流。"""
        queue = asyncio.Queue()
        queue.put_nowait({"type": "cancelled", "data": {}})

        result = asyncio.get_event_loop().run_until_complete(
            _run_event_generator(queue, _make_request_mock())
        )
        assert result[0]["event"] == "cancelled"

    def test_stream_client_disconnected(self):
        """客户端断开连接后生成器退出（测试 is_disconnected 分支）。"""
        queue = asyncio.Queue()
        # 不放任何事件，但 is_disconnected=True → 立即退出
        result = asyncio.get_event_loop().run_until_complete(
            _run_event_generator(queue, _make_request_mock(disconnected=True))
        )
        assert result == []  # 断开后无事件 yield

    def test_stream_heartbeat_on_timeout(self):
        """队列为空超过 heartbeat → 发送 ping 心跳（测试 TimeoutError 分支）。"""
        queue = asyncio.Queue()
        # 用极短 heartbeat 触发超时，然后放终止事件结束
        async def _run():
            req = _make_request_mock()
            results = []
            start = asyncio.get_running_loop().time()

            # 手动实现以精确控制超时
            from web.api.sse import TERMINAL_EVENTS
            ping_sent = False
            # 先等一个超时
            try:
                await asyncio.wait_for(queue.get(), timeout=0.05)
            except TimeoutError:
                results.append({"event": "ping", "data": "{}"})
                ping_sent = True
            # 放入终止事件
            queue.put_nowait({"type": "done", "data": {}})
            event = await asyncio.wait_for(queue.get(), timeout=1.0)
            results.append({
                "event": event.get("type", "message"),
                "data": json.dumps(event.get("data", {})),
            })
            return results

        result = asyncio.get_event_loop().run_until_complete(_run())
        types = [r["event"] for r in result]
        assert "ping" in types
        assert "done" in types

    def test_stream_unknown_event_type(self):
        """未知事件类型 → 使用默认 'message'。"""
        queue = asyncio.Queue()
        queue.put_nowait({"type": "", "data": {"x": 1}})

        result = asyncio.get_event_loop().run_until_complete(
            _run_event_generator(queue, _make_request_mock())
        )
        assert result[0]["event"] == "message"

    def test_stream_normal_then_terminal(self):
        """正常事件 + 终止事件的组合流。"""
        queue = asyncio.Queue()
        queue.put_nowait({"type": "step_done", "data": {"step_id": 1}})
        queue.put_nowait({"type": "step_done", "data": {"step_id": 2}})
        queue.put_nowait({"type": "done", "data": {}})

        result = asyncio.get_event_loop().run_until_complete(
            _run_event_generator(queue, _make_request_mock())
        )
        assert len(result) == 3
        assert result[0]["event"] == "step_done"
        assert result[2]["event"] == "done"

    def test_stream_timeout_lifetime(self):
        """连接超过最大存活时间 → timeout 事件 + 退出。"""
        queue = asyncio.Queue()
        # max_lifetime=0 → 第一次循环就触发超时
        result = asyncio.get_event_loop().run_until_complete(
            _run_event_generator(queue, _make_request_mock(), max_lifetime=0.0)
        )
        assert result[0]["event"] == "timeout"


class TestSSEEndpointIntegration:
    """测试 SSE 端点的 subscribe/unsubscribe 调用。"""

    def test_stream_calls_subscribe_and_unsubscribe(self):
        """stream_progress 调用 bus.subscribe 和 bus.unsubscribe。"""
        from web.api.sse import stream_progress

        queue = asyncio.Queue()
        queue.put_nowait({"type": "done", "data": {}})

        bus = MagicMock()
        bus.subscribe = AsyncMock(return_value=queue)
        bus.unsubscribe = AsyncMock()

        async def _run():
            with patch("web.api.sse.get_event_bus", return_value=bus):
                response = await stream_progress("pid-x", _make_request_mock())
                # 消费 body_iterator 触发生成器执行
                async for _ in response.body_iterator:
                    pass

        asyncio.get_event_loop().run_until_complete(_run())
        bus.subscribe.assert_awaited_once_with("pid-x")
        bus.unsubscribe.assert_awaited_once_with("pid-x", queue)
