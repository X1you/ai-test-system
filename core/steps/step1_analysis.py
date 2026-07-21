#!/usr/bin/env python3
"""
Step 1: 需求分析（AI 步骤）

读取需求文档 → 调用 LLM 分析 → 生成 requirements_analysis.md + clarification_needed.md
支持质量自检：输出不合格时带着改进意见重跑（最多 1 次）
"""

import re
from pathlib import Path

from core.llm_client import LLMError
from core.logger import get_logger
from core.prompt_loader import build_kb_context, load_prompt, render
from core.steps.base import BaseStep, StepResult

_logger = get_logger("core.steps.step1")


class Step1Analysis(BaseStep):
    step_id = 1
    step_name = "需求分析"
    output_file = "requirements_analysis.md"

    def run(self, **kwargs) -> StepResult:  # type: ignore[override]
        """
        kwargs:
            requirements_path: 需求文档路径（与 requirements_text 二选一）
            requirements_text: 需求文档文本（直接传入）
            kb_context: 知识库上下文文本（可选增强）
        """
        requirements_path = kwargs.get("requirements_path", "")
        requirements_text = kwargs.get("requirements_text", "")
        kb_context = kwargs.get("kb_context", "")
        self.log(f"Step {self.step_id}/7: {self.step_name}", "STEP")

        # 1. 获取需求文档内容
        if requirements_text:
            content = requirements_text
        elif requirements_path:
            path = Path(requirements_path)
            if not path.exists():
                self.log(f"需求文档不存在: {requirements_path}", "ERR")
                return StepResult(ok=False, error="需求文档不存在")
            # ★ 修复 TC-015：多编码兜底，避免二进制/GBK 文件触发 UnicodeDecodeError
            content = self._safe_read_requirement(path)
            if content is None:
                self.log(f"需求文档无法解码（非 UTF-8/GBK 文本）: {requirements_path}", "ERR")
                return StepResult(ok=False, error="需求文档编码无法识别，请转为 UTF-8 或 GBK 文本")
        else:
            return StepResult(ok=False, error="未提供需求文档")

        if not self.llm:
            return StepResult(ok=False, error="AI 步骤需要 LLM 客户端")

        # 2. 组装提示词
        template = load_prompt("requirement_analysis")
        prompt = render(
            template,
            requirements=content,
            kb_context=build_kb_context(kb_context),
        )

        # 3. 调用 LLM（带重试）
        try:
            self.log("  调用 LLM 分析需求...", "INFO")
            response = self.llm.chat_with_retry(
                prompt,
                system="你是一位资深测试架构师，擅长需求分析和测试设计。",
            )
        except LLMError as e:
            self.log(f"LLM 调用失败: {e}", "ERR")
            return StepResult(ok=False, error=str(e))

        # 4. 解析输出（拆分需求拆解 + 待确认清单）
        analysis_md, clarification_md = self._split_response(response)

        if not analysis_md:
            self.log("LLM 输出格式异常：未找到需求拆解部分", "ERR")
            return StepResult(ok=False, error="LLM 输出格式异常")

        # 5. 质量自检
        check_result = self.self_check(
            analysis_md,
            criteria=(
                "1. 模块覆盖是否完整？是否遗漏了需求文档中提到的功能模块？\n"
                "2. 每个模块的功能点拆解是否合理？\n"
                "3. 可测项是否具体可执行（而非'验证功能'这种模糊表述）？\n"
                "4. 待确认事项是否覆盖了需求中的模糊、缺失、矛盾点？"
            ),
        )
        score = check_result.get("score", 0)
        self.log(f"  自检评分: {score}/100", "INFO")

        # 6. 不合格则重跑一次
        if not check_result.get("passed", False) and score < 70:
            issues = check_result.get("issues", [])
            self.log(f"  自检未通过，带着改进意见重跑 (问题: {len(issues)} 个)", "WARN")

            improvement_hint = "\n".join(f"- {issue}" for issue in issues)
            retry_prompt = (
                prompt
                + f"\n\n## 上次输出的问题（请务必改进）\n{improvement_hint}\n"
                + "\n请重新生成改进后的版本。"
            )
            try:
                response = self.llm.chat(retry_prompt)
                analysis_md, clarification_md = self._split_response(response)
            except LLMError:
                self.log("  重跑失败，使用原始输出", "WARN")

        # 7. 写入文件
        self._write_output("requirements_analysis.md", analysis_md)
        if clarification_md:
            self._write_output("clarification_needed.md", clarification_md)

        # 8. 统计
        modules = len(re.findall(r"## 模块[一二三四五六七八九十]", analysis_md))
        features = len(re.findall(r"功能点\s*[\d.]+", analysis_md))
        clarifications = len(re.findall(r"\d+\.\s+\*\*", clarification_md)) if clarification_md else 0

        self.log(
            f"需求分析完成 — {modules} 模块, {features} 功能点, "
            f"{clarifications} 待确认事项",
            "OK",
        )

        return StepResult(
            ok=True,
            data={
                "modules": modules,
                "features": features,
                "clarifications": clarifications,
                "check_score": score,
            },
        )

    @staticmethod
    def _safe_read_requirement(path: Path) -> str | None:
        """安全读取需求文档，多编码兜底。

        修复 TC-015：原 read_text(encoding='utf-8') 对二进制/GBK 文件崩。
        策略：UTF-8 → GBK → errors='replace' 三级降级。
        纯二进制（替换字符占比 >30%）返回 None。
        """
        raw = path.read_bytes()
        if not raw:
            return ""
        for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
            try:
                return raw.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
        # 终极兜底：强制 UTF-8 替换非法字节
        try:
            text = raw.decode("utf-8", errors="replace")
            # ★ 二进制内容检测：替换字符占比过高说明是二进制非文本
            replace_chars = text.count("\ufffd")
            if len(text) > 0 and replace_chars / len(text) > 0.30:
                return None
            return text
        except Exception as e:
            _logger.warning("step1_safe_read_fallback_failed", error=str(e), size=len(raw))
            return None

    @staticmethod
    def _split_response(response: str) -> tuple:
        """拆分 LLM 输出为（需求拆解, 待确认清单）"""
        # 1. 尝试全等号分隔线（>=10 个等号构成的独立行）
        m = re.search(r"\n={10,}\n", response)
        if m:
            return response[:m.start()].strip(), response[m.end():].strip()

        # 2. 尝试 ===CLARIFICATION=== 标记
        marker = "===CLARIFICATION==="
        if marker in response:
            parts = response.split(marker, 1)
            return parts[0].strip(), parts[1].strip()

        # 3. 兼容：两个 "# " 一级标题
        positions = [m.start() for m in re.finditer(r"^# ", response, re.MULTILINE)]
        if len(positions) >= 2:
            return response[: positions[1]].strip(), response[positions[1] :].strip()

        # 4. 无法拆分，全部当作需求拆解
        return response.strip(), ""
