#!/usr/bin/env python3
"""
Step5Review 补充单元测试。

现有 test_step_pure_functions.py 已覆盖 _extract_score / _score_to_grade。
本文件补充：
  - _read_testcases_as_text: 读取 xlsx 转 Markdown 表格（无文件/空表/正常）
  - run() 错误路径: 缺少测试用例 / 无 LLM

用 tmp_path 隔离，openpyxl 真实读写（非 mock），覆盖实际 I/O 路径。
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# Step5Review._read_testcases_as_text
# ============================================================================


class TestReadTestcasesAsText:
    """测试 Excel → 文本转换（_read_testcases_as_text）"""

    def _make_step(self, tmp_path):
        from core.steps.step5_review import Step5Review

        return Step5Review(str(tmp_path), config={}, llm=None)

    def _make_xlsx(self, path, headers, rows):
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        assert ws is not None
        ws.append(headers)
        for row in rows:
            ws.append(row)
        wb.save(str(path))
        wb.close()

    def test_no_file_returns_empty(self, tmp_path):
        """testcases.xlsx 不存在 → 空字符串"""
        step = self._make_step(tmp_path)
        assert step._read_testcases_as_text() == ""

    def test_normal_excel(self, tmp_path):
        """正常 Excel → Markdown 表格行"""
        step = self._make_step(tmp_path)
        xlsx = tmp_path / "testcases.xlsx"
        self._make_xlsx(
            xlsx,
            ["用例编号", "标题", "执行结果"],
            [["TC-1", "登录成功", ""], ["TC-2", "密码错误", ""]],
        )
        text = step._read_testcases_as_text()
        assert "| 用例编号 |" in text
        assert "TC-1" in text
        assert "登录成功" in text
        assert "TC-2" in text

    def test_only_header_row(self, tmp_path):
        """仅有表头、无数据行 → 返回表头行（非空）"""
        step = self._make_step(tmp_path)
        xlsx = tmp_path / "testcases.xlsx"
        self._make_xlsx(xlsx, ["编号", "标题"], [])
        text = step._read_testcases_as_text()
        assert "编号" in text

    def test_long_cell_truncated(self, tmp_path):
        """超长单元格内容被截断到 80 字符（防超 token）"""
        step = self._make_step(tmp_path)
        xlsx = tmp_path / "testcases.xlsx"
        long_text = "A" * 200
        self._make_xlsx(xlsx, ["编号", "步骤"], [["TC-1", long_text]])
        text = step._read_testcases_as_text()
        # 80 字符的 "A" 不应出现 200 个
        assert text.count("A") == 80

    def test_newline_in_cell_normalized(self, tmp_path):
        """单元格内换行被替换为空格（避免破坏 Markdown 表格）"""
        step = self._make_step(tmp_path)
        xlsx = tmp_path / "testcases.xlsx"
        self._make_xlsx(
            xlsx,
            ["编号", "步骤"],
            [["TC-1", "步骤一\n步骤二"]],
        )
        text = step._read_testcases_as_text()
        # 换行应被替换，步骤内容保留在同一表格行
        assert "步骤一 步骤二" in text


# ============================================================================
# Step5Review.run 错误路径
# ============================================================================


class TestStep5RunErrorPaths:
    """测试 Step5 run() 的错误处理（不调用真实 LLM）"""

    def _make_step(self, tmp_path):
        from core.steps.step5_review import Step5Review

        return Step5Review(str(tmp_path), config={}, llm=None)

    def test_no_test_cases_no_excel(self, tmp_path):
        """无 test_cases 且无 xlsx → 缺少测试用例数据"""
        step = self._make_step(tmp_path)
        result = step.run()
        assert result.ok is False
        assert "测试用例" in result.error

    def test_has_cases_but_no_llm(self, tmp_path):
        """有 test_cases 但无 LLM → 需要 LLM 客户端"""
        step = self._make_step(tmp_path)
        result = step.run(test_cases="| 编号 | 标题 |\n| TC-1 | 登录 |")
        assert result.ok is False
        assert "LLM" in result.error

    def test_read_excel_but_no_llm(self, tmp_path):
        """能从 xlsx 读到用例文本，但无 LLM → 报需 LLM（而非缺用例）

        验证 _read_testcases_as_text 与 run 的衔接：
        xlsx 存在 → _read_testcases_as_text 返回非空 → 走到 llm 检查。
        """
        from openpyxl import Workbook

        xlsx = tmp_path / "testcases.xlsx"
        wb = Workbook()
        ws = wb.active
        assert ws is not None
        ws.append(["编号", "标题"])
        ws.append(["TC-1", "登录"])
        wb.save(str(xlsx))
        wb.close()

        step = self._make_step(tmp_path)
        result = step.run()
        assert result.ok is False
        # 关键：走到 LLM 检查，而非"缺少测试用例"
        assert "LLM" in result.error
