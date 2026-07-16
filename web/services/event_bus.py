#!/usr/bin/env python3
"""
EventBus — 进程内 pub/sub 事件总线

基于 asyncio.Queue 实现，用于：
  - Pipeline 执行过程中的事件分发（步骤完成、日志、错误）
  - SSE 端点订阅实时事件流

线程安全：subscribe/unpublish 使用 threading.Lock 保护订阅者列表，
           允许从工作线程安全发布事件（publish 内部自动 schedule 到事件循环）。
"""

import asyncio
import threading


class EventBus:
    """进程内 pub/sub 事件总线"""

    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def _ensure_loop(self):
        """获取当前事件循环（延迟绑定）"""
        if self._loop is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                # 没有运行中的事件循环，在 publish 时用 run_coroutine_threadsafe
                pass

    async def subscribe(self, topic: str) -> asyncio.Queue:
        """订阅主题 — 返回一个 asyncio.Queue 用于接收事件

        Args:
            topic: 订阅主题（通常是 pipeline_id）

        Returns:
            asyncio.Queue，消费者从中 get() 事件
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        with self._lock:
            if topic not in self._subscribers:
                self._subscribers[topic] = []
            self._subscribers[topic].append(queue)
        return queue

    async def publish(self, topic: str, event: dict) -> None:
        """发布事件到指定主题的所有订阅者

        Args:
            topic: 发布主题
            event: 事件字典，格式: {"type": "step_done", "data": {...}}
        """
        with self._lock:
            queues = list(self._subscribers.get(topic, []))
        for queue in queues:
            try:
                # 非阻塞 put，队列满时丢弃旧事件腾出空间
                if queue.full():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                queue.put_nowait(event)
            except RuntimeError:
                # 事件循环已关闭，忽略
                pass

    def publish_sync(self, topic: str, event: dict) -> None:
        """同步发布事件（供工作线程调用）

        线程安全地从非 async 上下文发布事件。
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # 当前线程没有事件循环 — 找主线程的
            loop = self._loop

        if loop is not None and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.publish(topic, event), loop
            )
        else:
            # 没有可用事件循环，直接操作队列
            with self._lock:
                queues = list(self._subscribers.get(topic, []))
            for queue in queues:
                try:
                    if queue.full():
                        try:
                            queue.get_nowait()
                        except asyncio.QueueEmpty:
                            pass
                    queue.put_nowait(event)
                except RuntimeError:
                    pass

    async def unsubscribe(self, topic: str, queue: asyncio.Queue) -> None:
        """取消订阅 — 从主题的订阅者列表中移除指定 Queue"""
        with self._lock:
            if topic in self._subscribers:
                self._subscribers[topic] = [
                    q for q in self._subscribers[topic] if q is not queue
                ]
                # 无订阅者时清理主题
                if not self._subscribers[topic]:
                    del self._subscribers[topic]

    def subscriber_count(self, topic: str) -> int:
        """获取指定主题的订阅者数量"""
        with self._lock:
            return len(self._subscribers.get(topic, []))


# ─── 全局单例 ───

_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """获取全局 EventBus 单例"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def reset_event_bus() -> None:
    """重置全局 EventBus（主要用于测试）"""
    global _event_bus
    _event_bus = None
