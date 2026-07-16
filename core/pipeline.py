#!/usr/bin/env python3
"""
Pipeline 引擎 — 独立版（v2.0）

自动串联 7 步：
  Step 1  需求分析 (AI)
  Step 2  知识库检索 (脚本)
  Step 3  测试点梳理 (AI)
  Step 4  生成测试用例 (脚本)
  Step 5  用例评审 (AI)
  Step 6  执行测试 (人工)
  Step 7  生成测试报告 (脚本)

支持：断点续跑、人工检查点、知识库自动集成、LLM 自检。
"""

import json
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from core.llm_client import LLMClient, LLMError
from core.steps.base import StepResult
from core.steps.step1_analysis import Step1Analysis
from core.steps.step2_kb_search import Step2KBSearch
from core.steps.step3_testpoints import Step3Testpoints
from core.steps.step4_generate import Step4Generate
from core.steps.step5_review import Step5Review
from core.steps.step6_human_test import Step6HumanTest
from core.steps.step7_report import Step7Report

STATE_FILE = "_pipeline_state.json"


class Pipeline:
    """全流程 Pipeline 引擎"""

    def __init__(self, config: dict, output_dir: str):
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.llm: LLMClient | None = None

        # WebUI 回调钩子（CLI 模式为 None，不影响行为）
        self.on_log: Callable | None = None         # fn(level, msg)
        self.on_step_done: Callable | None = None   # fn(step_id, result_dict)

    def _notify_log(self, level: str, msg: str):
        """日志回调通知 — 同时输出到结构化日志和 WebUI 回调"""
        from core.logger import get_logger
        logger = get_logger("pipeline")
        logger.info("step_log", level=level, message=msg)
        if self.on_log:
            self.on_log(level, msg)

    def _init_llm(self):
        """初始化 LLM 客户端"""
        if self.llm:
            return
        try:
            self.llm = LLMClient(self.config["llm"])
        except LLMError as e:
            print(f"❌ LLM 初始化失败: {e}", file=sys.stderr)
            raise

    # ─── 状态管理 ───

    def load_state(self) -> dict:
        path = self.output_dir / STATE_FILE
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {
            "started": datetime.now().isoformat(),
            "completed_steps": [],
            "step_results": {},
            "mode": "semi",
            "requirements_file": "",
        }

    def _check_skip(self, state: dict, step_id: int, output_file: str) -> bool:
        """检查是否可跳过：已完成且输出文件存在"""
        return self.is_done(state, step_id) and (self.output_dir / output_file).exists()

    def _has_results(self, xlsx_path: Path) -> bool:
        """检查 Excel 是否已填写执行结果"""
        try:
            from openpyxl import load_workbook
            wb = load_workbook(str(xlsx_path), data_only=True)
            ws = wb.active
            if not ws:
                wb.close()
                return False
            result_col = None
            for col in range(1, ws.max_column + 1):
                header = str(ws.cell(row=1, column=col).value or "").strip()
                if header == "执行结果" or ("执行" in header and "结果" in header):
                    result_col = col
                    break
            if not result_col:
                wb.close()
                return False
            filled = 0
            for row in range(2, ws.max_row + 1):
                val = str(ws.cell(row=row, column=result_col).value or "").strip()
                if val:
                    filled += 1
            wb.close()
            return filled > 0
        except Exception:
            return False

    def save_state(self, state: dict):
        state["updated"] = datetime.now().isoformat()
        path = self.output_dir / STATE_FILE
        path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def mark_done(self, state: dict, step_id: int, result: StepResult):
        if step_id not in state["completed_steps"]:
            state["completed_steps"].append(step_id)
        result_info = {
            "ok": result.ok,
            "data": result.data,
        }
        state["step_results"][str(step_id)] = result_info
        self.save_state(state)

        # 通知 WebUI 回调
        if self.on_step_done:
            self.on_step_done(step_id, result_info)

    @staticmethod
    def is_done(state: dict, step_id: int) -> bool:
        return step_id in state["completed_steps"]

    # ─── 执行 ───

    def run(
        self,
        requirements_file: str,
        mode: str = "semi",
        dimensions: str = "basic",
        formats: str = "excel",
    ) -> dict:
        """
        执行全流程 Pipeline

        Args:
            requirements_file: 需求文档路径
            mode: auto | semi | step
            dimensions: basic | all | positive,negative
            formats: excel | xmind | excel,xmind

        Returns:
            最终状态 dict
        """
        state = self.load_state()
        state["mode"] = mode
        state["requirements_file"] = requirements_file
        self.save_state(state)

        print()
        print("═" * 60)
        print(f"  🚀 全流程 Pipeline 启动 — 模式: {mode}")
        print(f"  📂 输出目录: {self.output_dir}")
        print(f"  📄 需求文档: {requirements_file}")
        if self.llm:
            print(f"  🤖 LLM: {self.llm.provider} / {self.llm.model}")
        print("═" * 60)
        print()

        out = str(self.output_dir)
        config = self.config

        # ─── Step 1: 需求分析 ───
        if self._check_skip(state, 1, "requirements_analysis.md"):
            print("✅ Step 1 已完成，跳过\n")
        else:
            self._init_llm()
            r = Step1Analysis(out, config, self.llm).run(
                requirements_path=requirements_file
            )
            if r.ok:
                self.mark_done(state, 1, r)
                print()
                if mode == "step":
                    if not self._pause("Step 1"):
                        return state
            elif mode in ("semi", "step"):
                print("⏸️  Step 1 需要确认后继续")
                return state
            else:
                print("❌ Step 1 失败，终止")
                return state

        # ─── Step 2: 知识库检索 ───
        if self._check_skip(state, 2, "knowledge-context.md"):
            print("✅ Step 2 已完成，跳过\n")
        else:
            analysis = (self.output_dir / "requirements_analysis.md").read_text(
                encoding="utf-8"
            )
            r = Step2KBSearch(out, config, self.llm).run(
                requirements_analysis=analysis
            )
            self.mark_done(state, 2, r)
            print()

        # ─── Step 3: 测试点梳理 ───
        if self._check_skip(state, 3, "testpoints.md"):
            print("✅ Step 3 已完成，跳过\n")
        else:
            self._init_llm()
            analysis = (self.output_dir / "requirements_analysis.md").read_text(
                encoding="utf-8"
            )
            kb_context = self._read_kb_context()
            r = Step3Testpoints(out, config, self.llm).run(
                requirements_analysis=analysis,
                kb_context=kb_context,
                dimensions=dimensions,
            )
            if r.ok:
                self.mark_done(state, 3, r)
                print()
                if mode in ("semi", "step"):
                    if not self._pause("Step 3"):
                        return state
            else:
                print("⏸️  Step 3 失败/需确认")
                return state

        # ─── Step 4: 生成测试用例 ───
        if self._check_skip(state, 4, "testcases.xlsx"):
            print("✅ Step 4 已完成，跳过\n")
        else:
            r = Step4Generate(out, config).run(
                dimensions=dimensions, formats=formats
            )
            if r.ok:
                self.mark_done(state, 4, r)
                print()
            else:
                print("❌ Step 4 失败，终止")
                return state

        # ─── Step 5: 用例评审 ───
        if self._check_skip(state, 5, "test_case_review_report.md"):
            print("✅ Step 5 已完成，跳过\n")
        else:
            self._init_llm()
            kb_context = self._read_kb_context()
            r = Step5Review(out, config, self.llm).run(kb_context=kb_context)
            if r.ok:
                self.mark_done(state, 5, r)
                print()
                if mode in ("semi", "step"):
                    if not self._pause("Step 5"):
                        return state
            else:
                print("⏸️  Step 5 需确认")
                return state

        # ─── Step 6: 人工执行测试 ───
        xlsx_path = self.output_dir / "testcases.xlsx"
        # Step 6 跳过检查：如果已完成且 Excel 有执行结果则跳过
        if self.is_done(state, 6) and xlsx_path.exists() and self._has_results(xlsx_path):
            print("✅ Step 6 已完成，跳过\n")
        else:
            r = Step6HumanTest(out, config).run()
            if r.ok:
                self.mark_done(state, 6, r)
                print()
            else:
                print("⏸️  Pipeline 暂停 — 等待人工执行测试")
                print(f"    文件: {self.output_dir / 'testcases.xlsx'}")
                print(f"    填写完成后重新运行: python cli.py resume -o {self.output_dir}")
                return state

        # ─── Step 7: 生成报告 ───
        if self._check_skip(state, 7, "test_report.md"):
            print("✅ Step 7 已完成，跳过\n")
        else:
            r = Step7Report(out, config).run()
            if r.ok:
                self.mark_done(state, 7, r)
                print()
            else:
                print("❌ Step 7 失败，终止")
                return state

        # ─── 完成 ───
        self._print_summary(state)
        return state

    def resume(self, dimensions: str = "basic", formats: str = "excel"):
        """从断点继续"""
        state = self.load_state()
        if not state.get("requirements_file"):
            print("❌ 未找到 pipeline 状态，请先 run", file=sys.stderr)
            return

        print()
        print(f"▶  继续执行 — 已完成: {state['completed_steps']}")
        print()

        self.run(
            state["requirements_file"],
            mode=state.get("mode", "semi"),
            dimensions=dimensions,
            formats=formats,
        )

    def status(self):
        """查看状态"""
        state = self.load_state()
        print()
        print("═" * 60)
        print("  📊 Pipeline 状态")
        print("═" * 60)
        print()
        print(f"  启动时间: {state.get('started', 'N/A')[:19]}")
        print(f"  最后更新: {state.get('updated', 'N/A')[:19]}")
        print(f"  执行模式: {state.get('mode', 'N/A')}")
        print(f"  需求文档: {state.get('requirements_file', 'N/A')}")
        print()

        steps = [
            (1, "需求分析", "requirements_analysis.md"),
            (2, "知识库检索", "knowledge-context.md"),
            (3, "测试点梳理", "testpoints.md"),
            (4, "生成测试用例", "testcases.xlsx"),
            (5, "用例评审", "test_case_review_report.md"),
            (6, "执行测试", "testcases.xlsx"),
            (7, "生成测试报告", "test_report.md"),
        ]

        print("  步骤                    │ 状态   │ 输出文件")
        print("  " + "─" * 56)
        for sid, name, fname in steps:
            done = sid in state["completed_steps"]
            exists = (self.output_dir / fname).exists()
            icon = "✅" if done else ("📁" if exists else "⬜")
            st = "已完成" if done else ("文件存在" if exists else "待执行")
            print(f"  {icon} Step {sid}. {name:<16} │ {st:<6} │ {fname}")

        done_count = len(state["completed_steps"])
        print()
        print(f"  进度: {done_count}/7 ({done_count / 7 * 100:.0f}%)")
        print()

    # ─── 内部工具 ───

    def _read_kb_context(self) -> str:
        path = self.output_dir / "knowledge-context.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    @staticmethod
    def _pause(step_name: str) -> bool:
        """semi/step 模式暂停确认（CLI 模式下自动跳过）"""
        return True  # CLI 直接继续；WebUI 会覆盖此方法

    def _print_summary(self, state: dict):
        print()
        print("═" * 60)
        print("  ✅ 全流程 Pipeline 执行完成！")
        print("═" * 60)
        print()
        print(f"  {'步骤':<22} │ {'状态':<6} │ 输出文件")
        print(f"  {'─' * 56}")
        steps = [
            (1, "需求分析", "requirements_analysis.md"),
            (2, "知识库检索", "knowledge-context.md"),
            (3, "测试点梳理", "testpoints.md"),
            (4, "生成测试用例", "testcases.xlsx"),
            (5, "用例评审", "test_case_review_report.md"),
            (6, "执行测试", "testcases.xlsx"),
            (7, "生成测试报告", "test_report.md"),
        ]
        for sid, name, fname in steps:
            done = sid in state["completed_steps"]
            icon = "✅" if done else "⬜"
            st = "完成" if done else "待执行"
            print(f"  {icon} {sid}. {name:<18} │ {st:<4} │ {fname}")

        print()
        print(f"  📁 输出目录: {self.output_dir}/")

        if self.llm:
            stats = self.llm.stats
            print(
                f"  🤖 LLM 调用: {stats['call_count']} 次, "
                f"{stats['total_tokens']} tokens ({stats['provider']})"
            )
