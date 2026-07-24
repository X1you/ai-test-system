#!/usr/bin/env python3
"""
LLM Gateway — 多 Provider 路由 + 故障转移 + 断路器

支持多协议（OpenAI 兼容 / Anthropic / Custom HTTP）+ 多 Provider 列表。
主 Provider + 备选链按配置顺序依次尝试，已熔断的 Provider 自动跳过。

配置 schema（新）：
    llm:
      default: glm            # 默认 provider 名字
      providers:
        - name: glm
          protocol: openai_compatible
          api_key: ...
          base_url: ...
          model: glm-4-flash
          enabled: true
          priority: 0         # 数字越小优先级越高
        - name: deepseek
          ...
        - name: claude
          protocol: anthropic
          ...

配置 schema（旧，向后兼容）：
    llm:
      provider: deepseek
      api_key: ...
      base_url: ...
      model: deepseek-chat
      fallback: [ ... ]       # 旧备选链（隐式 priority=1,2,...）

旧 config 会在 config_loader 加载时自动迁移为新 schema。
"""

import time

from core.llm_client import LLMClient, LLMError, create_llm_client
from core.metrics import (
    record_circuit_breaker_state,
    record_fallback,
    record_llm_call,
)

# ─── 断路器配置 ───
_CIRCUIT_FAILURE_THRESHOLD = 3
_CIRCUIT_RECOVERY_SECONDS = 60


class _CircuitState:
    """单个 Provider 的断路器状态。"""

    __slots__ = ("consecutive_failures", "tripped_at", "half_open_probing")

    def __init__(self):
        self.consecutive_failures = 0
        self.tripped_at: float | None = None
        self.half_open_probing = False

    @property
    def is_open(self) -> bool:
        return self.tripped_at is not None

    def should_try(self, now: float) -> bool:
        return (
            self.tripped_at is not None
            and not self.half_open_probing
            and (now - self.tripped_at) >= _CIRCUIT_RECOVERY_SECONDS
        )


