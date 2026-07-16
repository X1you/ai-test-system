#!/usr/bin/env python3
"""
LLM Gateway 完整版 (Track B) — 在 Track A 基础上增加：

1. 成本核算 — 按 Provider 价格计算每次调用费用
2. Rate Limiting — 令牌桶算法，按 Provider 配置 RPM 限制
3. 健康检查 — 定期检查 Provider 可用性
4. 自动降级 — 滑动窗口统计错误率，超阈值自动切换

兼容 Track A 接口，可作为 LLMGateway 的直接替代。
"""

import time
from collections import deque
from threading import Lock

from core.llm_gateway import LLMGateway

# ─── Provider 价格表（每百万 Token 美元）───

PROVIDER_PRICING: dict[str, dict[str, float]] = {
    "deepseek": {"input": 0.14, "output": 0.28},
    "glm": {"input": 0.50, "output": 0.50},
    "openai": {"input": 5.00, "output": 15.00},
    "moonshot": {"input": 3.30, "output": 3.30},
    "unknown": {"input": 1.00, "output": 1.00},
}


class TokenBucket:
    """令牌桶限流器"""

    def __init__(self, rate: float, capacity: int):
        self.rate = rate
        self.capacity = capacity
        self._tokens = float(capacity)
        self._last_time = time.monotonic()
        self._lock = Lock()

    def acquire(self) -> bool:
        """尝试获取一个令牌，返回是否成功"""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_time
            self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
            self._last_time = now
            if self._tokens >= 1:
                self._tokens -= 1
                return True
            return False


class ProviderHealthMonitor:
    """Provider 健康监控 — 滑动窗口错误率统计"""

    def __init__(self, window_size: int = 20, error_threshold: float = 0.5):
        """
        Args:
            window_size: 滑动窗口大小（最近 N 次调用）
            error_threshold: 错误率阈值，超过则标记为不健康
        """
        self.window_size = window_size
        self.error_threshold = error_threshold
        self._results: dict[str, deque] = {}  # provider_name -> deque of bool (True=success)
        self._lock = Lock()

    def record(self, provider: str, success: bool):
        """记录一次调用结果"""
        with self._lock:
            if provider not in self._results:
                self._results[provider] = deque(maxlen=self.window_size)
            self._results[provider].append(success)

    def is_healthy(self, provider: str) -> bool:
        """检查 Provider 是否健康"""
        with self._lock:
            results = self._results.get(provider)
            if not results or len(results) < 3:
                return True  # 样本不足时默认健康
            error_rate = 1.0 - (sum(results) / len(results))
            return error_rate < self.error_threshold

    def get_stats(self) -> dict[str, dict]:
        """获取所有 Provider 的健康统计"""
        with self._lock:
            stats = {}
            for provider, results in self._results.items():
                total = len(results)
                success = sum(results)
                stats[provider] = {
                    "total_calls": total,
                    "success_count": success,
                    "error_rate": round(1.0 - (success / total), 4) if total > 0 else 0,
                    "healthy": self.is_healthy(provider),
                }
            return stats


class EnhancedLLMGateway(LLMGateway):
    """LLM Gateway 完整版 — Track B"""

    def __init__(self, config: dict):
        super().__init__(config)

        # Rate Limiter（默认 60 RPM per provider）
        llm_cfg = config.get("llm", {})
        rpm_limit = llm_cfg.get("rate_limit_rpm", 60)
        self._rate_limiters: dict[str, TokenBucket] = {}
        for provider in [self.primary] + self.fallback_chain:
            self._rate_limiters[provider.provider] = TokenBucket(
                rate=rpm_limit / 60.0, capacity=rpm_limit
            )

        # 健康监控
        self._health = ProviderHealthMonitor(
            window_size=llm_cfg.get("health_window", 20),
            error_threshold=llm_cfg.get("health_error_threshold", 0.5),
        )

        # 成本核算
        self._cost_tracker: dict[str, float] = {}

        # 配置
        self._cost_budget = llm_cfg.get("cost_budget", 0)  # 0 = 不限制

    async def chat(self, prompt: str, system: str | None = None, **kwargs) -> str:
        """带健康检查 + 限流的故障转移调用"""
        providers = [self.primary] + self.fallback_chain
        last_error: Exception | None = None

        for i, provider in enumerate(providers):
            provider_name = provider.provider

            # 跳过不健康的 Provider
            if not self._health.is_healthy(provider_name):
                continue

            # 限流检查
            limiter = self._rate_limiters.get(provider_name)
            if limiter and not limiter.acquire():
                continue  # 限流，尝试下一个

            try:
                result = await self._call_provider(
                    provider, prompt, system, **kwargs
                )
                self._health.record(provider_name, True)
                self._track_cost(provider_name, provider.model, prompt, result)
                if i > 0:
                    self._stats["failovers"] += 1
                return result
            except Exception as e:
                last_error = e
                self._health.record(provider_name, False)
                self._stats["provider_errors"][provider_name] = (
                    self._stats["provider_errors"].get(provider_name, 0) + 1
                )
                continue

        from core.errors import LLMUnavailableError
        raise LLMUnavailableError(detail=str(last_error) if last_error else None)

    def _track_cost(self, provider: str, model: str, prompt: str, response: str):
        """估算并记录调用成本"""
        pricing = PROVIDER_PRICING.get(provider, PROVIDER_PRICING["unknown"])
        # 粗略估算 Token 数（1 Token ≈ 4 字符中文 / 0.75 单词英文）
        input_tokens = len(prompt) // 3
        output_tokens = len(response) // 3
        cost = (
            input_tokens * pricing["input"] / 1_000_000
            + output_tokens * pricing["output"] / 1_000_000
        )
        self._cost_tracker[provider] = self._cost_tracker.get(provider, 0) + cost

    @property
    def health_stats(self) -> dict:
        """健康检查统计"""
        return self._health.get_stats()

    @property
    def cost_stats(self) -> dict:
        """成本统计"""
        return {
            "per_provider": dict(self._cost_tracker),
            "total": sum(self._cost_tracker.values()),
            "budget": self._cost_budget,
        }
