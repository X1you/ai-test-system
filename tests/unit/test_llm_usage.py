#!/usr/bin/env python3
"""
LLM 用量统计单元测试 — core.llm_usage + BaseLLMClient 埋点

覆盖：
  - LLMUsageStats.record_call 聚合正确性
  - snapshot 返回结构
  - reset 清空
  - 异常安全（record_call 不抛）
  - BaseLLMClient.chat / async_chat 埋点触发（mock _do_chat）
  - 并发安全（多线程 record_call）
"""

import sys
import threading
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def fresh_usage():
    """每个测试用例拿到一个干净的 LLMUsageStats 实例（避免单例污染）。"""
    from core.llm_usage import LLMUsageStats

    stats = LLMUsageStats()
    yield stats


class TestLLMUsageStats:
    """LLMUsageStats 单元测试。"""

    def test_empty_snapshot(self, fresh_usage):
        """空统计的 snapshot 结构完整。"""
        snap = fresh_usage.snapshot()
        assert snap["totals"]["calls"] == 0
        assert snap["totals"]["success"] == 0
        assert snap["totals"]["errors"] == 0
        assert snap["totals"]["tokens"] == 0
        assert snap["totals"]["success_rate"] == 0.0
        assert snap["providers"] == {}
        assert "started_at" in snap
        assert "uptime_seconds" in snap

    def test_record_single_success(self, fresh_usage):
        """单次成功调用聚合正确。"""
        fresh_usage.record_call(
            provider="glm", model="glm-4-flash",
            success=True, tokens=1234, latency_ms=850.5,
        )
        snap = fresh_usage.snapshot()
        assert snap["totals"]["calls"] == 1
        assert snap["totals"]["success"] == 1
        assert snap["totals"]["errors"] == 0
        assert snap["totals"]["tokens"] == 1234
        assert snap["totals"]["success_rate"] == 1.0

        ps = snap["providers"]["glm"]
        assert ps["calls"] == 1
        assert ps["success"] == 1
        assert ps["errors"] == 0
        assert ps["tokens"] == 1234
        assert ps["latency_ms_avg"] == 850.5
        assert ps["latency_ms_max"] == 850.5
        assert ps["last_error"] == ""

    def test_record_failure(self, fresh_usage):
        """失败调用聚合正确，last_error 被记录。"""
        fresh_usage.record_call(
            provider="deepseek", model="deepseek-chat",
            success=False, tokens=0, latency_ms=120.0,
            error_msg="connection timeout",
        )
        snap = fresh_usage.snapshot()
        assert snap["totals"]["calls"] == 1
        assert snap["totals"]["success"] == 0
        assert snap["totals"]["errors"] == 1
        assert snap["totals"]["success_rate"] == 0.0

        ps = snap["providers"]["deepseek"]
        assert ps["errors"] == 1
        assert ps["last_error"] == "connection timeout"

    def test_multiple_providers_aggregate(self, fresh_usage):
        """多 provider 分别聚合，互不污染。"""
        fresh_usage.record_call("a", "m1", True, 100, 50.0)
        fresh_usage.record_call("a", "m1", True, 200, 70.0)
        fresh_usage.record_call("b", "m2", False, 0, 30.0, "err")

        snap = fresh_usage.snapshot()
        assert snap["totals"]["calls"] == 3
        assert snap["totals"]["success"] == 2
        assert snap["totals"]["errors"] == 1
        assert snap["totals"]["tokens"] == 300

        a = snap["providers"]["a"]
        assert a["calls"] == 2
        assert a["success"] == 2
        assert a["tokens"] == 300
        assert a["latency_ms_avg"] == 60.0  # (50+70)/2
        assert a["latency_ms_max"] == 70.0
        assert a["success_rate"] == 1.0

        b = snap["providers"]["b"]
        assert b["calls"] == 1
        assert b["errors"] == 1
        assert b["success_rate"] == 0.0

    def test_by_model_breakdown(self, fresh_usage):
        """同 provider 多 model 维度细分。"""
        fresh_usage.record_call("glm", "glm-4-flash", True, 100, 50.0)
        fresh_usage.record_call("glm", "glm-4-air", True, 50, 30.0)
        fresh_usage.record_call("glm", "glm-4-flash", True, 80, 40.0)

        ps = fresh_usage.snapshot()["providers"]["glm"]
        assert ps["by_model"]["glm-4-flash"]["calls"] == 2
        assert ps["by_model"]["glm-4-flash"]["tokens"] == 180
        assert ps["by_model"]["glm-4-air"]["calls"] == 1
        assert ps["by_model"]["glm-4-air"]["tokens"] == 50

    def test_reset(self, fresh_usage):
        """reset 清空并返回清空前快照。"""
        fresh_usage.record_call("a", "m", True, 10, 5.0)
        before = fresh_usage.reset()
        assert before["totals"]["calls"] == 1

        snap = fresh_usage.snapshot()
        assert snap["totals"]["calls"] == 0
        assert snap["providers"] == {}

    def test_exception_safety(self, fresh_usage):
        """异常输入不抛错（统计失败绝不阻断业务）。"""
        # 这些都不应抛异常
        fresh_usage.record_call(None, None, True, 0, 0.0)
        fresh_usage.record_call("", "", True, -10, -5.0)  # 负值被 clamp 到 0
        fresh_usage.record_call("x", "y", True, "not-int", None)  # 类型异常
        # 聚合不崩
        snap = fresh_usage.snapshot()
        assert "totals" in snap

    def test_concurrent_writes(self, fresh_usage):
        """多线程并发 record_call 不丢数据。"""
        N_THREADS = 10
        N_PER_THREAD = 100

        def _worker():
            for _ in range(N_PER_THREAD):
                fresh_usage.record_call("p", "m", True, 1, 1.0)

        threads = [threading.Thread(target=_worker) for _ in range(N_THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        snap = fresh_usage.snapshot()
        assert snap["totals"]["calls"] == N_THREADS * N_PER_THREAD
        assert snap["totals"]["tokens"] == N_THREADS * N_PER_THREAD


class TestBaseLLMClientInstrumentation:
    """验证 BaseLLMClient.chat / async_chat 埋点触发。"""

    @staticmethod
    def _make_client(provider: str, model: str) -> "BaseLLMClient":
        """构造一个最小可用的具体 BaseLLMClient 子类实例（绕过抽象方法）。"""
        from core.llm_client import BaseLLMClient

        class _ConcreteClient(BaseLLMClient):
            protocol = "openai_compatible"

            def _do_chat(self, messages, temperature, max_tokens, timeout=None):
                return ("_concrete", 0)

            async def _async_do_chat(self, messages, temperature, max_tokens, timeout=None):
                return ("_concrete", 0)

        client = _ConcreteClient(
            {"name": provider, "provider": provider, "model": model, "api_key": "sk-test"}
        )
        return client

    def test_chat_success_records_usage(self, fresh_usage):
        """chat() 成功时埋点触发。"""
        from unittest.mock import patch

        client = self._make_client("test_pv", "test-model")

        # mock _do_chat 返回 (content, tokens)
        with patch.object(client, "_do_chat", return_value=("hello", 42)):
            with patch("core.llm_client.usage_stats", fresh_usage):
                result = client.chat("prompt", "sys")

        assert result == "hello"
        snap = fresh_usage.snapshot()
        assert snap["totals"]["calls"] == 1
        assert snap["totals"]["success"] == 1
        assert snap["totals"]["tokens"] == 42

    @pytest.mark.asyncio
    async def test_async_chat_failure_records_usage(self, fresh_usage):
        """async_chat() 失败时埋点触发。"""
        from core.llm_client import LLMError
        from unittest.mock import patch

        client = self._make_client("fail_pv", "fail-model")

        async def _boom(*args, **kwargs):
            raise RuntimeError("network down")

        with patch.object(client, "_async_do_chat", side_effect=_boom):
            with patch("core.llm_client.usage_stats", fresh_usage):
                with pytest.raises(LLMError):
                    await client.async_chat("prompt", "sys")

        snap = fresh_usage.snapshot()
        assert snap["totals"]["calls"] == 1
        assert snap["totals"]["errors"] == 1
        assert snap["totals"]["success"] == 0
        assert "network down" in snap["providers"]["fail_pv"]["last_error"]


class TestUsageEndpoint:
    """验证 /api/v1/usage/llm 端点。"""

    def test_get_llm_usage_endpoint(self, tmp_path, monkeypatch):
        """GET /api/v1/usage/llm 返回聚合结构。"""
        from core.llm_usage import usage_stats

        # 隔离单例：用临时实例替换
        from core.llm_usage import LLMUsageStats

        fake = LLMUsageStats()
        fake.record_call("glm", "glm-4", True, 100, 50.0)
        fake.record_call("glm", "glm-4", False, 0, 10.0, "boom")

        # 替换模块级单例（web.api.usage 在 import 时已绑定，需 patch 引用）
        import web.api.usage as usage_module

        monkeypatch.setattr(usage_module, "usage_stats", fake)

        from fastapi.testclient import TestClient
        from web.app import app

        # 跳过认证（测试环境）
        monkeypatch.setattr(
            "web.middleware.auth._AUTH_ENABLED", False, raising=True
        )

        resp = TestClient(app).get("/api/v1/usage/llm")
        assert resp.status_code == 200
        body = resp.json()
        assert body["totals"]["calls"] == 2
        assert body["totals"]["success"] == 1
        assert body["totals"]["errors"] == 1
        assert "glm" in body["providers"]
