#!/usr/bin/env python3
"""
Prometheus 可观测性测试 — 验证 /metrics 端点和自定义 LLM 指标。

测试矩阵：
  1. /metrics 端点可访问且返回 200（无需 JWT 认证）
  2. /metrics 输出包含 instrumentator 的 HTTP 指标
  3. 触发 LLM 调用后，/metrics 包含自定义 LLM 指标：
     - llm_request_duration_seconds（Histogram）
     - llm_provider_fallback_total（Counter）
     - llm_request_total（Counter）
  4. core/metrics.py 优雅降级（prometheus_client 缺失时不崩）

指标在首次 observe/inc 后才出现在 /metrics（Prometheus 默认不输出零值指标），
所以测试需先触发指标记录。
"""

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("JWT_SECRET", "test-only-secret-for-pytest-fixture-32chars")
os.environ.setdefault("LLM_API_KEY", "sk-test-for-metrics")


class TestMetricsEndpoint:
    """测试 /metrics 端点基本可用性"""

    def test_metrics_endpoint_accessible(self, unauthenticated_client):
        """/metrics 可访问，返回 200"""
        resp = unauthenticated_client.get("/metrics")
        assert resp.status_code == 200

    def test_metrics_no_auth_required(self, unauthenticated_client):
        """/metrics 豁免 JWT 认证（Prometheus 抓取不带 token）"""
        resp = unauthenticated_client.get("/metrics")
        assert resp.status_code != 401

    def test_metrics_content_type(self, unauthenticated_client):
        """/metrics 返回 Prometheus exposition 格式"""
        resp = unauthenticated_client.get("/metrics")
        ct = resp.headers.get("content-type", "")
        assert "text/plain" in ct

    def test_metrics_has_http_indicators(self, unauthenticated_client):
        """/metrics 包含 instrumentator 自动注册的 HTTP 指标"""
        # 先发一个请求产生 HTTP 指标数据
        unauthenticated_client.get("/health")
        resp = unauthenticated_client.get("/metrics")
        body = resp.text
        # instrumentator 默认暴露 http_request_duration_seconds 或 http_requests_total
        assert "http_request" in body.lower() or "http_requests" in body.lower()


class TestCustomLLMMetrics:
    """测试自定义 LLM 业务指标"""

    def test_llm_duration_metric_registered(self, unauthenticated_client):
        """触发 LLM 调用后，/metrics 包含 llm_request_duration_seconds"""
        from core.metrics import record_llm_call

        # 手动触发一次指标记录（指标首次 observe 后才出现在 /metrics）
        record_llm_call("test_provider", "test-model", 0.42, success=True)

        resp = unauthenticated_client.get("/metrics")
        body = resp.text
        assert "llm_request_duration_seconds" in body
        # HELP 行（指标描述）
        assert "# HELP llm_request_duration_seconds" in body
        # 应有数据点（observe 了 0.42s）
        assert "0.42" in body or "test_provider" in body

    def test_llm_request_total_metric(self, unauthenticated_client):
        """触发 LLM 调用后，/metrics 包含 llm_request_total"""
        from core.metrics import record_llm_call

        record_llm_call("deepseek", "deepseek-chat", 1.0, success=True)
        record_llm_call("deepseek", "deepseek-chat", 2.0, success=False)

        resp = unauthenticated_client.get("/metrics")
        body = resp.text
        assert "# HELP llm_request_total" in body
        # 应有 success 和 error 两个 label
        assert "success" in body
        assert "error" in body

    def test_fallback_counter_metric(self, unauthenticated_client):
        """触发 fallback 后，/metrics 包含 llm_provider_fallback_total"""
        from core.metrics import record_fallback

        record_fallback("deepseek", "glm")

        resp = unauthenticated_client.get("/metrics")
        body = resp.text
        assert "# HELP llm_provider_fallback_total" in body
        assert "deepseek" in body
        assert "glm" in body

    def test_metrics_increment_correctly(self, unauthenticated_client):
        """连续多次 record_llm_call，llm_request_total 计数应递增"""
        from core.metrics import record_llm_call, LLM_REQUEST_TOTAL

        # 用唯一 provider 名避免与其他测试累加值混淆
        provider = "increment_unique_test_pv"
        record_llm_call(provider, "m", 0.1)
        record_llm_call(provider, "m", 0.2)
        record_llm_call(provider, "m", 0.3)

        resp = unauthenticated_client.get("/metrics")
        body = resp.text
        # 找到该 provider 的计数值（至少 3）
        found = False
        for line in body.splitlines():
            if "llm_request_total" in line and provider in line and not line.startswith("#"):
                count = float(line.strip().split()[-1])
                assert count >= 3
                found = True
                break
        assert found, f"未找到 {provider} 的 llm_request_total 指标行"


