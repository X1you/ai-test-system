#!/usr/bin/env python3
"""
LLM 用量统计 — 应用级单例（进程内聚合）

设计目标：
  - 在 BaseLLMClient.chat / async_chat 中埋点，覆盖所有协议与调用路径
  - 不依赖 Prometheus / DB，进程级内存聚合（重启会丢失，MVP 阶段够用）
  - 线程安全：使用 threading.Lock 保护并发更新
  - 异常安全：统计记录失败绝不阻断业务调用

未来扩展：
  - 接入 SQLite 持久化（V5+）
  - 滚动时间窗口（最近 1h / 24h success rate）
  - 与 LLMGateway.stats（failovers / circuit_breaks）合并展示

暴露接口：
  - record_call(provider, model, success, tokens, latency_ms)
  - snapshot() -> dict  返回聚合视图（供 /api/v1/usage/llm 使用）
  - reset() -> dict     清空统计（用于测试 / 手动重置）
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class _ProviderStats:
    """单个 Provider 的累计统计（内部结构，不直接对外暴露）。"""

    calls: int = 0
    success: int = 0
    errors: int = 0
    tokens: int = 0
    latency_ms_total: float = 0.0
    latency_ms_max: float = 0.0
    last_call_at: float = 0.0
    last_error: str = ""
    # 按 model 维度的细分（key=model name）
    by_model: dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        avg = self.latency_ms_total / self.calls if self.calls > 0 else 0.0
        success_rate = self.success / self.calls if self.calls > 0 else 0.0
        return {
            "calls": self.calls,
            "success": self.success,
            "errors": self.errors,
            "tokens": self.tokens,
            "latency_ms_avg": round(avg, 2),
            "latency_ms_max": round(self.latency_ms_max, 2),
            "success_rate": round(success_rate, 4),
            "last_call_at": self.last_call_at,
            "last_error": self.last_error,
            "by_model": dict(self.by_model),
        }


class LLMUsageStats:
    """LLM 用量统计单例（进程级）。

    使用方式：
        from core.llm_usage import usage_stats
        usage_stats.record_call(provider="glm", model="glm-4-flash",
                                success=True, tokens=1234, latency_ms=850.5)
        snapshot = usage_stats.snapshot()
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._providers: dict[str, _ProviderStats] = {}
        self._started_at = time.time()
        self._total_calls = 0
        self._total_tokens = 0

    def record_call(
        self,
        provider: str,
        model: str,
        success: bool,
        tokens: int = 0,
        latency_ms: float = 0.0,
        error_msg: str = "",
    ) -> None:
        """记录一次 LLM 调用。

        异常安全：任何异常吞掉，绝不阻断业务。
        """
        try:
            provider = provider or "unknown"
            model = model or "unknown"
            tokens = max(0, int(tokens or 0))
            latency_ms = max(0.0, float(latency_ms or 0.0))
            now = time.time()

            with self._lock:
                ps = self._providers.setdefault(provider, _ProviderStats())
                ps.calls += 1
                if success:
                    ps.success += 1
                else:
                    ps.errors += 1
                    if error_msg:
                        ps.last_error = error_msg[:200]
                ps.tokens += tokens
                ps.latency_ms_total += latency_ms
                if latency_ms > ps.latency_ms_max:
                    ps.latency_ms_max = latency_ms
                ps.last_call_at = now

                # model 维度细分
                m = ps.by_model.setdefault(
                    model,
                    {"calls": 0, "success": 0, "errors": 0, "tokens": 0},
                )
                m["calls"] += 1
                if success:
                    m["success"] += 1
                else:
                    m["errors"] += 1
                m["tokens"] += tokens

                self._total_calls += 1
                self._total_tokens += tokens
        except Exception:
            # 统计失败绝不能影响业务
            pass

    def snapshot(self) -> dict:
        """返回当前聚合视图（深拷贝，调用方可安全使用）。"""
        with self._lock:
            providers_view = {
                name: ps.to_dict() for name, ps in self._providers.items()
            }
            total_calls = self._total_calls
            total_tokens = self._total_tokens
            total_success = sum(ps.success for ps in self._providers.values())
            total_errors = sum(ps.errors for ps in self._providers.values())
            started_at = self._started_at

        overall_success_rate = (
            total_success / total_calls if total_calls > 0 else 0.0
        )
        return {
            "started_at": started_at,
            "uptime_seconds": round(time.time() - started_at, 1),
            "totals": {
                "calls": total_calls,
                "success": total_success,
                "errors": total_errors,
                "tokens": total_tokens,
                "success_rate": round(overall_success_rate, 4),
            },
            "providers": providers_view,
        }

    def reset(self) -> dict:
        """清空所有统计（返回清空前快照，便于审计）。

        注意：不可在持锁状态下调用 self.snapshot()（threading.Lock 不可重入会死锁），
        因此在锁内手动构造快照。
        """
        with self._lock:
            providers_view = {
                name: ps.to_dict() for name, ps in self._providers.items()
            }
            total_calls = self._total_calls
            total_tokens = self._total_tokens
            total_success = sum(ps.success for ps in self._providers.values())
            total_errors = sum(ps.errors for ps in self._providers.values())
            started_at = self._started_at
            overall_success_rate = (
                total_success / total_calls if total_calls > 0 else 0.0
            )
            before = {
                "started_at": started_at,
                "uptime_seconds": round(time.time() - started_at, 1),
                "totals": {
                    "calls": total_calls,
                    "success": total_success,
                    "errors": total_errors,
                    "tokens": total_tokens,
                    "success_rate": round(overall_success_rate, 4),
                },
                "providers": providers_view,
            }
            self._providers.clear()
            self._started_at = time.time()
            self._total_calls = 0
            self._total_tokens = 0
        return before


# ─── 模块级单例 ───
usage_stats = LLMUsageStats()


__all__ = ["LLMUsageStats", "usage_stats"]
