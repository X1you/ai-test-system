#!/usr/bin/env python3
"""
Step 6: 人工执行测试（人工步骤）

不自动执行，只检测 Excel 是否已填写执行结果。
"""

from core.steps.base import BaseStep, StepResult


class Step6HumanTest(BaseStep):
    step_id = 6
    step_name = "执行测试（人工）"
    output_file = "testcases.xlsx"

    def run(self, **kwargs) -> StepResult:  # type: ignore[override]
        """检测 Excel 是否已填写执行结果"""
        self.log(f"Step {self.step_id}/7: {self.step_name}", "HUMAN")

        xlsx_path = self._out("testcases.xlsx")
        self.log(f"  请打开 {xlsx_path} 执行测试", "HUMAN")
        self.log('  在「执行结果」列填写：通过/失败/阻塞/跳过', "HUMAN")

        if self._check_has_results(str(xlsx_path)):
            self.log("检测到执行结果已填写，继续下一步", "OK")
            return StepResult(ok=True)

        self.log("⏸️  等待人工执行测试，填写完成后重新运行", "HUMAN")
        return StepResult(ok=False, error="等待人工执行测试", human=True)

    @staticmethod
    def _check_has_results(xlsx_path: str) -> bool:
        try:
            from openpyxl import load_workbook
            wb = load_workbook(xlsx_path, data_only=True)
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
