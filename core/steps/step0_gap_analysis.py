#!/usr/bin/env python3
"""
Step 0: 需求漏洞扫描（PRD Gap Analysis）（AI 步骤）

读取需求文档 → 调用 LLM 以「红队思维」识别漏洞/歧义/缺失 →
生成 requirement_gap_analysis.md，并把 gap_count 注入全局上下文。

设计原则（来自无人值守铁律）：
  - 【容灾降级】：整步 try-except 保护。LLM 超时/解析失败 → gap_count=0，
    写入占位报告，坚决不阻断后续 Step 1 核心生成逻辑。
  -【结构化可解析】：gap_count 优先正则提取（不信任 LLM 输出 JSON 结构），
    多重兜底：JSON → 正则 → 计数 H3 标题 → 0。
"""

import re
from pathlib import Path

from core.llm_client import LLMError
from core.prompt_loader import load_prompt, render
from core.steps.base import BaseStep, StepResult


class Step0GapAnalysis(BaseStep):
    step_id = 0
    step_name = "需求漏洞扫描"
    output_file = "requirement_gap_analysis.md"

    def run(self, **kwargs) -> StepResult:  # type: ignore[override]
        """
        kwargs:
            requirements_path: 需求文档路径
            requirements_text: 需求文档文本（二选一）

        Returns:
            StepResult.data 含 gap_count: int（始终存在，失败降级为 0）
            ok 始终为 True（容灾：扫描失败不阻断主流程）
        """
        # ★ 整步 try-except 保护：任何异常都降级为 gap_count=0
        try:
            return self._run_inner(**kwargs)
        except Exception as e:
            self.log(f"⚠️ Step 0 异常降级: {e}，gap_count 置 0，继续后续步骤", "WARN")
            # 写入降级报告（便于用户知晓扫描未完成）
            try:
                self._write_output(
                    self.output_file,
                    "# 需求漏洞扫描报告（降级）\n\n"
                    "> 扫描过程中发生异常，本次未完成。后续 Step 1 仍会正常执行。\n"
                    f"> 异常信息: {e}\n\nGAP_COUNT: 0\n",
                )
            except Exception:
                pass  # 连降级报告都写不进去也别再抛
            return StepResult(
                ok=True,  # ★ 关键：降级不算失败，不阻断主流程
                data={"gap_count": 0, "degraded": True, "error": str(e)},
            )

    def _run_inner(self, **kwargs) -> StepResult:
        self.log(f"Step 0: {self.step_name}", "STEP")

        requirements_path = kwargs.get("requirements_path", "")
        requirements_text = kwargs.get("requirements_text", "")

        # 1. 读取需求内容
        if requirements_text:
            content = requirements_text
        elif requirements_path:
            path = Path(requirements_path)
            if not path.exists():
                self.log(f"需求文档不存在: {requirements_path}，跳过扫描", "WARN")
                return StepResult(ok=True, data={"gap_count": 0, "degraded": True})
            # ★ 修复 TC-002/010：编码兜底，避免二进制/GBK 文件触发 UnicodeDecodeError
            content = self._safe_read_text(path)
            if content is None:
                self.log(f"需求文档无法解码（非 UTF-8/GBK 文本）: {requirements_path}", "WARN")
                self._write_output(
                    self.output_file,
                    "# 需求漏洞扫描报告（降级）\n\n"
                    f"> 需求文档 `{requirements_path}` 无法以文本方式读取，"
                    "请确认是 UTF-8 或 GBK 编码的文本文件。\n\nGAP_COUNT: 0\n",
                )
                return StepResult(ok=True, data={"gap_count": 0, "degraded": True,
                                                  "error": "文件编码无法识别"})
        else:
            self.log("未提供需求文档，跳过漏洞扫描", "WARN")
            return StepResult(ok=True, data={"gap_count": 0, "degraded": True})

        # 2. LLM 必须可用
        if not self.llm:
            self.log("LLM 未初始化，跳过漏洞扫描", "WARN")
            return StepResult(ok=True, data={"gap_count": 0, "degraded": True})

        # 3. 组装提示词并调用（chat_with_retry 自带重试，超时会抛 LLMError）
        try:
            template = load_prompt("requirement_gap_analysis")
            prompt = render(template, requirements=content)
            self.log("  调用 LLM 扫描需求漏洞...", "INFO")
            response = self.llm.chat_with_retry(
                prompt,
                system="你是资深测试架构师，擅长以红队思维发现需求文档中的漏洞、歧义与缺失。",
            )
        except LLMError as e:
            self.log(f"LLM 调用失败（已重试）: {e}，gap_count 置 0", "WARN")
            self._write_output(
                self.output_file,
                "# 需求漏洞扫描报告（降级）\n\n"
                f"> LLM 调用失败，本次未完成。\n> {e}\n\nGAP_COUNT: 0\n",
            )
            return StepResult(ok=True, data={"gap_count": 0, "degraded": True, "error": str(e)})

        # 4. 解析 gap_count（多重兜底，不信任单一方式）
        gap_count = self._extract_gap_count(response)

        # 5. 写入报告
        self._write_output(self.output_file, response)

        self.log(f"✅ 需求漏洞扫描完成 — 识别 {gap_count} 项待澄清问题", "OK")

        return StepResult(
            ok=True,
            data={
                "gap_count": gap_count,
                "degraded": False,
            },
        )

    @staticmethod
    def _safe_read_text(path: Path) -> str | None:
        """安全读取文本文件，多编码兜底。

        修复 TC-002/010：原 read_text(encoding='utf-8') 对二进制/GBK 文件抛
        UnicodeDecodeError，虽有外层 try-except 兜底不崩，但会暴露异常栈。

        新策略：UTF-8 → GBK → errors='replace' 三级降级，绝不抛异常。
        二进制文件（替换字符占比 >30%）返回 None，由调用方决定降级处理。

        Returns:
            解码后的文本；若文件完全无法解码（纯二进制）返回 None。
        """
        raw = path.read_bytes()
        if not raw:
            return ""
        # 1. 优先 UTF-8（含 BOM 自动处理）
        for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
            try:
                return raw.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
        # 2. 终极兜底：强制 UTF-8 替换非法字节（保留可读部分）
        try:
            text = raw.decode("utf-8", errors="replace")
            # ★ 二进制内容检测：替换字符占比过高说明是二进制非文本
            replace_chars = text.count("\ufffd")
            if len(text) > 0 and replace_chars / len(text) > 0.30:
                return None
            return text
        except Exception:
            return None

    @staticmethod
    def _extract_gap_count(response: str) -> int:
        """从 LLM 输出中稳健提取 gap_count。

        兜底顺序（任一命中即用）：
          1. 末尾 `GAP_COUNT: N` 行（规范输出，取最后一个匹配避免历史值干扰）
          2. `gap_count": N` JSON 片段（取最后一个匹配）
          3. 统计漏洞标题数量（兼容数字/中文/字母编号）
          4. 0（全失败）

        ★ 修复 TC-008：原实现用 re.search 只取第一个匹配，若文本中出现历史值
        （如「之前 gap_count: 99 的记录」）会误取。改为取最后一个匹配。
        同时标题计数正则扩展支持中文编号（漏洞一/漏洞 A）。
        """
        if not response:
            return 0

        # 1. GAP_COUNT: N 行（大小写不敏感，兼容全角冒号）
        # ★ 修复：用 findall 取最后一个，避免文本中历史值干扰
        matches = re.findall(r"GAP_COUNT\s*[:：]\s*(\d+)", response, re.IGNORECASE)
        if matches:
            return max(0, int(matches[-1]))

        # 2. JSON 片段（取最后一个匹配）
        matches = re.findall(r'"gap_count"\s*:\s*(\d+)', response, re.IGNORECASE)
        if matches:
            return max(0, int(matches[-1]))

        # 3. 统计漏洞标题（兼容：漏洞 1 / 漏洞一 / 漏洞 A / 漏洞 #1）
        # ★ 修复：原 r'###\s*漏洞\s*\d+' 只匹配数字，中文/字母编号会漏
        headings = re.findall(
            r"###\s*漏洞\s*[\d一二三四五六七八九十百A-Za-z#]+\b",
            response,
        )
        if headings:
            return len(headings)

        return 0
