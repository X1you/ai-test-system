#!/usr/bin/env python3
"""测试 ReportAnalyzer 的失败原因推断算法。

重点覆盖 commit 44b91f6 新增的「代码审查型失败」识别逻辑：
  - review_hit 预扫描：命中代码缺陷/功能未实现关键词时，运行时类别失去维度加权
  - 代码审查型自身保留维度加权（安全→代码缺陷，异常→功能未实现）
  - 回归保护：无代码审查关键词时，运行时维度加权行为不变

这些是子任务新增的复杂逻辑但未写测试，本文件锁住行为防止回归。
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def analyzer():
    from scripts.generate_report import ReportAnalyzer
    return ReportAnalyzer()


# ═══════════════════════════════════════════════════════════════
# 代码审查型失败：review_hit 触发后的推断
# ═══════════════════════════════════════════════════════════════


class TestCodeReviewFailureInference:
    """代码审查型失败（功能未实现 / 代码缺陷）的推断。"""

    def test_missing_hash_check_is_code_defect(self, analyzer):
        """TC-006 场景：代码缺 hash 校验，安全测试维度。

        修复前会被安全维度加权误判为「权限/认证问题」。
        """
        cause = analyzer.infer_failure_cause({
            "title": "步骤产物被篡改",
            "remark": "代码中未发现产物完整性校验逻辑，不验证内容",
            "dimension": "安全测试",
            "priority": "P0",
        })
        assert cause == "代码缺陷"

    def test_missing_feature_is_not_implemented(self, analyzer):
        """TC-010 场景：功能未实现，异常测试维度。

        修复前会被异常维度加权误判为「接口/服务异常」。
        """
        cause = analyzer.infer_failure_cause({
            "title": "动态修改模式",
            "remark": "未发现运行中动态修改模式的接口，该功能不存在",
            "dimension": "异常测试",
            "priority": "P1",
        })
        assert cause == "功能未实现"

    def test_dependency_missing_is_not_implemented(self, analyzer):
        """TC-016 场景：依赖功能缺失。"""
        cause = analyzer.infer_failure_cause({
            "title": "中断后修改模式恢复",
            "remark": "依赖TC-010，该功能不存在，用例无法通过",
            "dimension": "异常测试",
            "priority": "P0",
        })
        assert cause == "功能未实现"

    def test_code_defect_outranks_not_implemented_on_tie(self, analyzer):
        """平局时「代码缺陷」优先于「功能未实现」（FAILURE_CAUSE_MAP 顺序）。

        构造同时含两类关键词的文本，应返回代码缺陷。
        """
        cause = analyzer.infer_failure_cause({
            "title": "缺校验的功能",
            "remark": "未发现完整性校验逻辑，不验证内容，功能不存在",
            "dimension": "安全测试",
        })
        assert cause == "代码缺陷"


# ═══════════════════════════════════════════════════════════════
# 回归保护：review_hit = 0 时运行时类别正常工作
# ═══════════════════════════════════════════════════════════════


class TestRuntimeFailureRegression:
    """无代码审查关键词时，运行时失败推断不应被新逻辑影响。"""

    def test_security_dim_still_infers_auth(self, analyzer):
        """纯运行时安全失败（无代码审查词）→ 判「权限/认证问题」。

        注意：含"缺失/未做校验"的会判代码缺陷（合理），这里构造纯运行时场景。
        """
        cause = analyzer.infer_failure_cause({
            "title": "越权访问",
            "remark": "普通用户token能访问管理员接口，返回200，应该403",
            "dimension": "安全测试",
        })
        assert cause == "权限/认证问题"

    def test_exception_dim_still_infers_service_error(self, analyzer):
        """异常测试 + 接口超时关键词 → 判「接口/服务异常」（不被新逻辑干扰）。"""
        cause = analyzer.infer_failure_cause({
            "title": "接口超时",
            "remark": "请求502，服务不可用，连接超时",
            "dimension": "异常测试",
        })
        assert cause == "接口/服务异常"

    def test_no_keywords_returns_default(self, analyzer):
        """无任何关键词命中 → 返回默认值「待确认」。"""
        cause = analyzer.infer_failure_cause({
            "title": "未知问题",
            "remark": "something happened",
            "dimension": "正向测试",
        })
        assert cause == "待确认"

    def test_empty_case_returns_default(self, analyzer):
        """空 case → 返回「待确认」（不抛异常）。"""
        assert analyzer.infer_failure_cause({}) == "待确认"


# ═══════════════════════════════════════════════════════════════
# 修复建议映射
# ═══════════════════════════════════════════════════════════════


class TestFixSuggestions:
    """新分类的修复建议存在且非空。"""

    def test_code_defect_has_suggestion(self, analyzer):
        s = analyzer.get_fix_suggestion("代码缺陷")
        assert isinstance(s, str)
        assert len(s) > 10
        assert "校验" in s or "检查" in s

    def test_not_implemented_has_suggestion(self, analyzer):
        s = analyzer.get_fix_suggestion("功能未实现")
        assert isinstance(s, str)
        assert len(s) > 10
        assert "需求" in s or "实现" in s or "预期" in s

    def test_unknown_cause_fallback(self, analyzer):
        """未知类别 → 返回非空默认建议（不抛异常）。"""
        s = analyzer.get_fix_suggestion("不存在的类别")
        assert isinstance(s, str)
        assert len(s) > 0
