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
from core.metrics import record_fallback, record_llm_call


class LLMGateway:
    """LLM 统一网关（Track A 轻量版）"""

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
        }

        # 解析备选 Provider
        fallback_configs = config.get("llm", {}).get("fallback", [])
        for fb_config in fallback_configs:
            try:
                self.fallback_chain.append(LLMClient(fb_config))
            except LLMError:
                pass  # 备选 Provider 配置错误时跳过

    async def chat(self, prompt: str, system: str | None = None, **kwargs) -> str:
        """带故障转移的 LLM 调用

        按顺序尝试 Provider：主 → 备选1 → 备选2 → ...
        所有 Provider 都失败时抛出最后的异常。
        """
        providers = [self.primary] + self.fallback_chain
        last_error: Exception | None = None
        provider_attempted = 0

        for i, provider in enumerate(providers):
            provider_name = provider.provider
            try:
                result = await self._call_provider(
                    provider, prompt, system, **kwargs
                )
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
                provider_attempted += 1
                continue

        raise last_error or RuntimeError("所有 LLM Provider 均不可用")

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
