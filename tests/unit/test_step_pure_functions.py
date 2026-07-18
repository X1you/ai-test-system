#!/usr/bin/env python3
"""
core/steps/ 纯函数单元测试

覆盖 step3/step5/step6 中无 LLM 依赖、无副作用的工具方法：
  - Step3Testpoints._build_dimensions_text  (维度配置解析)
  - Step5Review._extract_score / _score_to_grade  (评分提取与分级)
  - Step6HumanTest._check_has_results  (Excel 执行结果检测)
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# Step3Testpoints._build_dimensions_text
# ============================================================================


class TestBuildDimensionsText:
    """测试维度配置文本生成"""

    def test_all_dimensions(self):
        from core.steps.step3_testpoints import Step3Testpoints

        text = Step3Testpoints._build_dimensions_text("all")
        assert "6 个" in text
        for dim in ["正向测试", "负向测试", "边界测试", "异常测试", "性能测试", "安全测试"]:
            assert f"✅ {dim}" in text
        assert "其他维度不需要生成" in text

    def test_basic_dimensions(self):
        from core.steps.step3_testpoints import Step3Testpoints

        text = Step3Testpoints._build_dimensions_text("basic")
        assert "4 个" in text
        for dim in ["正向测试", "负向测试", "边界测试", "异常测试"]:
            assert f"✅ {dim}" in text
        # basic 不含性能/安全
        assert "性能测试" not in text
        assert "安全测试" not in text

    def test_custom_dimensions(self):
        from core.steps.step3_testpoints import Step3Testpoints

        text = Step3Testpoints._build_dimensions_text("positive,negative")
        assert "2 个" in text
        assert "✅ 正向测试" in text
        assert "✅ 负向测试" in text
        assert "边界测试" not in text

    def test_custom_dimensions_with_whitespace(self):
        """逗号分隔的维度带空格应被正确 trim"""
        from core.steps.step3_testpoints import Step3Testpoints

        text = Step3Testpoints._build_dimensions_text("positive, negative , boundary")
        assert "3 个" in text
        assert "正向测试" in text
        assert "负向测试" in text
        assert "边界测试" in text

    def test_custom_dimensions_with_unknown_key(self):
        """未知维度 key 应原样保留"""
        from core.steps.step3_testpoints import Step3Testpoints

        text = Step3Testpoints._build_dimensions_text("positive,custom-thing")
        assert "✅ 正向测试" in text
        assert "✅ custom-thing" in text

    def test_empty_dimensions_string(self):
        """空字符串 → 1 个空维度项（边界 case）"""
        from core.steps.step3_testpoints import Step3Testpoints

        text = Step3Testpoints._build_dimensions_text("")
        # "".split(",") == [''] → 1 个空项
        assert "1 个" in text


# ============================================================================
# Step5Review._extract_score / _score_to_grade
# ============================================================================


class TestExtractScore:
    """测试评审报告评分提取（多种格式）"""

    @pytest.mark.parametrize(
        "report_text,expected",
        [
            # 表格格式：| **总计** | **100** | **85** |
            ("| 维度 | 满分 | 得分 |\n| **总计** | **100** | **85** |", 85),
            # 纯总分行（带加粗）
            ("| **总计** | **100** | **92** |", 92),
            # 纯总分行（无加粗）
            ("| 总计 | 100 | 78 |", 78),
            # 冒号格式
            ("综合评分：92", 92),
            # 英文冒号
            ("评分: 78", 78),
            # 多行报告，总计行在中间
            ("# 评审报告\n## 总览\n| 总计 | 100 | 65 |\n## 详情", 65),
            # 无评分 → 0
            ("本报告无评分", 0),
        ],
    )
    def test_extract(self, report_text, expected):
        from core.steps.step5_review import Step5Review

        assert Step5Review._extract_score(report_text) == expected


class TestScoreToGrade:
    """测试评分转等级"""

    @pytest.mark.parametrize(
        "score,grade",
        [
            (100, "优秀"),
            (90, "优秀"),
            (89, "良好"),
            (75, "良好"),
            (74, "中等"),
            (60, "中等"),
            (59, "较差"),
            (0, "较差"),
        ],
    )
    def test_grade(self, score, grade):
        from core.steps.step5_review import Step5Review

        assert Step5Review._score_to_grade(score) == grade


# ============================================================================
# Step6HumanTest._check_has_results
# ============================================================================


class TestCheckHasResults:
    """测试 Excel 执行结果检测

    直接测试共享实现 core.utils.excel_has_results。
    Pipeline._has_results 和 Step6HumanTest._check_has_results 均委托给它。
    """

    def _make_xlsx(self, path, headers, rows):
        """构造测试 Excel"""
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        assert ws is not None  # Workbook() 总会创建 active sheet
        ws.append(headers)
        for row in rows:
            ws.append(row)
        wb.save(str(path))
        wb.close()

    def test_no_result_column(self, tmp_path):
        """无「执行结果」列 → False"""
        from core.utils import excel_has_results

        xlsx = tmp_path / "tc.xlsx"
        self._make_xlsx(xlsx, ["用例编号", "标题"], [["TC-1", "登录"]])
        assert excel_has_results(xlsx) is False

    def test_result_column_empty(self, tmp_path):
        """有「执行结果」列但全部为空 → False"""
        from core.utils import excel_has_results

        xlsx = tmp_path / "tc.xlsx"
        self._make_xlsx(
            xlsx,
            ["用例编号", "执行结果"],
            [["TC-1", ""], ["TC-2", ""], ["TC-3", None]],
        )
        assert excel_has_results(xlsx) is False

    def test_result_column_filled(self, tmp_path):
        """有「执行结果」列且至少 1 行填写 → True"""
        from core.utils import excel_has_results

        xlsx = tmp_path / "tc.xlsx"
        self._make_xlsx(
            xlsx,
            ["用例编号", "执行结果"],
            [["TC-1", ""], ["TC-2", "通过"], ["TC-3", "失败"]],
        )
        assert excel_has_results(xlsx) is True

    def test_result_column_variant_header(self, tmp_path):
        """列名变体「测试执行结果」也应识别"""
        from core.utils import excel_has_results

        xlsx = tmp_path / "tc.xlsx"
        self._make_xlsx(
            xlsx,
            ["编号", "测试执行结果"],
            [["TC-1", "通过"]],
        )
        assert excel_has_results(xlsx) is True

    def test_nonexistent_file(self, tmp_path):
        """文件不存在 → False（不抛异常）"""
        from core.utils import excel_has_results

        assert excel_has_results(str(tmp_path / "nope.xlsx")) is False

    def test_only_header_row(self, tmp_path):
        """仅有表头、无数据行 → False"""
        from core.utils import excel_has_results

        xlsx = tmp_path / "tc.xlsx"
        self._make_xlsx(xlsx, ["用例编号", "执行结果"], [])
        assert excel_has_results(xlsx) is False

    def test_pipeline_and_step6_delegate_to_shared(self, tmp_path):
        """回归：Step6._check_has_results 委托共享实现后行为正确

        Pipeline._has_results 是实例方法，这里通过验证共享函数本身
        + Step6 委托来间接覆盖 Pipeline 路径（三者使用同一实现）。
        """
        from core.steps.step6_human_test import Step6HumanTest

        xlsx = tmp_path / "tc.xlsx"
        self._make_xlsx(xlsx, ["编号", "执行结果"], [["TC-1", "通过"]])

        # Pipeline 用实例方法（需要构造实例或直接调用底层函数）
        # 这里直接验证共享函数的行为被两端正确委托
        from core.utils import excel_has_results
        assert excel_has_results(xlsx) is True
        assert Step6HumanTest._check_has_results(str(xlsx)) is True


# ============================================================================
# Step2KBSearch._extract_keywords
# ============================================================================


class TestExtractKeywords:
    """测试从需求分析 Markdown 提取关键词

    覆盖正常提取、上限截断、去重、空输入回退等边界。
    """

    def test_extract_modules_and_features(self):
        """正常情况：提取模块名 + 功能点"""
        from core.steps.step2_kb_search import Step2KBSearch

        analysis = """# 需求分析

