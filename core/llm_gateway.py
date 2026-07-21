#!/usr/bin/env python3
"""
LLM Gateway 轻量版 — 多 Provider 路由 + 故障转移

Track A 简化版：
  - 主 Provider（从 config 读取）
  - 备选 Provider 列表（可配置）
  - 自动故障转移：主 → 备选1 → 备选2 → ...
  - 调用统计（每个 Provider 的调用次数和 Token 用量）

Track B 完整版将增加：缓存层、成本核算、Rate Limiting。
"""


from core.llm_client import LLMClient, LLMError
from core.metrics import record_circuit_breaker_state, record_fallback, record_llm_call

# ─── 断路器配置 ───
# 连续失败达到阈值 → 熔断该 Provider，熔断窗口内直接跳过（不等超时）
# 熔断窗口过后进入半开状态，允许 1 次探测；探测成功 → 恢复，失败 → 重新熔断
_CIRCUIT_FAILURE_THRESHOLD = 3   # 连续失败 3 次触发熔断
_CIRCUIT_RECOVERY_SECONDS = 60   # 熔断 60s 后进入半开探测


class _CircuitState:
    """单个 Provider 的断路器状态。"""

    __slots__ = ("consecutive_failures", "tripped_at", "half_open_probing")

    def __init__(self):
        self.consecutive_failures = 0
        self.tripped_at: float | None = None      # monotonic 时间戳，None=未熔断
        self.half_open_probing = False

    @property
    def is_open(self) -> bool:
        """是否处于熔断状态（含熔断窗口和半开探测中）。"""
        return self.tripped_at is not None

    def should_try(self, now: float) -> bool:
        """熔断窗口是否已过，允许半开探测。"""
        return (
            self.tripped_at is not None
            and not self.half_open_probing
            and (now - self.tripped_at) >= _CIRCUIT_RECOVERY_SECONDS
        )


class LLMGateway:
    """LLM 统一网关（Track A 轻量版 + 断路器）"""

    def __init__(self, config: dict):
        """
        Args:
            config: 完整配置（config["llm"] 为主 Provider，
                    config["llm"]["fallback"] 为备选列表）
        """
        self.primary = LLMClient(config["llm"])
        self.fallback_chain: list[LLMClient] = []
        self._stats: dict = {
            "total_calls": 0,
            "total_tokens": 0,
            "provider_calls": {},
            "provider_errors": {},
            "failovers": 0,
            "circuit_breaks": {},   # provider → 熔断次数
        }

        # 断路器状态：provider_name → _CircuitState
        self._circuits: dict[str, _CircuitState] = {}

        # 解析备选 Provider
        fallback_configs = config.get("llm", {}).get("fallback", [])
        for fb_config in fallback_configs:
            try:
                self.fallback_chain.append(LLMClient(fb_config))
            except LLMError:
                pass  # 备选 Provider 配置错误时跳过

    def _get_circuit(self, provider_name: str) -> _CircuitState:
        """获取或创建 Provider 的断路器状态。"""
        if provider_name not in self._circuits:
            self._circuits[provider_name] = _CircuitState()
        return self._circuits[provider_name]

    async def chat(self, prompt: str, system: str | None = None, **kwargs) -> str:
        """带故障转移 + 断路器的 LLM 调用

        按顺序尝试 Provider：主 → 备选1 → 备选2 → ...
        已熔断的 Provider 直接跳过（不等待超时），熔断窗口后允许半开探测。
        所有 Provider 都失败时抛出最后的异常。
        """
        import time

        providers = [self.primary] + self.fallback_chain
        last_error: Exception | None = None
        now = time.monotonic()

        for i, provider in enumerate(providers):
            provider_name = provider.provider
            circuit = self._get_circuit(provider_name)

            # 断路器逻辑：跳过已熔断的 Provider（除非进入半开窗口）
            if circuit.is_open and not circuit.should_try(now):
                continue
            if circuit.should_try(now):
                # 进入半开状态，本次调用即探测
                circuit.half_open_probing = True
                record_circuit_breaker_state(provider_name, "half_open")

            try:
                result = await self._call_provider(
                    provider, prompt, system, **kwargs
                )
                # 成功：重置该 Provider 的断路器
                self._reset_circuit(circuit)
                record_circuit_breaker_state(provider_name, "closed")
                if i > 0:
                    self._stats["failovers"] += 1
                    # 记录 Prometheus fallback 指标（上一个失败的 provider → 当前成功的）
                    record_fallback(providers[i - 1].provider, provider_name)
                return result
            except Exception as e:
                last_error = e
                self._stats["provider_errors"][provider_name] = (
                    self._stats["provider_errors"].get(provider_name, 0) + 1
                )
                # 标记失败，可能触发熔断
                self._record_failure(provider_name, circuit)
                continue

        raise last_error or RuntimeError("所有 LLM Provider 均不可用或已熔断")

    def _record_failure(self, provider_name: str, circuit: _CircuitState) -> None:
        """记录一次失败，连续失败达阈值则熔断。"""
        circuit.half_open_probing = False
        circuit.consecutive_failures += 1
        if circuit.consecutive_failures >= _CIRCUIT_FAILURE_THRESHOLD and not circuit.is_open:
            import time

            circuit.tripped_at = time.monotonic()
            self._stats["circuit_breaks"][provider_name] = (
                self._stats["circuit_breaks"].get(provider_name, 0) + 1
            )
            record_circuit_breaker_state(provider_name, "open")

    def _reset_circuit(self, circuit: _CircuitState) -> None:
        """调用成功后重置断路器（从半开恢复到闭合）。"""
        circuit.consecutive_failures = 0
        circuit.tripped_at = None
        circuit.half_open_probing = False

    async def _call_provider(
        self,
        provider: LLMClient,
        prompt: str,
        system: str | None,
        **kwargs,
    ) -> str:
        """调用单个 Provider — 直接使用原生异步调用"""
        import time

        provider_name = provider.provider
        self._stats["provider_calls"][provider_name] = (
            self._stats["provider_calls"].get(provider_name, 0) + 1
        )
        self._stats["total_calls"] += 1

        # 直接使用 async_chat 避免 asyncio.to_thread 线程切换开销
        start = time.monotonic()
        try:
            result = await provider.async_chat(prompt, system=system)
            # 记录成功调用的耗时指标（异常安全，不影响返回值）
            record_llm_call(
                provider_name, provider.model,
                time.monotonic() - start, success=True,
            )
        except Exception:
            # 失败也记录耗时和状态，便于观测错误请求的延迟
            record_llm_call(
                provider_name, provider.model,
                time.monotonic() - start, success=False,
            )
            raise

        stats = provider.stats
        self._stats["total_tokens"] += stats.get("total_tokens", 0)

        return result

    @property
    def stats(self) -> dict:
        """网关统计"""
        return dict(self._stats)

    def __repr__(self) -> str:
        return (
            f"LLMGateway(primary={self.primary.provider}, "
            f"fallbacks={[p.provider for p in self.fallback_chain]})"
        )
