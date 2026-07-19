#!/usr/bin/env python3
"""
Phase 3 异步执行层测试

覆盖：
  - TaskBackend 抽象接口
  - InMemoryTaskBackend（submit / cancel / get_status / shutdown）
  - EventBus（subscribe / publish / unsubscribe / 线程安全）
  - SSE 端点（EventSourceResponse + 心跳）
  - PipelineTask 取消机制
  - config 中 pipeline.max_concurrent 配置项

注：不依赖 pytest-asyncio，用 asyncio.run() 在同步测试内执行异步逻辑。
"""

import asyncio
import sys
import threading
from pathlib import Path

import pytest

# 设置项目根路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ─── EventBus 测试 ───


class TestEventBus:
    """进程内 pub/sub 事件总线"""

    def test_subscribe_and_publish(self):
        """订阅 → 发布 → 接收"""
        from web.services.event_bus import EventBus

        async def _run():
            bus = EventBus()
            queue = await bus.subscribe("pipeline-001")

            await bus.publish(
                "pipeline-001", {"type": "step_done", "data": {"step": 1}}
            )

            event = await asyncio.wait_for(queue.get(), timeout=1.0)
            assert event["type"] == "step_done"
            assert event["data"]["step"] == 1

        asyncio.run(_run())

    def test_multiple_subscribers(self):
        """一个事件分发给多个订阅者"""
        from web.services.event_bus import EventBus

        async def _run():
            bus = EventBus()
            q1 = await bus.subscribe("topic")
            q2 = await bus.subscribe("topic")

            await bus.publish("topic", {"type": "ping", "data": {}})

            e1 = await asyncio.wait_for(q1.get(), timeout=1.0)
            e2 = await asyncio.wait_for(q2.get(), timeout=1.0)
            assert e1["type"] == "ping"
            assert e2["type"] == "ping"

        asyncio.run(_run())

    def test_unsubscribe(self):
        """取消订阅后不再收到事件"""
        from web.services.event_bus import EventBus

        async def _run():
            bus = EventBus()
            q = await bus.subscribe("topic")

            await bus.unsubscribe("topic", q)

            await bus.publish("topic", {"type": "ping", "data": {}})
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(q.get(), timeout=0.3)

        asyncio.run(_run())

    def test_unsubscribe_cleans_topic(self):
        """所有订阅者退出后主题被清理"""
        from web.services.event_bus import EventBus

        async def _run():
            bus = EventBus()
            q = await bus.subscribe("topic")
            assert bus.subscriber_count("topic") == 1

            await bus.unsubscribe("topic", q)
            assert bus.subscriber_count("topic") == 0

        asyncio.run(_run())

    def test_no_subscribers_publish_ok(self):
        """无订阅者时发布不报错"""
        from web.services.event_bus import EventBus

        async def _run():
            bus = EventBus()
            await bus.publish("nobody", {"type": "ping", "data": {}})

        asyncio.run(_run())

    def test_publish_sync_from_thread(self):
        """publish_sync 从工作线程安全发布"""
        from web.services.event_bus import EventBus

        async def _run():
            bus = EventBus()
            queue = await bus.subscribe("thread-topic")

            received = threading.Event()

            def worker():
                bus.publish_sync(
                    "thread-topic", {"type": "from_thread", "data": {}}
                )
                received.set()

            t = threading.Thread(target=worker)
            t.start()
            t.join(timeout=2.0)

            await asyncio.sleep(0.1)
            event = await asyncio.wait_for(queue.get(), timeout=1.0)
            assert event["type"] == "from_thread"

        asyncio.run(_run())

    def test_get_event_bus_singleton(self):
        """get_event_bus 返回全局单例"""
        from web.services.event_bus import get_event_bus, reset_event_bus

        reset_event_bus()
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2


# ─── SSE 端点测试 ───


