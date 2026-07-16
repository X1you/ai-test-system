#!/usr/bin/env python3
"""
Step 7: 生成测试报告（脚本步骤）

读取已执行的 testcases.xlsx → 调用 generate_report.py → 输出 test_report.md
"""

import re
import subprocess
import sys
from pathlib import Path

from core.steps.base import BaseStep, StepResult

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_GEN_REPORT = PROJECT_ROOT / "scripts" / "generate_report.py"


class Step7Report(BaseStep):
    step_id = 7
    step_name = "生成测试报告"
    output_file = "test_report.md"

    def run(self, **kwargs) -> StepResult:  # type: ignore[override]
        self.log(f"Step {self.step_id}/7: {self.step_name}", "STEP")

        xlsx_path = self._out("testcases.xlsx")
        report_path = self._out("test_report.md")

        if not xlsx_path.exists():
            self.log("testcases.xlsx 不存在", "ERR")
            return StepResult(ok=False, error="缺少测试用例 Excel")

        if not SCRIPT_GEN_REPORT.exists():
            self.log(f"脚本不存在: {SCRIPT_GEN_REPORT}", "ERR")
            return StepResult(ok=False, error="generate_report.py 不存在")

        result = subprocess.run(
            [sys.executable, str(SCRIPT_GEN_REPORT),
             str(xlsx_path), "-o", str(report_path)],
            capture_output=True, text=True, timeout=60,
        )

        if result.returncode != 0:
            self.log(f"报告生成失败: {result.stderr[:200]}", "ERR")
            return StepResult(ok=False, error=result.stderr[:200])

        # 提取通过率
        pass_match = re.search(r"通过: (\d+) 个 \(([0-9.]+)%\)", result.stdout)
        if pass_match:
            self.log(f"测试报告生成完成 — 通过率 {pass_match.group(2)}%", "OK")
        else:
            self.log("测试报告生成完成", "OK")

        return StepResult(ok=True)
