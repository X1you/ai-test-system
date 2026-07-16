#!/usr/bin/env python3
"""
Step 4: 生成测试用例（脚本步骤）

读取 testpoints.md → 调用 generate_excel.py + generate_xmind.py → 输出 testcases.xlsx/.xmind
"""

import subprocess
import sys
from pathlib import Path

from core.steps.base import BaseStep, StepResult

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_GEN_EXCEL = PROJECT_ROOT / "scripts" / "generate_excel.py"
SCRIPT_GEN_XMIND = PROJECT_ROOT / "scripts" / "generate_xmind.py"


class Step4Generate(BaseStep):
    step_id = 4
    step_name = "生成测试用例"
    output_file = "testcases.xlsx"

    def run(self, **kwargs) -> StepResult:  # type: ignore[override]
        """
        kwargs:
            dimensions: basic|all|positive,negative
            formats: excel|xmind|excel,xmind
        """
        dimensions = kwargs.get("dimensions", "basic")
        formats = kwargs.get("formats", "excel")

        self.log(f"Step {self.step_id}/7: {self.step_name}", "STEP")

        tp_path = self._out("testpoints.md")
        if not tp_path.exists():
            self.log("testpoints.md 不存在，无法生成用例", "ERR")
            return StepResult(ok=False, error="缺少测试点文件")

        case_count = 0

        # Excel
        if "excel" in formats:
            xlsx_path = self._out("testcases.xlsx")

            # 如果已有执行结果，不覆盖
            if xlsx_path.exists() and self._has_results(str(xlsx_path)):
                case_count = self._count_cases(xlsx_path)
                self.log(f"Excel 已存在（含执行结果），跳过 — {case_count} 条", "OK")
                return StepResult(ok=True, data={"case_count": case_count, "reused": True})

            if not SCRIPT_GEN_EXCEL.exists():
                self.log(f"脚本不存在: {SCRIPT_GEN_EXCEL}", "ERR")
                return StepResult(ok=False, error="generate_excel.py 不存在")

            result = subprocess.run(
                [sys.executable, str(SCRIPT_GEN_EXCEL),
                 str(tp_path), "-o", str(xlsx_path), "-d", dimensions],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                case_count = self._count_cases(str(xlsx_path))
                self.log(f"Excel 用例生成完成 — {case_count} 条", "OK")
            else:
                self.log(f"Excel 生成失败: {result.stderr[:200]}", "ERR")
                return StepResult(ok=False, error=result.stderr[:200])

        # XMind
        if "xmind" in formats:
            xmind_path = self._out("testcases.xmind")
            args = [sys.executable, str(SCRIPT_GEN_XMIND), str(tp_path), "-o", str(xmind_path)]
            if dimensions != "all":
                args.extend(["-d", dimensions])

            if SCRIPT_GEN_XMIND.exists():
                result = subprocess.run(
                    args, capture_output=True, text=True, timeout=120,
                )
                if result.returncode == 0:
                    self.log("XMind 用例生成完成", "OK")
                else:
                    self.log(f"XMind 生成失败: {result.stderr[:200]}", "WARN")
            else:
                self.log("XMind 脚本不存在，跳过", "WARN")

        return StepResult(ok=True, data={"case_count": case_count})

    @staticmethod
    def _count_cases(xlsx_path: str) -> int:
        try:
            from openpyxl import load_workbook
            wb = load_workbook(xlsx_path, data_only=True)
            ws = wb.active
            count = (ws.max_row - 1) if ws else 0
            wb.close()
            return max(count, 0)
        except Exception:
            return 0

    @staticmethod
    def _has_results(xlsx_path) -> bool:
        """检查 Excel 是否已填写执行结果"""
        try:
            from openpyxl import load_workbook
            wb = load_workbook(str(xlsx_path), data_only=True)
            ws = wb.active
            if not ws:
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
