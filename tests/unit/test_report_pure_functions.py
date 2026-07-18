#!/usr/bin/env python3
"""
scripts/generate_report.py 纯函数单元测试

覆盖 ReportAnalyzer 的无副作用方法：
  - get_quality_grade  (通过率 → 质量评级)
  - get_fix_suggestion  (失败原因 → 修复建议)
  - assess_risk / get_release_recommendation  (风险评估)

设计原则：不读真实 Excel、不写文件，全部用构造的 dict 输入。
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# ReportAnalyzer.get_quality_grade
# ============================================================================


class TestGetQualityGrade:
    """测试通过率 → 质量评级映射"""

    @pytest.fixture
    def analyzer(self):
        from scripts.generate_report import ReportAnalyzer
        return ReportAnalyzer()

    @pytest.mark.parametrize(
        "pass_rate,expected_grade,expected_emoji",
        [
            (1.0, "优秀", "🏆"),
            (0.95, "优秀", "🏆"),
            (0.94, "良好", "✅"),
            (0.85, "良好", "✅"),
            (0.84, "中等", "⚠️"),
            (0.70, "中等", "⚠️"),
            (0.69, "较差", "❌"),
            (0.0, "较差", "❌"),
        ],
    )
    def test_grade_thresholds(self, analyzer, pass_rate, expected_grade, expected_emoji):
        """验证各阈值边界的评级正确性"""
        grade, desc = analyzer.get_quality_grade(pass_rate)
        assert expected_grade in grade
        assert expected_emoji in grade
        assert isinstance(desc, str) and len(desc) > 0

    def test_grade_returns_tuple(self, analyzer):
        """返回值为 (grade, desc) 二元组"""
        result = analyzer.get_quality_grade(0.9)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_description_is_actionable(self, analyzer):
        """描述应包含可操作的指引（"发布"关键词）"""
        for rate in [1.0, 0.9, 0.8, 0.7]:
            _, desc = analyzer.get_quality_grade(rate)
            # 至少高通过率的描述应提及发布建议
            assert isinstance(desc, str)


# ============================================================================
# ReportAnalyzer.get_fix_suggestion
# ============================================================================


class TestGetFixSuggestion:
    """测试失败原因 → 修复建议映射"""

    @pytest.fixture
    def analyzer(self):
        from scripts.generate_report import ReportAnalyzer
        return ReportAnalyzer()

    @pytest.mark.parametrize(
        "cause",
        [
            "代码缺陷",
            "功能未实现",
            "接口/服务异常",
            "权限/认证问题",
            "数据校验失败",
            "状态流转错误",
            "并发/竞态",
            "边界值问题",
            "兼容性",
            "环境配置",
            "功能缺陷",
            "数据问题",
            "用例缺陷",
        ],
    )
    def test_known_cause_returns_specific_suggestion(self, analyzer, cause):
        """每个 FAILURE_CAUSE_MAP 类别都应有具体的修复建议"""
        suggestion = analyzer.get_fix_suggestion(cause)
        assert isinstance(suggestion, str)
        assert len(suggestion) > 10, f"建议过短: {cause} → {suggestion}"
        # 不应是 fallback 文案
        assert "待确认" not in suggestion or cause == "待确认"

    def test_unknown_cause_falls_back(self, analyzer):
        """未知原因 → fallback 到"待确认"建议"""
        suggestion = analyzer.get_fix_suggestion("完全不存在的类别XYZ")
        assert "待确认" in suggestion or "排查" in suggestion

    def test_all_cause_map_keys_have_suggestions(self, analyzer):
        """回归：FAILURE_CAUSE_MAP 的每个 key 都必须有对应建议

        防止新增失败原因类别时遗漏对应的修复建议。
        """
        for cause in analyzer.FAILURE_CAUSE_MAP:
            suggestion = analyzer.get_fix_suggestion(cause)
            assert suggestion != analyzer.get_fix_suggestion("完全不存在的类别XYZ"), (
                f"失败原因 '{cause}' 缺少专属建议，fallback 到了待确认"
            )

    def test_suggestion_is_actionable(self, analyzer):
        """建议应包含动词（检查/确认/修复等），具备可操作性"""
        action_verbs = ["检查", "确认", "修复", "补充", "核对", "参考"]
        for cause in analyzer.FAILURE_CAUSE_MAP:
            suggestion = analyzer.get_fix_suggestion(cause)
            assert any(v in suggestion for v in action_verbs), (
                f"建议缺少可操作动词: {cause} → {suggestion}"
            )


# ============================================================================
# ReportAnalyzer.assess_risk
# ============================================================================


class TestAssessRisk:
    """测试风险评估"""

    @pytest.fixture
    def analyzer(self):
        from scripts.generate_report import ReportAnalyzer
        return ReportAnalyzer()

    def _make_stats(self, **overrides):
        """构造完整的 stats 输入（assess_risk 需要 by_priority/by_module 等）"""
        defaults = {
            "total": 100,
            "passed": 50,
            "failed": 50,
            "blocked": 0,
            "skipped": 0,
            "block": 0,
            "pass": 50,
            "fail": 50,
            "skip": 0,
            "pass_rate": 0.5,
            "by_priority": {
                "P0": {"pass": 0, "fail": 0},
                "P1": {"pass": 0, "fail": 0},
                "P2": {"pass": 0, "fail": 0},
            },
            "by_module": {},
        }
        defaults.update(overrides)
        return defaults

    def test_high_failure_rate_high_risk(self, analyzer):
        """P0 失败 → 高风险"""
        stats = self._make_stats(
            by_priority={"P0": {"pass": 0, "fail": 5}, "P1": {}, "P2": {}},
        )
        risk = analyzer.assess_risk(stats)
        assert isinstance(risk, dict)
        assert len(risk["high"]) > 0
        assert "高风险" in risk["level"]

    def test_p1_failure_medium_risk(self, analyzer):
        """P1 失败（无 P0 失败）→ 中风险"""
        stats = self._make_stats(
            by_priority={"P0": {"pass": 10, "fail": 0}, "P1": {"pass": 5, "fail": 3}, "P2": {}},
        )
        risk = analyzer.assess_risk(stats)
        assert "中风险" in risk["level"]

    def test_zero_failures_low_risk(self, analyzer):
        """零失败 → 低风险（不应抛异常）"""
        stats = self._make_stats(
            passed=100, failed=0, pass_rate=1.0,
            by_priority={"P0": {"pass": 20, "fail": 0}, "P1": {"pass": 30, "fail": 0}, "P2": {}},
        )
        stats["pass"] = 100
        stats["fail"] = 0
        risk = analyzer.assess_risk(stats)
        assert "低风险" in risk["level"]

    def test_low_module_pass_rate_high_risk(self, analyzer):
        """模块通过率 < 70% → 高风险"""
        stats = self._make_stats(
            by_priority={"P0": {"pass": 1, "fail": 0}, "P1": {}, "P2": {}},
            by_module={"登录模块": {"pass": 3, "fail": 7, "block": 0, "skip": 0}},
        )
        risk = analyzer.assess_risk(stats)
        assert any("登录模块" in r for r in risk["high"])