class LLMGateway:
    """LLM 统一网关（多协议 + 多 Provider + 断路器）

    接受完整 config（顶层含 "llm" 段），自动从 providers 列表或旧 schema 构造。
    chat() 按 priority 顺序尝试 Provider，断路器跳过的直接跳过。
    """

    def __init__(self, config: dict):
        """
        Args:
            config: 完整配置，至少含 config["llm"] 段。
        """
        llm_cfg = config.get("llm", {}) or {}
        providers_cfg = self._extract_providers(llm_cfg)

        if not providers_cfg:
            raise LLMError("LLM Gateway: 至少需要配置一个 provider")

        # 按 priority 排序（priority 越小越靠前）
        providers_cfg = sorted(providers_cfg, key=lambda p: p.get("priority", 999))

        # 构造所有 enabled 的 client
        self.clients: list = []
        for p_cfg in providers_cfg:
            if not p_cfg.get("enabled", True):
                continue
            try:
                client = create_llm_client(p_cfg)
                self.clients.append(client)
            except LLMError:
                # 配置错误的 provider 跳过（不阻塞网关启动）
                continue

        if not self.clients:
            raise LLMError("LLM Gateway: 没有任何可用的 provider（全部配置错误或全部禁用）")

        # 兼容旧 API：primary / fallback_chain 属性
        self.primary = self.clients[0]
        self.fallback_chain = self.clients[1:]

        # 统计
        self._stats: dict = {
            "total_calls": 0,
            "total_tokens": 0,
            "provider_calls": {},
            "provider_errors": {},
            "failovers": 0,
            "circuit_breaks": {},
        }

        # 断路器
        self._circuits: dict[str, _CircuitState] = {}

    @staticmethod
    def _extract_providers(llm_cfg: dict) -> list[dict]:
        """从 llm 段提取 providers 列表（兼容新旧 schema）"""
        # 新 schema
        if isinstance(llm_cfg.get("providers"), list) and llm_cfg["providers"]:
            providers = []
            default_name = llm_cfg.get("default")
            for i, p in enumerate(llm_cfg["providers"]):
                p = dict(p)
                if "name" not in p:
                    p["name"] = p.get("provider", f"provider_{i}")
                p.setdefault("priority", i)
                if default_name and p.get("name") == default_name:
                    p["priority"] = -1  # 默认 provider 排最前
                providers.append(p)
            return providers

        # 旧 schema：单 provider + 旧 fallback 列表
        if llm_cfg.get("provider") or llm_cfg.get("api_key") or llm_cfg.get("base_url"):
            providers = []
            # 主 provider
            main = {k: v for k, v in llm_cfg.items() if k not in ("fallback",)}
            if main.get("provider") is None and main.get("name"):
                main["provider"] = main["name"]
            main.setdefault("priority", 0)
            providers.append(main)
            # 旧 fallback 列表
            for i, fb in enumerate(llm_cfg.get("fallback", []) or []):
                fb = dict(fb)
                if "name" not in fb:
                    fb["name"] = fb.get("provider", f"fallback_{i}")
                fb.setdefault("priority", i + 1)
                providers.append(fb)
            return providers

        return []

    # ─── 断路器 ───

    def _get_circuit(self, provider_name: str) -> _CircuitState:
        if provider_name not in self._circuits:
            self._circuits[provider_name] = _CircuitState()
        return self._circuits[provider_name]

    def _record_failure(self, provider_name: str, circuit: _CircuitState) -> None:
        circuit.half_open_probing = False
        circuit.consecutive_failures += 1
        if circuit.consecutive_failures >= _CIRCUIT_FAILURE_THRESHOLD and not circuit.is_open:
            circuit.tripped_at = time.monotonic()
            self._stats["circuit_breaks"][provider_name] = (
                self._stats["circuit_breaks"].get(provider_name, 0) + 1
            )
            record_circuit_breaker_state(provider_name, "open")

    def _reset_circuit(self, circuit: _CircuitState) -> None:
        circuit.consecutive_failures = 0
        circuit.tripped_at = None
        circuit.half_open_probing = False

    # ─── 调用 ───

    async def chat(self, prompt: str, system: str | None = None, **kwargs) -> str:
        """带故障转移 + 断路器的 LLM 调用

        按 priority 顺序尝试 Provider：主 → 备选1 → 备选2 → ...
        已熔断的 Provider 直接跳过，熔断窗口后允许半开探测。
        所有 Provider 都失败时抛出最后的异常。
        """
        last_error: Exception | None = None
        now = time.monotonic()

        for i, provider in enumerate(self.clients):
            provider_name = provider.provider
            circuit = self._get_circuit(provider_name)

            if circuit.is_open and not circuit.should_try(now):
                continue
            if circuit.should_try(now):
                circuit.half_open_probing = True
                record_circuit_breaker_state(provider_name, "half_open")

            try:
                result = await self._call_provider(provider, prompt, system, **kwargs)
                self._reset_circuit(circuit)
                record_circuit_breaker_state(provider_name, "closed")
                if i > 0:
                    self._stats["failovers"] += 1
                    record_fallback(self.clients[i - 1].provider, provider_name)
                return result
            except Exception as e:
                last_error = e
                self._stats["provider_errors"][provider_name] = (
                    self._stats["provider_errors"].get(provider_name, 0) + 1
                )
                self._record_failure(provider_name, circuit)
                continue

        if last_error:
            raise last_error
        raise RuntimeError("所有 LLM Provider 均不可用或已熔断")

    async def _call_provider(
        self, provider, prompt: str, system: str | None, **kwargs
    ) -> str:
        """调用单个 Provider — 直接使用 async_chat"""
        provider_name = provider.provider
        self._stats["provider_calls"][provider_name] = (
            self._stats["provider_calls"].get(provider_name, 0) + 1
        )
        self._stats["total_calls"] += 1

        start = time.monotonic()
        try:
            result = await provider.async_chat(prompt, system=system)
            record_llm_call(
                provider_name, provider.model,
                time.monotonic() - start, success=True,
            )
        except Exception:
            record_llm_call(
                provider_name, provider.model,
                time.monotonic() - start, success=False,
            )
            raise

        stats = provider.stats
        self._stats["total_tokens"] += stats.get("total_tokens", 0)
        return result

    # ─── 统计 ───

    @property
    def stats(self) -> dict:
        return dict(self._stats)

    def __repr__(self) -> str:
        names = [c.provider for c in self.clients]
        return f"LLMGateway(providers={names})"


# 保留向后兼容：旧 import 路径
__all__ = ["LLMGateway", "LLMClient", "LLMError"]