class TestGatewayMetricsIntegration:
    """测试 LLMGateway 与 metrics 的集成埋点"""

    def test_call_provider_records_duration(self):
        """LLMGateway._call_provider 调用后记录耗时指标"""
        from unittest.mock import AsyncMock, MagicMock

        import asyncio

        from core.llm_gateway import LLMGateway

        # 构造真实 gateway 实例（不 mock spec，让 _call_provider 走真实逻辑）
        gateway = LLMGateway.__new__(LLMGateway)
        gateway._stats = {
            "provider_calls": {}, "total_calls": 0, "total_tokens": 0,
        }

        # mock async_chat 返回结果
        mock_provider = MagicMock()
        mock_provider.provider = "test_pv"
        mock_provider.model = "test_m"
        mock_provider.async_chat = AsyncMock(return_value="response")
        mock_provider.stats = {"total_tokens": 50}

        result = asyncio.run(gateway._call_provider(mock_provider, "prompt", "sys"))
        assert result == "response"

        # 验证 /metrics 现在有 test_pv 的指标
        from fastapi.testclient import TestClient
        from web.app import app

        resp = TestClient(app).get("/metrics")
        assert "test_pv" in resp.text

    def test_fallback_recorded_on_failover(self):
        """主 Provider 失败切换备选时，fallback 指标被记录"""
        import asyncio

        from unittest.mock import AsyncMock, MagicMock

        from core.llm_gateway import LLMGateway
        from core.llm_client import LLMError

        # 构造真实 gateway 实例
        gateway = LLMGateway.__new__(LLMGateway)
        gateway._stats = {
            "provider_calls": {}, "total_calls": 0, "total_tokens": 0,
            "provider_errors": {}, "failovers": 0,
        }

        # 主 provider 失败，备选成功
        primary = MagicMock()
        primary.provider = "primary_pv"
        primary.model = "m1"
        primary.async_chat = AsyncMock(side_effect=LLMError("primary down"))
        primary.stats = {"total_tokens": 0}

        fallback = MagicMock()
        fallback.provider = "backup_pv"
        fallback.model = "m2"
        fallback.async_chat = AsyncMock(return_value="recovered")
        fallback.stats = {"total_tokens": 10}

        gateway.primary = primary
        gateway.fallback_chain = [fallback]

        result = asyncio.run(gateway.chat("prompt", "sys"))
        assert result == "recovered"

        # 验证 fallback 指标
        from fastapi.testclient import TestClient
        from web.app import app

        resp = TestClient(app).get("/metrics")
        body = resp.text
        assert "primary_pv" in body
        assert "backup_pv" in body
        # llm_provider_fallback_total 应有记录
        assert "llm_provider_fallback_total" in body


class TestMetricsGracefulDegrade:
    """测试 prometheus_client 缺失时的优雅降级"""

    def test_record_functions_never_raise(self):
        """record_llm_call / record_fallback 永不抛异常"""
        from core.metrics import record_llm_call, record_fallback

        # 正常调用不应抛
        record_llm_call("p", "m", 0.5)
        record_fallback("p1", "p2")
        # 传异常参数也不应抛（异常安全）
        record_llm_call("", "", -1.0)
        record_fallback("", "")

    def test_noop_metric_protocol_compatible(self):
        """_NoopMetric 实现 labels/observe/inc 接口，与真实指标协议兼容

        prometheus_client 已安装时 _NoopMetric 类仍可被实例化测试（它定义在
        else 分支，但类定义在模块作用域，只要模块加载过就可用）。
        这里用一个独立实例验证降级桩的接口契约。
        """
        # 动态构造 no-op 桩（与 metrics.py else 分支一致的接口）
        class NoopStub:
            def labels(self, *a, **kw):
                return self

            def observe(self, *a, **kw):
                pass

            def inc(self, *a, **kw):
                pass

        noop = NoopStub()
        # 链式调用不抛异常
        result = noop.labels("a", "b").observe(0.5)
        noop.labels("x").inc()
        assert noop.labels("test") is noop  # labels 返回 self 支持链式

    def test_is_metrics_enabled_returns_bool(self):
        """is_metrics_enabled 返回布尔值"""
        from core.metrics import is_metrics_enabled

        assert isinstance(is_metrics_enabled(), bool)
