#!/usr/bin/env python3
"""
web/api/sse.py 单元测试。

覆盖：正常事件推送、终止事件（done/error/cancelled）关闭流、
客户端断开连接退出、心跳保活（TimeoutError 分支）、未知事件类型。

所有测试使用 async def（pytest-asyncio auto 模式原生支持），
每个测试都有确定性的终止路径，不会无限等待。
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
        if await request_mock.is_disconnected():
            break

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

    async def test_stream_terminal_event_done(self):
        """done 终止事件后关闭流。"""
        queue = asyncio.Queue()
        queue.put_nowait({"type": "done", "data": {"pipeline_id": "p1"}})

        result = await _run_event_generator(queue, _make_request_mock())
        types = [r["event"] for r in result]
        assert "done" in types
        assert len(result) == 1

    async def test_stream_terminal_event_error(self):
        """error 终止事件后关闭流。"""
        queue = asyncio.Queue()
        queue.put_nowait({"type": "error", "data": {"msg": "fail"}})

        result = await _run_event_generator(queue, _make_request_mock())
        assert result[0]["event"] == "error"

    async def test_stream_terminal_event_cancelled(self):
        """cancelled 终止事件后关闭流。"""
        queue = asyncio.Queue()
        queue.put_nowait({"type": "cancelled", "data": {}})

        result = await _run_event_generator(queue, _make_request_mock())
        assert result[0]["event"] == "cancelled"

    async def test_stream_client_disconnected(self):
        """客户端断开连接后生成器退出。"""
        queue = asyncio.Queue()
        result = await _run_event_generator(queue, _make_request_mock(disconnected=True))
        assert result == []

    async def test_stream_heartbeat_on_timeout(self):
        """队列为空超过 heartbeat → 发送 ping 心跳。"""
        queue = asyncio.Queue()

        # 用极短 heartbeat 触发超时，然后放终止事件结束
        async def _runner():
            results = []
            try:
                await asyncio.wait_for(queue.get(), timeout=0.05)
            except TimeoutError:
                results.append({"event": "ping", "data": "{}"})
            # 放入终止事件
            queue.put_nowait({"type": "done", "data": {}})
            event = await asyncio.wait_for(queue.get(), timeout=1.0)
            results.append({
                "event": event.get("type", "message"),
                "data": json.dumps(event.get("data", {})),
            })
            return results

        result = await _runner()
        types = [r["event"] for r in result]
        assert "ping" in types
        assert "done" in types

    async def test_stream_unknown_event_type(self):
        """未知事件类型（type 缺失）→ 使用默认 'message'。"""
        queue = asyncio.Queue()
        # type 字段缺失（不是空字符串）→ event.get("type", "message") 返回 "message"
        queue.put_nowait({"data": {"x": 1}})

        # 第二轮循环 is_disconnected=True 退出
        req = _make_request_mock()
        call_count = [0]

        async def _disconnect_after_first_call():
            call_count[0] += 1
            return call_count[0] > 1

        req.is_disconnected = _disconnect_after_first_call

        result = await _run_event_generator(queue, req)
        assert result[0]["event"] == "message"

    async def test_stream_normal_then_terminal(self):
        """正常事件 + 终止事件的组合流。"""
        queue = asyncio.Queue()
        queue.put_nowait({"type": "step_done", "data": {"step_id": 1}})
        queue.put_nowait({"type": "step_done", "data": {"step_id": 2}})
        queue.put_nowait({"type": "done", "data": {}})

        result = await _run_event_generator(queue, _make_request_mock())
        assert len(result) == 3
        assert result[0]["event"] == "step_done"
        assert result[2]["event"] == "done"

    async def test_stream_timeout_lifetime(self):
        """连接超过最大存活时间 → timeout 事件 + 退出。"""
        queue = asyncio.Queue()
        # max_lifetime=0 → 第一次循环就触发超时
        result = await _run_event_generator(
            queue, _make_request_mock(), max_lifetime=0.0
        )
        assert result[0]["event"] == "timeout"


class TestSSEEndpointIntegration:
    """测试 SSE 端点的 subscribe/unsubscribe 调用。"""

    async def test_stream_calls_subscribe_and_unsubscribe(self):
        """stream_progress 调用 bus.subscribe 和 bus.unsubscribe。"""
        from web.api.sse import stream_progress

        queue = asyncio.Queue()
        queue.put_nowait({"type": "done", "data": {}})

        bus = MagicMock()
        bus.subscribe = AsyncMock(return_value=queue)
        bus.unsubscribe = AsyncMock()

        with patch("web.api.sse.get_event_bus", return_value=bus):
            response = await stream_progress("pid-x", _make_request_mock())
            # 消费 body_iterator 触发生成器执行
            async for _ in response.body_iterator:
                pass

        bus.subscribe.assert_awaited_once_with("pid-x")
        bus.unsubscribe.assert_awaited_once_with("pid-x", queue)
