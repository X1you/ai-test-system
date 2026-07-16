#!/usr/bin/env python3
"""
步骤基类 — 所有 pipeline 步骤的统一接口

每个步骤接收：
  - llm: LLMClient（AI 步骤使用，脚本步骤可不用）
  - output_dir: 输出目录
  - config: 全局配置

每个步骤返回：
  StepResult(ok, data, error)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.llm_client import LLMClient


@dataclass
class StepResult:
    """步骤执行结果"""
    ok: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    human: bool = False  # 是否需要人工介入


class BaseStep(ABC):
    """步骤基类"""

    # 子类必须定义
    step_id: int = 0
    step_name: str = ""
    output_file: str = ""  # 主要输出文件名

    def __init__(self, output_dir: str, config: dict, llm: LLMClient | None = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.config = config
        self.llm = llm

    def _out(self, filename: str) -> Path:
        """获取输出目录下的完整路径"""
        return self.output_dir / filename

    def _read_output(self, filename: str) -> str | None:
        """读取已存在的输出文件"""
        path = self._out(filename)
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None

    def _write_output(self, filename: str, content: str) -> Path:
        """写入输出文件"""
        path = self._out(filename)
        path.write_text(content, encoding="utf-8")
        return path

    def log(self, msg: str, level: str = "INFO"):
        """日志输出"""
        icons = {
            "INFO": "  ",
            "STEP": "▶ ",
            "OK": "✅",
            "WARN": "⚠️",
            "ERR": "❌",
            "HUMAN": "👤",
            "KB": "🧠",
        }
        icon = icons.get(level, "")
        print(f"{icon} {msg}")

    @abstractmethod
    def run(self, **kwargs) -> StepResult:
        """执行步骤（子类实现）"""
        ...

    def self_check(self, content: str, criteria: str) -> dict:
        """
        质量自检 — LLM 评估输出质量

        Returns:
            {"score": int, "passed": bool, "issues": [...], "suggestions": [...]}
        """
        if not self.llm:
            return {"score": 100, "passed": True, "issues": [], "suggestions": []}
        if not self.config.get("pipeline", {}).get("self_check", False):
            return {"score": 100, "passed": True, "issues": [], "suggestions": []}
        return self.llm.evaluate(content, criteria)
