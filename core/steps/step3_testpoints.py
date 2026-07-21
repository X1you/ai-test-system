#!/usr/bin/env python3
"""
Step 3: 测试点梳理（AI 步骤）— P3-A 分模块调用

读取需求分析结果 → 按模块拆分 → 每模块独立调用 LLM 生成测试点 → 合并重编号 → 输出 testpoints.md

P3-A 改造（解决长文档覆盖不全问题）：
- 旧方案：整个需求分析一次性发给 LLM，模块数 >6 时靠后模块被忽略
- 新方案：先提取模块列表，每个模块独立调用 LLM，彻底解决覆盖问题
- 对模块数 ≤2 的小文档自动降级为单次调用（避免无谓拆分开销）
"""

import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.config_loader import load_config
from core.llm_client import LLMError
from core.prompt_loader import build_kb_context, load_prompt, render
from core.steps.base import BaseStep, StepResult

# 触发分模块调用的最小模块数（≤此值用旧的单次调用模式）
SPLIT_MODULE_THRESHOLD = 2


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

        # 2. 提取模块列表
        modules = self._extract_modules(analysis)

        # 3. 路由：模块少走单次调用，模块多走分模块调用
        if len(modules) <= SPLIT_MODULE_THRESHOLD:
            self.log(f"  模块数 {len(modules)} ≤ {SPLIT_MODULE_THRESHOLD}，使用单次调用模式", "INFO")
            return self._run_single(analysis, kb_context, dimensions_config)
        else:
            self.log(f"  模块数 {len(modules)} > {SPLIT_MODULE_THRESHOLD}，使用分模块调用模式", "INFO")
            return self._run_per_module(modules, analysis, kb_context, dimensions_config)

    # ─── 单次调用模式（原逻辑，小文档用）───

    def _run_single(self, analysis: str, kb_context: str, dimensions_config: str) -> StepResult:
        """单次调用 LLM 生成测试点（原逻辑，模块数 ≤ 阈值时使用）。"""
        template = load_prompt("test_points")
        prompt = render(
            template,
            requirements_analysis=analysis,
            kb_context=build_kb_context(kb_context),
            dimensions_config=dimensions_config,
        )

        try:
            self.log("  调用 LLM 梳理测试点...", "INFO")
            response = self.llm.chat_with_retry(
                prompt,
                system="你是一位资深测试架构师，擅长全面覆盖的测试设计。",
            )
        except LLMError as e:
            self.log(f"LLM 调用失败: {e}", "ERR")
            return StepResult(ok=False, error=str(e))

        # 质量自检
        score = self._self_check(response)
        self.log(f"  自检评分: {score}/100", "INFO")

        # 不合格重跑
        response = self._retry_if_needed(prompt, response, score)

        # 写入文件
        self._write_output("testpoints.md", response)

        count = len(re.findall(r"测试点\s*[\d.]+", response))
        self.log(f"测试点梳理完成 — {count} 个测试点", "OK")
        return StepResult(ok=True, data={"count": count, "check_score": score})

    # ─── 分模块调用模式（P3-A 新增）───

    def _run_per_module(self, modules: list[dict], analysis: str, kb_context: str, dimensions_config: str) -> StepResult:
        """对每个模块独立调用 LLM，然后合并。

        Args:
            modules: [{"name": "模块名", "content": "该模块的需求分析文本"}]
            analysis: 完整需求分析（用于 fallback）
            kb_context: 知识库上下文
            dimensions_config: 维度配置文本
        """
        template = load_prompt("test_points_per_module")
        max_concurrent = self._get_max_concurrent()

        self.log(f"  分模块生成中（{len(modules)} 个模块，并发上限 {max_concurrent}）...", "INFO")

        # 每模块独立调用 LLM
        module_results: dict[str, str] = {}
        errors: list[str] = []
        completed = 0

        def _generate_for_module(module: dict) -> tuple[str, str | None, str | None]:
            """为单个模块生成测试点，返回 (模块名, LLM响应, 错误信息)。"""
            mod_name = module["name"]
            prompt = render(
                template,
                module_analysis=module["content"],
                kb_context=build_kb_context(kb_context),
                dimensions_config=dimensions_config,
            )
            try:
                resp = self.llm.chat_with_retry(
                    prompt,
                    system=f"你是一位资深测试架构师，专注「{mod_name}」模块的测试设计。",
                )
                return mod_name, resp, None
            except LLMError as e:
                return mod_name, None, str(e)

        with ThreadPoolExecutor(max_workers=max_concurrent) as pool:
            futures = {pool.submit(_generate_for_module, mod): mod for mod in modules}
            for future in as_completed(futures):
                mod_name, resp, err = future.result()
                completed += 1
                if err:
                    errors.append(f"{mod_name}: {err}")
                    self.log(f"  [{completed}/{len(modules)}] ❌ {mod_name} 失败: {err}", "WARN")
                else:
                    module_results[mod_name] = resp
                    self.log(f"  [{completed}/{len(modules)}] ✅ {mod_name} 完成", "INFO")

        if not module_results:
            return StepResult(ok=False, error=f"所有模块生成失败: {'; '.join(errors)}")

        # 合并所有模块的测试点，重新编号
        merged = self._merge_module_outputs(modules, module_results)
        self._write_output("testpoints.md", merged)

        # 全局自检
        score = self._self_check(merged)
        self.log(f"  全局自检评分: {score}/100", "INFO")

        count = len(re.findall(r"测试点\s*[\d.]+", merged))
        covered = len(module_results)
        total = len(modules)
        self.log(
            f"测试点梳理完成 — {count} 个测试点（{covered}/{total} 模块覆盖"
            + (f"，{len(errors)} 模块失败" if errors else "")
            + "）",
            "OK",
        )
        return StepResult(
            ok=True,
            data={
                "count": count,
                "check_score": score,
                "modules_covered": covered,
                "modules_total": total,
            },
        )

    def _merge_module_outputs(self, modules: list[dict], results: dict[str, str]) -> str:
        """合并各模块的测试点输出，全局重新编号。

        编号规则：
          模块序号.功能点序号.测试点序号
          如：1.1.1, 1.1.2, 1.2.1, 2.1.1, 2.1.2 ...
        """
        header = "# 测试点清单\n\n"
        sections: list[str] = []

        for mod_idx, module in enumerate(modules, 1):
            mod_name = module["name"]
            raw = results.get(mod_name)
            if not raw:
                continue

            renumbered = self._renumber_module(raw, mod_idx)
            sections.append(f"## 模块{self._cn_num(mod_idx)}：{mod_name}\n\n{renumbered}")

        return header + "\n\n".join(sections)

    @staticmethod
    def _renumber_module(text: str, mod_idx: int) -> str:
        """将模块内输出中的编号第一段替换为 mod_idx。

        匹配模式：N.M 或 N.M.K（功能点编号或测试点编号）
        替换：把第一个 N 换成 mod_idx

        例：mod_idx=2 时
          "测试点 1.1.1" → "测试点 2.1.1"
          "功能点 1.1"   → "功能点 2.1"
        """
        # 匹配：数字.数字 或 数字.数字.数字（后面不能跟更多数字）
        pattern = re.compile(r"(?<!\d)(\d+)(\.\d+(?:\.\d+)?)(?!\d)")

        def _replace(m: re.Match) -> str:
            return f"{mod_idx}{m.group(2)}"

        return pattern.sub(_replace, text)

    @staticmethod
    def _cn_num(n: int) -> str:
        """数字转中文（用于模块标题：一、二、三...）。"""
        cn = "零一二三四五六七八九十"
        if n <= 10:
            return cn[n]
        if n < 20:
            return f"十{cn[n - 10]}"
        return str(n)

    # ─── 模块提取 ───

    @staticmethod
    def _extract_modules(analysis: str) -> list[dict]:
        """从需求分析文档中提取模块列表。

        支持格式：
          ## 模块一：[模块名]  （step2 prompt 生成的格式）
          ## 模块1：[模块名]
          ## 1. [模块名]

        Returns:
            [{"name": "模块名", "content": "模块内需求分析文本"}]
        """
        # 匹配模块标题：## 模块X：名称 或 ## 模块X: 名称
        pattern = re.compile(r"^##\s*模块[一二三四五六七八九十0-9]+\s*[：:]\s*(.+)$", re.MULTILINE)
        matches = list(pattern.finditer(analysis))

        if not matches:
            # 备用格式：## 1. 模块名 或 ## 一、模块名
            pattern2 = re.compile(r"^##\s*[\d一二三四五六七八九十]+[.、]\s*(.+)$", re.MULTILINE)
            matches = list(pattern2.finditer(analysis))

        if not matches:
            return [{"name": "全部", "content": analysis}]

        modules: list[dict] = []
        for i, match in enumerate(matches):
            name = match.group(1).strip()
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(analysis)
            content = analysis[start:end].strip()
            modules.append({"name": name, "content": content})

        return modules

    # ─── 辅助方法 ───

    @staticmethod
    def _get_max_concurrent() -> int:
        """从配置读取 LLM 最大并发数。"""
        try:
            config = load_config()
            return int(config.get("pipeline", {}).get("max_concurrent", 2))
        except Exception:
            return 2

    def _self_check(self, response: str) -> int:
        """质量自检 — 返回评分 (0-100)。"""
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
        return check_result.get("score", 0)

    def _retry_if_needed(self, prompt: str, response: str, score: int) -> str:
        """自检不合格时重跑一次。"""
        if score >= 70:
            return response
        issues = self.self_check(
            response,
            criteria=(
                "1. 是否覆盖了需求分析中所有功能点？\n"
                "2. 每个功能点是否有正向、负向、边界、异常四个维度的测试点？\n"
                "3. 测试点的预期结果是否明确可判断？\n"
                "4. 测试数据是否具体可构造（而非'有效数据'这种模糊描述）？\n"
                "5. 每个测试点是否都包含「优先级」字段（取值 P0/P1/P2）？\n"
                "6. 优先级分配是否合理（P0 核心正向+安全，P1 重要负向边界，P2 性能/辅助）？"
            ),
        ).get("issues", [])
        self.log(f"  自检未通过，带着改进意见重跑 (问题: {len(issues)} 个)", "WARN")
        improvement_hint = "\n".join(f"- {issue}" for issue in issues)
        retry_prompt = (
            prompt
            + f"\n\n## 上次输出的问题（请务必改进）\n{improvement_hint}\n"
            + "\n请重新生成改进后的版本。"
        )
        try:
            return self.llm.chat(retry_prompt)
        except LLMError:
            self.log("  重跑失败，使用原始输出", "WARN")
            return response

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
