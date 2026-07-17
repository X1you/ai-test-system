#!/usr/bin/env python3
"""
Step 3: 测试点梳理（AI 步骤）

读取需求分析结果 → 调用 LLM 生成结构化测试点清单 → 输出 testpoints.md
"""

import re

from core.llm_client import LLMError
from core.prompt_loader import build_kb_context, load_prompt, render
from core.steps.base import BaseStep, StepResult


class Step3Testpoints(BaseStep):
    step_id = 3
    step_name = "测试点梳理"
    output_file = "testpoints.md"

    def run(self, **kwargs) -> StepResult:  # type: ignore[override]
        """
        kwargs:
            requirements_analysis: 需求分析文本（必需）
            kb_context: 知识库上下文（可选）
            dimensions: 测试维度配置 basic|all|positive,negative,...
        """
        analysis = kwargs.get("requirements_analysis", "")
        kb_context = kwargs.get("kb_context", "")
        dimensions = kwargs.get("dimensions", "basic")

        self.log(f"Step {self.step_id}/7: {self.step_name}", "STEP")

        if not analysis:
            # 尝试从输出目录读取
            analysis = self._read_output("requirements_analysis.md") or ""
        if not analysis:
            return StepResult(ok=False, error="缺少需求分析文档")

        if not self.llm:
            return StepResult(ok=False, error="AI 步骤需要 LLM 客户端")

        # 1. 构建维度配置文本
        dimensions_config = self._build_dimensions_text(dimensions)

        # 2. 组装提示词
        template = load_prompt("test_points")
        prompt = render(
            template,
            requirements_analysis=analysis,
            kb_context=build_kb_context(kb_context),
            dimensions_config=dimensions_config,
        )

        # 3. 调用 LLM
        try:
            self.log("  调用 LLM 梳理测试点...", "INFO")
            response = self.llm.chat_with_retry(
                prompt,
                system="你是一位资深测试架构师，擅长全面覆盖的测试设计。",
            )
        except LLMError as e:
            self.log(f"LLM 调用失败: {e}", "ERR")
            return StepResult(ok=False, error=str(e))

        # 4. 质量自检
        check_result = self.self_check(
            response,
            criteria=(
                "1. 是否覆盖了需求分析中所有功能点？\n"
                "2. 每个功能点是否有正向、负向、边界、异常四个维度的测试点？\n"
                "3. 测试点的预期结果是否明确可判断？\n"
                "4. 测试数据是否具体可构造（而非'有效数据'这种模糊描述）？\n"
                "5. 每个测试点是否都包含「优先级」字段（取值 P0/P1/P2）？\n"
                "6. 优先级分配是否合理（P0 核心正向+安全，P1 重要负向边界，P2 性能/辅助）？"
            ),
        )
        score = check_result.get("score", 0)
        self.log(f"  自检评分: {score}/100", "INFO")

        # 5. 不合格重跑
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
            except LLMError:
                self.log("  重跑失败，使用原始输出", "WARN")

        # 6. 写入文件
        self._write_output("testpoints.md", response)

        # 7. 统计
        count = len(re.findall(r"测试点\s*[\d.]+", response))
        self.log(f"测试点梳理完成 — {count} 个测试点", "OK")

        return StepResult(
            ok=True,
            data={"count": count, "check_score": score},
        )

    @staticmethod
    def _build_dimensions_text(dimensions: str) -> str:
        """将维度配置转换为提示词中的说明文本"""
        all_dims = ["正向测试", "负向测试", "边界测试", "异常测试", "性能测试", "安全测试"]

        if dimensions == "all":
            active = all_dims
        elif dimensions == "basic":
            active = ["正向测试", "负向测试", "边界测试", "异常测试"]
        else:
            # 自定义：positive,negative → 正向测试,负向测试
            mapping = {
                "positive": "正向测试",
                "negative": "负向测试",
                "boundary": "边界测试",
                "exception": "异常测试",
                "performance": "性能测试",
                "security": "安全测试",
            }
            active = [mapping.get(d.strip(), d.strip()) for d in dimensions.split(",")]

        lines = [f"本次需要生成以下测试维度（共 {len(active)} 个）："]
        for dim in active:
            lines.append(f"- ✅ {dim}")
        lines.append("")
        lines.append("其他维度不需要生成。")
        return "\n".join(lines)
