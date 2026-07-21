#!/usr/bin/env python3
"""
Prometheus 指标注册中心 — 集中管理所有自定义业务指标。

设计原则：
  1. 优雅降级：prometheus_client 未安装时，所有指标操作变为 no-op，
     绝不影响核心 LLM/Pipeline 逻辑（可观测性是"增强"不是"必需"）。
  2. 模块级单例：指标在模块加载时注册一次，全局复用（Prometheus 要求）。
  3. 零异常外泄：所有 observe/inc 操作都吞掉异常，指标故障不阻断业务。

当前指标：
  - llm_request_duration_seconds (Histogram): LLM 单次调用耗时
  - llm_provider_fallback_total (Counter): Provider 故障转移次数
  - llm_request_total (Counter): LLM 调用总次数（按 provider/status 维度）
"""

try:
    from prometheus_client import Counter, Gauge, Histogram

    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False


# ─── 指标定义（仅 prometheus_client 可用时注册）───

if _PROMETHEUS_AVAILABLE:
    # LLM 调用耗时直方图（秒）
    # buckets 覆盖 10ms ~ 60s 的典型 LLM 响应时间分布
    LLM_REQUEST_DURATION = Histogram(
        "llm_request_duration_seconds",
        "LLM 单次请求耗时（秒）",
        labelnames=("provider", "model"),
        buckets=(
            0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0,
        ),
    )

    # Provider fallback 次数（主 Provider 失败后切换备选）
    LLM_PROVIDER_FALLBACK = Counter(
        "llm_provider_fallback_total",
        "LLM Provider 故障转移总次数",
        labelnames=("from_provider", "to_provider"),
    )

    # LLM 调用总次数（按 provider + 成功/失败维度）
    LLM_REQUEST_TOTAL = Counter(
        "llm_request_total",
        "LLM 调用总次数",
        labelnames=("provider", "status"),
    )

    # LLM 断路器状态 Gauge（0=closed 正常, 1=open 熔断中, 2=half_open 半开探测）
    LLM_CIRCUIT_BREAKER_STATE = Gauge(
        "llm_circuit_breaker_state",
        "LLM Provider 断路器状态 (0=closed, 1=open, 2=half_open)",
        labelnames=("provider",),
    )
else:
    # 降级：no-op 桩对象，所有方法静默忽略
    class _NoopMetric:
        """prometheus_client 缺失时的 no-op 桩，保证业务逻辑不受影响。"""

        def labels(self, *args, **kwargs):
            return self

        def observe(self, *args, **kwargs):
            pass

        def inc(self, *args, **kwargs):
            pass

        def set(self, *args, **kwargs):
            pass

    LLM_REQUEST_DURATION = _NoopMetric()
    LLM_PROVIDER_FALLBACK = _NoopMetric()
    LLM_REQUEST_TOTAL = _NoopMetric()
    LLM_CIRCUIT_BREAKER_STATE = _NoopMetric()


def record_llm_call(provider: str, model: str, duration_seconds: float, success: bool = True):
    """记录一次 LLM 调用的指标（耗时 + 计数）。

    异常安全：任何指标记录失败都不抛出（可观测性不能阻断业务）。
    """
    try:
        LLM_REQUEST_DURATION.labels(provider=provider, model=model).observe(duration_seconds)
        LLM_REQUEST_TOTAL.labels(
            provider=provider, status="success" if success else "error"
        ).inc()
    except Exception as e:
        # 指标记录失败不应阻断业务，但需留痕便于排查（指标系统自身的异常）
        import logging
        logging.getLogger("core.metrics").debug(
            "metrics_record_llm_call_failed: %s", e
        )


def record_fallback(from_provider: str, to_provider: str):
    """记录一次 Provider 故障转移。

    异常安全：同上。
    """
    try:
        LLM_PROVIDER_FALLBACK.labels(
            from_provider=from_provider, to_provider=to_provider
        ).inc()
    except Exception as e:
        import logging
        logging.getLogger("core.metrics").debug(
            "metrics_record_fallback_failed: %s", e
        )


def is_metrics_enabled() -> bool:
    """prometheus_client 是否可用（用于条件判断）。"""
    return _PROMETHEUS_AVAILABLE


def record_circuit_breaker_state(provider: str, state: str):
    """记录断路器状态变更。

    Args:
        provider: Provider 名称
        state: "closed" | "open" | "half_open"
    """
    try:
        state_map = {"closed": 0, "open": 1, "half_open": 2}
        LLM_CIRCUIT_BREAKER_STATE.labels(provider=provider).set(
            state_map.get(state, 0)
        )
    except Exception as e:
        import logging
        logging.getLogger("core.metrics").debug(
            "metrics_record_circuit_breaker_failed: %s", e
        )
