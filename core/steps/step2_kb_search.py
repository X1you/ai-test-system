#!/usr/bin/env python3
"""
Step 2: 知识库检索（脚本步骤）

调用 kb_manager 检索 Obsidian Vault → 输出 knowledge-context.md
"""

import subprocess
import sys
from pathlib import Path

from core.steps.base import BaseStep, StepResult

# 知识库脚本路径
PROJECT_ROOT = Path(__file__).resolve().parents[2]
KB_SCRIPT = PROJECT_ROOT / "core" / "kb" / "kb_manager_mcp.py"


class Step2KBSearch(BaseStep):
    step_id = 2
    step_name = "知识库检索"
    output_file = "knowledge-context.md"

    def run(self, **kwargs) -> StepResult:  # type: ignore[override]
        """
        kwargs:
            keywords: 检索关键词（空则从需求分析中提取）
            requirements_analysis: 需求分析文本（用于提取关键词）
        """
        keywords = kwargs.get("keywords", "")
        analysis = kwargs.get("requirements_analysis", "")

        self.log(f"Step {self.step_id}/7: {self.step_name} (RAG)", "STEP")

        # 检查知识库是否启用（DB 数据源，与知识库页面配置同源）
        try:
            from core.kb.dynamic_kb_manager import get_dynamic_kb_manager

            mgr = get_dynamic_kb_manager()
            if not mgr.is_configured():
                self.log("知识库未配置，跳过 RAG 检索", "WARN")
                return StepResult(ok=True, data={"skipped": True, "hits": 0})
            kb_cfg = mgr.get_config() or {}
            vault_path = kb_cfg.get("vault_path", "")
        except Exception as e:
            self.log(f"知识库配置读取失败: {e}，跳过 RAG 检索", "WARN")
            return StepResult(ok=True, data={"skipped": True, "hits": 0})

        if not vault_path or not Path(vault_path).expanduser().exists():
            self.log(
                f"知识库路径不存在: {vault_path}，跳过 RAG 检索",
                "WARN",
            )
            return StepResult(ok=True, data={"skipped": True, "hits": 0})

        if not KB_SCRIPT.exists():
            self.log(f"知识库脚本不存在: {KB_SCRIPT}，跳过", "WARN")
            return StepResult(ok=True, data={"skipped": True, "hits": 0})

        # 提取关键词
        if not keywords and analysis:
            keywords = self._extract_keywords(analysis)
        if not keywords:
            keywords = "测试"

        self.log(f"  检索关键词: {keywords}", "KB")

        # 调用知识库脚本
        context_path = self._out("knowledge-context.md")
        try:
            result = subprocess.run(
                [sys.executable, str(KB_SCRIPT), "export", keywords,
                 "--output", str(context_path)],
                capture_output=True,
                text=True,
                timeout=60,
                env={**__import__("os").environ,
                     "OBSIDIAN_VAULT": vault_path},
            )
        except subprocess.TimeoutExpired:
            self.log("知识库检索超时", "WARN")
            return StepResult(ok=True, data={"skipped": True, "hits": 0})

        if result.returncode != 0:
            self.log(f"知识库检索出错: {result.stderr[:100]}", "WARN")
            return StepResult(ok=True, data={"skipped": True, "hits": 0})

        # 统计命中数 + 区分空库/无匹配/异常三态（修复 TC-005）
        hits = 0
        if context_path.exists():
            content = context_path.read_text(encoding="utf-8")
            hits = content.count("### ")

        # ★ 三态区分（v4.0 架构审计修复 TC-005）
        # 原实现只记 "未命中相关知识"，无法区分配置问题 vs 正常无匹配
        vault = Path(vault_path).expanduser()
        total_files = 0
        if vault.exists():
            total_files = sum(1 for _ in vault.rglob("*.md"))
        if hits > 0:
            self.log(f"知识库命中 {hits} 条相关知识", "KB")
        else:
            # 区分三种空命中场景
            if total_files == 0:
                # 场景1：知识库启用但空
                self.log(
                    "⚠️ 知识库已启用但 Vault 为空（0 个 .md 文件）。"
                    "建议先通过 Pipeline 回灌或手动添加业务规则/历史用例。"
                    "本次生成将不携带 RAG 增强（用例质量可能下降）",
                    "WARN",
                )
            elif total_files < 3:
                # 场景2：知识库文件极少（冷启动）
                self.log(
                    f"⚠️ 知识库仅有 {total_files} 个文件（冷启动阶段），"
                    "RAG 增强效果有限。随着使用积累会逐步提升",
                    "WARN",
                )
            else:
                # 场景3：知识库非空但本次无匹配（正常）
                self.log(
                    f"知识库未命中相关知识（Vault 共 {total_files} 文件，"
                    f"关键词: {keywords[:40]}）。本次不携带 RAG 增强",
                    "KB",
                )

        return StepResult(ok=True, data={"hits": hits, "skipped": False,
                                          "vault_total_files": total_files if vault.exists() else 0})

    @staticmethod
    def _extract_keywords(analysis_md: str) -> str:
        """从需求分析 Markdown 提取关键词"""
        import re

        modules = re.findall(r"模块[一二三四五六七八九十百千]+[：:]\s*(.+)", analysis_md)
        features = re.findall(r"功能点\s*[\d.]+[：:]\s*(.+)", analysis_md)

        keywords = modules[:3] + features[:3]
        seen = set()
        unique = []
        for kw in keywords:
            kw = kw.strip()
            if kw and kw not in seen:
                seen.add(kw)
                unique.append(kw)
            if len(unique) >= 5:
                break

        return " ".join(unique) if unique else "测试"
