#!/usr/bin/env python3
"""
单元测试 — ExcelReader（generate_report.py）
覆盖：表头模糊匹配、执行结果归一化、数据行读取、边界条件
"""

import sys
import tempfile
from pathlib import Path

import pytest

# 延迟导入：generate_report.py 在 import 时检查 openpyxl
scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

from generate_report import ExcelReader

# ═══════════════════════════════════════════════════════════════
# 辅助函数：构造测试用 Excel
# ═══════════════════════════════════════════════════════════════

def _make_test_excel(headers, rows, tmpdir):
    """用 openpyxl 构造测试 Excel 文件"""
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    path = str(Path(tmpdir) / "test_cases.xlsx")
    wb.save(path)
    return path


# ═══════════════════════════════════════════════════════════════
# 表头匹配
# ═══════════════════════════════════════════════════════════════

class TestColumnMatching:
    """测试表头模糊匹配"""

    def test_exact_match(self):
        reader = ExcelReader()
        assert reader._match_column("用例编号") == "id"
        assert reader._match_column("所属模块") == "module"
        assert reader._match_column("执行结果") == "result"
        assert reader._match_column("预期结果") == "expected"

    def test_fuzzy_match(self):
        reader = ExcelReader()
        # 部分匹配：「用例执行结果」包含「执行结果」
        assert reader._match_column("用例执行结果") == "result"
        assert reader._match_column("模块名称") == "module"

    def test_english_match(self):
        reader = ExcelReader()
        assert reader._match_column("id") == "id"
        assert reader._match_column("module") == "module"
        assert reader._match_column("priority") == "priority"

    def test_whitespace_punctuation(self):
        reader = ExcelReader()
        # 含空格和括号
        assert reader._match_column("用例编号 ") == "id"
        assert reader._match_column("（模块）") == "module"
        assert reader._match_column("【功能点】") == "feature"

    def test_no_match(self):
        reader = ExcelReader()
        assert reader._match_column("不存在的列名") == ""
        assert reader._match_column("") == ""
        assert reader._match_column(None) == ""


# ═══════════════════════════════════════════════════════════════
# 执行结果归一化
# ═══════════════════════════════════════════════════════════════

class TestResultNormalize:
    """测试执行结果归一化"""

    def test_chinese_status(self):
        reader = ExcelReader()
        assert reader._normalize_result("通过") == "pass"
        assert reader._normalize_result("失败") == "fail"
        assert reader._normalize_result("阻塞") == "block"
        assert reader._normalize_result("跳过") == "skip"

    def test_english_status(self):
        reader = ExcelReader()
        assert reader._normalize_result("pass") == "pass"
        assert reader._normalize_result("FAIL") == "fail"
        assert reader._normalize_result("Blocked") == "block"

    def test_emoji_status(self):
        reader = ExcelReader()
        assert reader._normalize_result("✅") == "pass"
        assert reader._normalize_result("❌") == "fail"
        assert reader._normalize_result("⛔") == "block"
        assert reader._normalize_result("⏭️") == "skip"

    def test_empty_and_none(self):
        reader = ExcelReader()
        assert reader._normalize_result("") == "not_run"
        assert reader._normalize_result(None) == "not_run"
        assert reader._normalize_result("未执行") == "not_run"
        assert reader._normalize_result("—") == "not_run"

    def test_unknown_value(self):
        reader = ExcelReader()
        assert reader._normalize_result("未知状态xyz") == "not_run"

    def test_case_insensitive(self):
        reader = ExcelReader()
        assert reader._normalize_result("Pass") == "pass"
        assert reader._normalize_result("PASS") == "pass"
        assert reader._normalize_result("Skip") == "skip"


# ═══════════════════════════════════════════════════════════════
# Excel 文件读取
# ═══════════════════════════════════════════════════════════════

class TestExcelRead:
    """测试 Excel 文件读取"""

    def test_read_standard_format(self):
        """测试标准 12 列格式读取"""
        headers = ["用例编号", "所属模块", "功能点", "测试维度", "用例标题",
                   "优先级", "前置条件", "测试步骤", "测试数据", "预期结果", "备注", "执行结果"]
        rows = [
            ["TC001", "用户管理", "用户注册", "正向", "正常注册", "P0", "无", "1.打开页面", "手机号", "注册成功", "", "通过"],
            ["TC002", "用户管理", "用户注册", "负向", "重复注册", "P1", "无", "1.打开页面", "已注册", "提示重复", "", "失败"],
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _make_test_excel(headers, rows, tmpdir)
            reader = ExcelReader()
            test_cases, metadata = reader.read(path)

        assert len(test_cases) == 2
        assert test_cases[0]["id"] == "TC001"
        assert test_cases[0]["module"] == "用户管理"
        assert test_cases[0]["result"] == "pass"
        assert test_cases[1]["result"] == "fail"
        assert metadata["has_result_col"] is True
        assert metadata["total_rows"] == 2

    def test_read_with_partial_headers(self):
        """测试部分列名匹配"""
        headers = ["编号", "模块", "标题", "结果"]
        rows = [
            ["TC001", "订单", "下单", "通过"],
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _make_test_excel(headers, rows, tmpdir)
            reader = ExcelReader()
            test_cases, metadata = reader.read(path)

        assert len(test_cases) == 1
        assert test_cases[0]["id"] == "TC001"
        assert test_cases[0]["result"] == "pass"

    def test_read_empty_excel(self):
        """测试只有表头没有数据行"""
        headers = ["用例编号", "所属模块", "执行结果"]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _make_test_excel(headers, [], tmpdir)
            reader = ExcelReader()
            test_cases, metadata = reader.read(path)

        assert len(test_cases) == 0
        assert metadata["total_rows"] == 0

    def test_read_no_result_column(self):
        """测试没有执行结果列"""
        headers = ["用例编号", "所属模块", "用例标题"]
        rows = [["TC001", "用户", "测试"]]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _make_test_excel(headers, rows, tmpdir)
            reader = ExcelReader()
            test_cases, metadata = reader.read(path)

        assert len(test_cases) == 1
        assert metadata["has_result_col"] is False
        # 没有结果列时，result 默认为 not_run
        assert test_cases[0]["result"] == "not_run"

    def test_read_unrecognizable_headers(self):
        """测试完全无法识别的表头"""
        headers = ["aaa", "bbb", "ccc"]
        rows = [["x", "y", "z"]]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _make_test_excel(headers, rows, tmpdir)
            reader = ExcelReader()
            test_cases, metadata = reader.read(path)

        assert len(test_cases) == 0
        assert metadata == {}

    def test_read_null_values(self):
        """测试空值处理"""
        headers = ["用例编号", "所属模块", "执行结果"]
        rows = [
            ["TC001", None, "通过"],
            [None, "用户", None],
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _make_test_excel(headers, rows, tmpdir)
            reader = ExcelReader()
            test_cases, _ = reader.read(path)

        assert len(test_cases) == 2
        # None 值应该转为空字符串
        assert test_cases[0]["module"] == ""
        assert test_cases[1]["id"] == ""
        assert test_cases[1]["result"] == "not_run"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
