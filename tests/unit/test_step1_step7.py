#!/usr/bin/env python3
"""
Step1 / Step7 单元测试

覆盖：
  - Step1Analysis._split_response (纯函数, 4 种解析策略)
  - Step1Analysis.run 错误路径 (文件不存在/无 LLM/无输入)
  - Step7Report.run 错误路径 (Excel 不存在/脚本不存在)

设计：传 llm=None 让 self_check 短路返回满分，用 tmp_path 隔离。
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# Step1Analysis._split_response
# ============================================================================


class TestSplitResponse:
    """测试 LLM 输出拆分（需求拆解 + 待确认清单）"""

    @pytest.mark.parametrize(
        "response,expected_clarification_nonempty",
        [
            # 策略1: 全等号分隔线 (>=10 个 =)
            ("需求拆解内容\n==========\n待确认事项内容", True),
            ("需求内容\n============\n澄清清单", True),
            # 策略2: ===CLARIFICATION=== 标记
            ("需求拆解\n===CLARIFICATION===\n待确认", True),
        ],
    )
    def test_split_strategies(self, response, expected_clarification_nonempty):
        from core.steps.step1_analysis import Step1Analysis

        analysis, clarification = Step1Analysis._split_response(response)
        assert analysis  # 需求拆解部分不应为空
        if expected_clarification_nonempty:
            assert clarification, f"待确认清单应为非空: {response!r}"

    def test_split_by_equals_separator(self):
        """策略1：>=10 个等号分隔线正确拆分"""
        from core.steps.step1_analysis import Step1Analysis

        response = "这是需求拆解\n这是第二行\n==========\n这是待确认"
        analysis, clarification = Step1Analysis._split_response(response)
        assert "需求拆解" in analysis
        assert "待确认" in clarification
        # 等号分隔线本身不应出现在任一部分
        assert "==========" not in analysis
        assert "==========" not in clarification

    def test_split_by_clarification_marker(self):
        """策略2：===CLARIFICATION=== 标记正确拆分"""
        from core.steps.step1_analysis import Step1Analysis

        response = "需求分析内容\n===CLARIFICATION===\n1. **确认点A**\n2. **确认点B**"
        analysis, clarification = Step1Analysis._split_response(response)
        assert analysis == "需求分析内容"
        assert "确认点A" in clarification

    def test_split_by_two_h1_headers(self):
        """策略3：两个一级标题(# )拆分"""
        from core.steps.step1_analysis import Step1Analysis

        response = "# 需求拆解\n内容A\n# 待确认事项\n内容B"
        analysis, clarification = Step1Analysis._split_response(response)
        assert "需求拆解" in analysis
        assert "待确认事项" in clarification

    def test_no_split_returns_all_as_analysis(self):
        """策略4：无法识别分隔符 → 全部当作需求拆解，待确认为空"""
        from core.steps.step1_analysis import Step1Analysis

        response = "纯需求内容，没有分隔符也没有多个标题"
        analysis, clarification = Step1Analysis._split_response(response)
        assert analysis == response
        assert clarification == ""

    def test_empty_response(self):
        """空响应 → 两部分都为空（strip 后）"""
        from core.steps.step1_analysis import Step1Analysis

        analysis, clarification = Step1Analysis._split_response("")
        assert analysis == ""
        assert clarification == ""

    def test_only_separator_with_newlines(self):
        """分隔线前后都有换行 → 拆分为两个空部分"""
        from core.steps.step1_analysis import Step1Analysis

        response = "\n==========\n"
        analysis, clarification = Step1Analysis._split_response(response)
        # 前后换行都有，策略1匹配，两部分 strip 后为空
        assert analysis == ""
        assert clarification == ""

    def test_separator_at_start_no_leading_newline(self):
        """分隔线在开头（无前导换行）→ 策略1不触发，全部当 analysis"""
        from core.steps.step1_analysis import Step1Analysis

        response = "==========\n"
        analysis, clarification = Step1Analysis._split_response(response)
        # 策略1要求 \n={10,}\n，开头缺前导\n，不匹配 → 策略4
        assert clarification == ""

    def test_short_equals_not_treated_as_separator(self):
        """<10 个等号不视为分隔线（如表格对齐线）"""
        from core.steps.step1_analysis import Step1Analysis

        # 9 个等号不应触发策略1
        response = "内容A\n=========\n内容B"
        analysis, clarification = Step1Analysis._split_response(response)
        # 不应被等号拆分
        assert "=========" in analysis or "=========" in clarification


# ============================================================================
# Step1Analysis.run 错误路径
# ============================================================================


class TestStep1RunErrorPaths:
    """测试 Step1 的错误处理路径（不调用真实 LLM）"""

    def _make_step(self, tmp_path):
        from core.steps.step1_analysis import Step1Analysis

        # llm=None → self_check 短路返回满分，不会调用 LLM
        return Step1Analysis(str(tmp_path), config={}, llm=None)

    def test_no_input_returns_error(self, tmp_path):
        """未提供需求文档（path 和 text 都为空）→ 报错"""
        step = self._make_step(tmp_path)
        result = step.run()
        assert result.ok is False
        assert "需求文档" in result.error or "未提供" in result.error

    def test_nonexistent_file_returns_error(self, tmp_path):
        """需求文档路径不存在 → 报错"""
        step = self._make_step(tmp_path)
        result = step.run(requirements_path=str(tmp_path / "nonexistent.md"))
        assert result.ok is False
        assert "不存在" in result.error

    def test_no_llm_returns_error(self, tmp_path):
        """有需求文本但无 LLM → 报错"""
        step = self._make_step(tmp_path)
        result = step.run(requirements_text="# 某需求")
        assert result.ok is False
        assert "LLM" in result.error


# ============================================================================
# Step7Report.run 错误路径
# ============================================================================


class TestStep7RunErrorPaths:
    """测试 Step7 的错误处理路径（不调用真实脚本）"""

    def _make_step(self, tmp_path):
        from core.steps.step7_report import Step7Report

        return Step7Report(str(tmp_path), config={})

    def test_no_excel_returns_error(self, tmp_path):
        """testcases.xlsx 不存在 → 报错"""
        step = self._make_step(tmp_path)
        result = step.run()
        assert result.ok is False
        assert "Excel" in result.error or "xlsx" in result.error.lower()

    def test_excel_exists_but_script_missing(self, tmp_path, monkeypatch):
        """Excel 存在但脚本不存在 → 报错

        通过 monkeypatch 让 SCRIPT_GEN_REPORT 指向不存在的路径。
        """
        from core.steps import step7_report

        # 创建假的 xlsx 触发后续检查
        (tmp_path / "testcases.xlsx").write_bytes(b"fake")

        # 让脚本路径指向不存在的地方
        monkeypatch.setattr(step7_report, "SCRIPT_GEN_REPORT", tmp_path / "no_script.py")

        step = self._make_step(tmp_path)
        result = step.run()
        assert result.ok is False
        assert "generate_report" in result.error or "脚本" in result.error

    def test_script_subprocess_failure(self, tmp_path, monkeypatch):
        """脚本执行失败（returncode != 0）→ 报错"""
        from core.steps import step7_report

        (tmp_path / "testcases.xlsx").write_bytes(b"fake")
        # 指向一个存在的"脚本"（随便一个 .py 文件）
        fake_script = tmp_path / "fake_script.py"
        fake_script.write_text("# fake")
        monkeypatch.setattr(step7_report, "SCRIPT_GEN_REPORT", fake_script)

        # mock subprocess.run 返回失败
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "脚本执行出错"
        mock_result.stdout = ""
        monkeypatch.setattr(step7_report.subprocess, "run", lambda *a, **kw: mock_result)

        step = self._make_step(tmp_path)
        result = step.run()
        assert result.ok is False
        assert "脚本执行出错" in result.error or "出错" in result.error

    def test_script_success(self, tmp_path, monkeypatch):
        """脚本执行成功 → ok=True"""
        from core.steps import step7_report

        (tmp_path / "testcases.xlsx").write_bytes(b"fake")
        fake_script = tmp_path / "fake_script.py"
        fake_script.write_text("# fake")
        monkeypatch.setattr(step7_report, "SCRIPT_GEN_REPORT", fake_script)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_result.stdout = "通过: 45 个 (90.0%)"
        monkeypatch.setattr(step7_report.subprocess, "run", lambda *a, **kw: mock_result)

        step = self._make_step(tmp_path)
        result = step.run()
        assert result.ok is True