class TestSSEEndpoint:
    """SSE 实时推送端点"""

    def test_sse_route_registered(self):
        """SSE stream 路由已注册（Sprint 6.1: 通过 OpenAPI schema 验证）"""
        from web.app import app

        schema = app.openapi()
        paths = schema.get("paths", {})
        assert "/api/v1/pipeline/{pipeline_id}/stream" in paths, \
            f"SSE route not found in OpenAPI paths: {list(paths.keys())[:10]}"

    def test_sse_router_has_correct_prefix(self):
        """SSE 路由前缀正确（Sprint 6.1: prefix 移至 app.include_router 层）"""
        from web.api.sse import router

        # router 本身不再携带 prefix，由 app.py 统一挂载 /api/v1/pipeline
        assert router.prefix == ""

    def test_heartbeat_interval_is_15s(self):
        """心跳间隔为 15 秒"""
        from web.api.sse import HEARTBEAT_INTERVAL

        assert HEARTBEAT_INTERVAL == 15.0

    def test_terminal_events_set(self):
        """终止事件类型定义正确"""
        from web.api.sse import TERMINAL_EVENTS

        assert "done" in TERMINAL_EVENTS
        assert "error" in TERMINAL_EVENTS
        assert "cancelled" in TERMINAL_EVENTS


# ─── PipelineTask 取消机制测试 ───


class TestPipelineTaskCancellation:
    """PipelineTask 取消机制"""

    def test_cancel_sets_flag(self, tmp_path):
        """cancel() 设置 _cancel_flag"""
        from web.services.pipeline_task import PipelineTask

        task = PipelineTask(
            pipeline_id="cancel-001",
            output_dir=str(tmp_path),
            config={},
            requirements_path="/tmp/req.md",
        )
        assert task._cancel_flag is False
        task.cancel()
        assert task._cancel_flag is True
        assert task.status == "cancelled"

    def test_is_cancelled_method(self, tmp_path):
        """is_cancelled() 正确反映取消状态"""
        from web.services.pipeline_task import PipelineTask

        task = PipelineTask(
            pipeline_id="cancel-002",
            output_dir=str(tmp_path),
            config={},
            requirements_path="/tmp/req.md",
        )
        assert task.is_cancelled() is False
        task._cancel_flag = True
        assert task.is_cancelled() is True

    def test_check_cancelled_raises(self, tmp_path):
        """_check_cancelled() 被取消时抛出异常"""
        from web.services.pipeline_task import PipelineTask, _PipelineCancelled

        task = PipelineTask(
            pipeline_id="cancel-003",
            output_dir=str(tmp_path),
            config={},
            requirements_path="/tmp/req.md",
        )
        task._check_cancelled()  # 未取消时不抛异常

        task._cancel_flag = True
        with pytest.raises(_PipelineCancelled):
            task._check_cancelled()


# ─── 配置项测试 ───


class TestMaxConcurrentConfig:
    """pipeline.max_concurrent 配置项"""

    def test_default_config_has_max_concurrent(self):
        """默认配置包含 max_concurrent"""
        from core.config_loader import DEFAULT_CONFIG

        assert "max_concurrent" in DEFAULT_CONFIG["pipeline"]
        assert DEFAULT_CONFIG["pipeline"]["max_concurrent"] == 2

    def test_load_config_reads_max_concurrent(self):
        """加载 config.yaml 时读取 max_concurrent"""
        from core.config_loader import load_config

        cfg = load_config()
        assert cfg["pipeline"]["max_concurrent"] == 2

    def test_max_concurrent_overridable(self, tmp_path):
        """max_concurrent 可被自定义配置覆盖"""
        from core.config_loader import load_config

        custom_yaml = tmp_path / "custom.yaml"
        custom_yaml.write_text(
            "pipeline:\n  max_concurrent: 5\n", encoding="utf-8"
        )
        cfg = load_config(str(custom_yaml))
        assert cfg["pipeline"]["max_concurrent"] == 5
