#!/usr/bin/env python3
"""
core/metrics.py 补充单元测试

覆盖：
  - _NoopMetric 桩对象（prometheus_client 缺失时的降级路径，覆盖 61-79 行）
  - record_llm_call / record_fallback / record_circuit_breaker_state 的异常安全路径
  - is_metrics_enabled 返回值
  - 正常记录路径 + 断路器状态映射

_NoopMetric 定义在 metrics.py 的 else 分支（prometheus_client 未安装时）。
当前环境已安装 prometheus_client，故用 importlib 以"导入失败"方式重新加载源码，
使 else 分支执行，从而覆盖 61-79 行。
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from core import metrics


def _load_noop_metrics_module():
    """以 prometheus_client 缺失的方式重新加载 metrics 模块源码。

    在模块命名空间预置一个会让 import 失败的 prometheus_client（None），
    触发 ImportError 分支 → else 分支定义 _NoopMetric（覆盖 61-79 行）。
    返回加载后的独立模块对象（不影响全局 core.metrics）。
    """
    source = (PROJECT_ROOT / "core" / "metrics.py").read_text(encoding="utf-8")
    spec = importlib.util.spec_from_loader("metrics_noop_test", loader=None)
    mod = importlib.util.module_from_spec(spec)
    # None 作为模块 → `from prometheus_client import ...` 触发异常
    sys.modules["prometheus_client"] = None
    try:
        exec(compile(source, str(PROJECT_ROOT / "core" / "metrics.py"), "exec"), mod.__dict__)
    finally:
        sys.modules.pop("prometheus_client", None)
    return mod


# ============================================================================
# _NoopMetric 桩对象（prometheus_client 缺失路径，覆盖 61-79 行）
# ============================================================================


class TestNoopMetric:
    """测试 prometheus_client 缺失时的 no-op 桩对象"""

    def test_labels_returns_self(self):
        # labels() 链式调用返回自身（桩对象可链式调用）
        m = _load_noop_metrics_module()._NoopMetric()
        assert m.labels("a", b="c") is m

    def test_observe_noop(self):
        # observe() 不抛异常、无返回值
        m = _load_noop_metrics_module()._NoopMetric()
        assert m.observe(1.2) is None

    def test_inc_noop(self):
        # inc() 不抛异常
        m = _load_noop_metrics_module()._NoopMetric()
        assert m.inc() is None

    def test_set_noop(self):
        # set() 不抛异常
        m = _load_noop_metrics_module()._NoopMetric()
        assert m.set(3) is None

    def test_chained_calls(self):
        # 链式调用 labels().observe().inc().set() 不报错
        m = _load_noop_metrics_module()._NoopMetric()
        m.labels(provider="p").observe(0.5)

    def test_noop_global_instances(self):
        # else 分支创建的 4 个全局指标实例都是 _NoopMetric 且方法静默
        mod = _load_noop_metrics_module()
        assert mod._PROMETHEUS_AVAILABLE is False
        for attr in ("LLM_REQUEST_DURATION", "LLM_PROVIDER_FALLBACK",
                     "LLM_REQUEST_TOTAL", "LLM_CIRCUIT_BREAKER_STATE"):
            inst = getattr(mod, attr)
            labeled = inst.labels(provider="test", model="test")
        labeled.observe(1)
        labeled.inc()
        labeled.set(0)


# ============================================================================
# record_llm_call
# ============================================================================


class TestRecordLlmCall:
    """测试记录单次 LLM 调用指标"""

    def test_success_no_exception(self):
        # 正常记录不抛异常（prometheus_client 安装与否均静默成功）
        metrics.record_llm_call("deepseek", "glm-4", 1.5, success=True)
        metrics.record_llm_call("openai", "gpt-4", 2.0, success=False)

    def test_exception_swallowed(self):
        # 异常安全：metric 抛异常时不外泄（被 except 吞掉，覆盖 92-95 行）
        boom = MagicMock()
        boom.labels.return_value.observe.side_effect = RuntimeError("boom")
        with patch.object(metrics, "LLM_REQUEST_DURATION", boom), \
             patch.object(metrics, "LLM_REQUEST_TOTAL", MagicMock()):
            metrics.record_llm_call("p", "m", 1.0)
        boom.labels.return_value.observe.assert_called_once_with(1.0)


# ============================================================================
# record_fallback
# ============================================================================


class TestRecordFallback:
    """测试记录 Provider 故障转移"""

    def test_success_no_exception(self):
        # 正常记录不抛异常
        metrics.record_fallback("openai", "deepseek")

    def test_exception_swallowed(self):
        # 异常安全：metric 抛异常时不外泄（覆盖 109-111 行）
        boom = MagicMock()
        boom.labels.return_value.inc.side_effect = RuntimeError("boom")
        with patch.object(metrics, "LLM_PROVIDER_FALLBACK", boom):
            metrics.record_fallback("a", "b")
        boom.labels.return_value.inc.assert_called_once()


# ============================================================================
# record_circuit_breaker_state
# ============================================================================


class TestRecordCircuitBreakerState:
    """测试记录断路器状态变更"""

    @pytest.mark.parametrize("state,expected", [
        ("closed", 0), ("open", 1), ("half_open", 2),
    ])
    def test_state_mapping(self, state, expected):
        # 各状态正确映射到数值（覆盖 129-132 行）
        mock_gauge = MagicMock()
        with patch.object(metrics, "LLM_CIRCUIT_BREAKER_STATE", mock_gauge):
            metrics.record_circuit_breaker_state("provider-x", state)
        mock_gauge.labels.return_value.set.assert_called_once_with(expected)

    def test_unknown_state_maps_to_closed(self):
        # 未知状态映射为 0（closed）
        mock_gauge = MagicMock()
        with patch.object(metrics, "LLM_CIRCUIT_BREAKER_STATE", mock_gauge):
            metrics.record_circuit_breaker_state("p", "nonsense")
        mock_gauge.labels.return_value.set.assert_called_once_with(0)

    def test_exception_swallowed(self):
        # 异常安全：metric 抛异常时不外泄（覆盖 133-135 行）
        boom = MagicMock()
        boom.labels.return_value.set.side_effect = RuntimeError("boom")
        with patch.object(metrics, "LLM_CIRCUIT_BREAKER_STATE", boom):
            metrics.record_circuit_breaker_state("p", "open")
        boom.labels.return_value.set.assert_called_once()


# ============================================================================
# is_metrics_enabled
# ============================================================================


class TestIsMetricsEnabled:
    """测试 prometheus_client 是否可用"""

    def test_returns_bool(self):
        # 返回值应为 bool（True/False 取决于环境）
        result = metrics.is_metrics_enabled()
        assert isinstance(result, bool)
