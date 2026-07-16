#!/usr/bin/env python3
"""
统一日志工具 — structlog 优先，降级到 print

提供跨模块的结构化日志接口：
  - 当 structlog 可用时输出 JSON 结构化日志
  - 当 structlog 不可用时降级到 print()
  - 保持向后兼容现有的 print() 调用
"""

import sys
from typing import Any

try:
    import structlog
    _HAS_STRUCTLOG = True
except ImportError:
    _HAS_STRUCTLOG = False


def get_logger(name: str = "core"):
    """获取日志器 — structlog 优先，降级到 print"""
    if _HAS_STRUCTLOG:
        return structlog.get_logger(name)
    return _PrintLogger(name)


class _PrintLogger:
    """structlog 不可用时的降级日志器"""

    def __init__(self, name: str):
        self.name = name

    def _log(self, level: str, event: str, **kwargs: Any):
        parts = [f"[{level}] [{self.name}] {event}"]
        for k, v in kwargs.items():
            parts.append(f"{k}={v}")
        print(" ".join(parts), file=sys.stderr)

    def debug(self, event: str, **kwargs: Any):
        self._log("DEBUG", event, **kwargs)

    def info(self, event: str, **kwargs: Any):
        self._log("INFO", event, **kwargs)

    def warning(self, event: str, **kwargs: Any):
        self._log("WARN", event, **kwargs)

    def error(self, event: str, **kwargs: Any):
        self._log("ERROR", event, **kwargs)

    def critical(self, event: str, **kwargs: Any):
        self._log("CRITICAL", event, **kwargs)


# 模块级单例
_logger = get_logger("core")


def log_step(step_id: int, step_name: str, status: str, **extra: Any):
    """记录 Pipeline 步骤日志"""
    _logger.info("pipeline_step", step_id=step_id, step_name=step_name, status=status, **extra)


def log_llm_call(provider: str, model: str, tokens: int = 0, **extra: Any):
    """记录 LLM 调用日志"""
    _logger.info("llm_call", provider=provider, model=model, tokens=tokens, **extra)