模块一：用户认证
模块二：订单管理

功能点 1.1：登录验证
功能点 2.1：创建订单
"""
        keywords = Step2KBSearch._extract_keywords(analysis)
        assert "用户认证" in keywords
        assert "订单管理" in keywords
        assert "登录验证" in keywords

    def test_limit_to_five_keywords(self):
        """超过 5 个时只取前 5 个（去重后）"""
        from core.steps.step2_kb_search import Step2KBSearch

        analysis = "\n".join(
            f"模块{c}：模块{c}\n功能点 {i}.1：功能{i}"
            for i, c in enumerate("一二三四五六七八", 1)
        )
        keywords = Step2KBSearch._extract_keywords(analysis)
        # 模块[:3] + 功能点[:3] = 最多 6 个，去重后 ≤5
        assert len(keywords.split()) <= 5

    def test_empty_input_returns_default(self):
        """空输入 → 默认关键词"测试" """
        from core.steps.step2_kb_search import Step2KBSearch

        assert Step2KBSearch._extract_keywords("") == "测试"

    def test_no_match_returns_default(self):
        """无模块/功能点匹配 → 默认"测试" """
        from core.steps.step2_kb_search import Step2KBSearch

        analysis = "# 一些无关内容\n这里没有模块或功能点"
        assert Step2KBSearch._extract_keywords(analysis) == "测试"

    def test_dedup_same_keyword(self):
        """重复关键词去重"""
        from core.steps.step2_kb_search import Step2KBSearch

        analysis = "模块一：登录\n功能点 1.1：登录"
        keywords = Step2KBSearch._extract_keywords(analysis)
        # "登录"出现两次，去重后只保留一个
        assert keywords == "登录"

    def test_trims_whitespace(self):
        """关键词前后空白被 trim"""
        from core.steps.step2_kb_search import Step2KBSearch

        analysis = "模块一：  带空格的关键词  \n"
        keywords = Step2KBSearch._extract_keywords(analysis)
        assert keywords == "带空格的关键词"
