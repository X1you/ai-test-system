#!/usr/bin/env python3
"""
提示词加载与组装工具

职责：
  - 从 core/prompts/ 加载静态模板
  - 组装动态增强（知识库上下文）
  - 提供统一的变量替换接口
"""

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(name: str) -> str:
    """
    加载提示词模板

    Args:
        name: 模板名（不含扩展名），如 "requirement_analysis"

    Returns:
        模板文本（含 {variable} 占位符）
    """
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"提示词模板不存在: {path}")
    return path.read_text(encoding="utf-8")


def render(template: str, **kwargs) -> str:
    """
    渲染模板 — 替换 {variable} 占位符

    对于值为空的变量，替换为空字符串而非 "{variable}"。

    Args:
        template: 含 {variable} 的模板
        **kwargs: 变量值

    Returns:
        渲染后的文本
    """
    result = template
    for key, value in kwargs.items():
        placeholder = "{" + key + "}"
        result = result.replace(placeholder, str(value) if value else "")
    return result


def build_kb_context(kb_text: str | None) -> str:
    """
    构建知识库上下文注入文本

    Args:
        kb_text: 知识库检索结果（knowledge-context.md 内容），可为空

    Returns:
        注入到提示词的知识库段落（空则返回空字符串）
    """
    if not kb_text or not kb_text.strip():
        return ""

    return f"""
## 知识库增强上下文

以下是知识库中检索到的相关业务规则、历史坑点和优质用例，请在分析时参考：

{kb_text}
"""
