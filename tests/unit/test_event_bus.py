#!/usr/bin/env python3
"""
EventBus 并发安全测试

覆盖：
  - 跨线程 publish_sync → async 消费者正确接收
  - subscribe 后 _loop 正确绑定（修复前的 bug：_loop 永远 None）
  - unsubscribe 清理订阅者（防内存泄漏）
  - 多订阅者广播
  - 队列满时丢弃旧事件（不阻塞生产者）
"""

import asyncio
import sys
import threading
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.mark.asyncio
class TestEventBusConcurrency:
    """EventBus 并发安全测试"""

    async def test_subscribe_binds_event_loop(self):
        """subscribe 后 _loop 应绑定到当前事件循环

        回归测试：修复前 _ensure_loop 是死代码，_loop 永远 None，
        导致 publish_sync 无法用 run_coroutine_threadsafe 跨线程调度。
        """
        from web.services.event_bus import EventBus

        bus = EventBus()
        assert bus._loop is None  # 初始未绑定
        await bus.subscribe("topic1")
        assert bus._loop is not None  # subscribe 后绑定
        assert bus._loop is asyncio.get_running_loop()

    async def test_cross_thread_publish_received(self):
        """工作线程 publish_sync → async 消费者正确收到事件"""
        from web.services.event_bus import EventBus

        bus = EventBus()
        q = await bus.subscribe("pipeline-1")

        received = []

        def producer():
            # 从非 async 工作线程发布
            bus.publish_sync("pipeline-1", {"type": "step_done", "data": {"id": 1}})

        t = threading.Thread(target=producer)
        t.start()

        event = await asyncio.wait_for(q.get(), timeout=2)
        received.append(event)
        t.join()

        assert len(received) == 1
        assert received[0]["type"] == "step_done"

    async def test_multiple_subscribers_broadcast(self):
        """同一主题多个订阅者都收到事件"""
        from web.services.event_bus import EventBus

        bus = EventBus()
        q1 = await bus.subscribe("topic")
        q2 = await bus.subscribe("topic")
        q3 = await bus.subscribe("topic")

        await bus.publish("topic", {"type": "msg", "data": {"v": 1}})

        e1 = await asyncio.wait_for(q1.get(), timeout=1)
        e2 = await asyncio.wait_for(q2.get(), timeout=1)
        e3 = await asyncio.wait_for(q3.get(), timeout=1)

        assert e1 == e2 == e3

    async def test_unsubscribe_removes_queue(self):
        """unsubscribe 后不再收到事件（防订阅泄漏）"""
        from web.services.event_bus import EventBus

        bus = EventBus()
        q = await bus.subscribe("topic")

        await bus.unsubscribe("topic", q)

        # 取消订阅后发布，旧 queue 不应收到
        await bus.publish("topic", {"type": "msg"})
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(q.get(), timeout=0.3)

        assert bus.subscriber_count("topic") == 0

    async def test_unsubscribe_cleans_empty_topic(self):
        """最后一个订阅者取消后，主题从 dict 移除（防内存泄漏）"""
        from web.services.event_bus import EventBus

        bus = EventBus()
        q = await bus.subscribe("temp-topic")
        assert bus.subscriber_count("temp-topic") == 1

        await bus.unsubscribe("temp-topic", q)

        # 主题应被完全移除
        with bus._lock:
            assert "temp-topic" not in bus._subscribers

    async def test_queue_full_drops_oldest(self):
        """队列满时丢弃最旧事件，不阻塞生产者"""
        from web.services.event_bus import EventBus

        bus = EventBus()
        q = await bus.subscribe("topic")  # maxsize=256

        # 填满队列
        for i in range(256):
            await bus.publish("topic", {"type": "msg", "data": {"i": i}})

        assert q.full()

        # 再发一个 → 应丢弃最旧的（i=0），腾位给新的
        await bus.publish("topic", {"type": "msg", "data": {"i": 999}})

        first = await q.get()
        # 最旧的 i=0 应已被丢弃，第一个是 i=1
        assert first["data"]["i"] == 1

    async def test_publish_to_no_subscribers_silent(self):
        """向无订阅者的主题发布 → 静默成功（不抛异常）"""
        from web.services.event_bus import EventBus

        bus = EventBus()
        # 不应抛异常
        await bus.publish("nobody", {"type": "msg"})
        bus.publish_sync("nobody", {"type": "msg"})

    async def test_publish_sync_without_loop_fallback(self):
        """publish_sync 在无事件循环时走 fallback（直接操作队列）"""
        from web.services.event_bus import EventBus

        bus = EventBus()
        q = await bus.subscribe("topic")

        # 模拟事件循环不可用（重置 _loop）
        original_loop = bus._loop
        bus._loop = None

        try:
            # 在 async 上下文里，get_running_loop 会成功；
            # 但如果我们在无循环的线程调用，会走 fallback。
            # 这里直接验证 fallback 逻辑：手动调用内部队列操作
            bus.publish_sync("topic", {"type": "fallback_test"})
            event = await asyncio.wait_for(q.get(), timeout=1)
            assert event["type"] == "fallback_test"
        finally:
            bus._loop = original_loop
