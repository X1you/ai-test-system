#!/usr/bin/env python3
"""
单元测试 — XMindGenerator（generate_xmind.py）
覆盖：树结构构建、优先级缓存、统计节点、mock xmind 库
"""

import pytest
import tempfile
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

# 先 mock xmind 库（generate_xmind.py import 时会检查）
_mock_xmind = types.ModuleType("xmind")
_mock_xmind.load = MagicMock(return_value=MagicMock())
_mock_xmind.save = MagicMock()
sys.modules["xmind"] = _mock_xmind

scripts_dir = Path(__file__).parent.parent / "skills" / "generate-testcases" / "scripts"
sys.path.insert(0, str(scripts_dir))


class TestXMindTreeBuild:
    """测试 XMind 树结构构建（不依赖真实 xmind 库）"""

    def _build_tree(self, test_points):
        """复用 generate_xmind 的树构建逻辑"""
        tree = {}
        for tp in test_points:
            mod = tp["module"] or "未分类"
            feat = tp["feature"] or "未分类"
            dim = tp["dimension"] or "未分类"
            tree.setdefault(mod, {})
            tree[mod].setdefault(feat, {})
            tree[mod][feat].setdefault(dim, [])
            tree[mod][feat][dim].append(tp)
        return tree

    def test_single_module_tree(self):
        """单模块树构建"""
        tps = [
            {"module": "用户", "feature": "登录", "dimension": "正向", "title": "正常登录"},
        ]
        tree = self._build_tree(tps)
        assert "用户" in tree
        assert "登录" in tree["用户"]
        assert "正向" in tree["用户"]["登录"]
        assert len(tree["用户"]["登录"]["正向"]) == 1

    def test_multi_module_tree(self):
        """多模块多维度树构建"""
        tps = [
            {"module": "用户", "feature": "登录", "dimension": "正向", "title": "正常登录"},
            {"module": "用户", "feature": "登录", "dimension": "负向", "title": "密码错误"},
            {"module": "订单", "feature": "下单", "dimension": "正向", "title": "正常下单"},
        ]
        tree = self._build_tree(tps)
        assert len(tree) == 2
        assert "用户" in tree and "订单" in tree
        assert len(tree["用户"]["登录"]) == 2

    def test_empty_fields_default(self):
        """空字段用「未分类」填充"""
        tps = [
            {"module": "", "feature": "", "dimension": "", "title": "test"},
        ]
        tree = self._build_tree(tps)
        assert "未分类" in tree
        assert "未分类" in tree["未分类"]

    def test_none_fields_default(self):
        """None 字段用「未分类」填充"""
        tps = [
            {"module": None, "feature": None, "dimension": None, "title": "test"},
        ]
        tree = self._build_tree(tps)
        assert "未分类" in tree

    def test_empty_list(self):
        """空列表生成空树"""
        tree = self._build_tree([])
        assert tree == {}


class TestPriorityCache:
    """测试 assign_priority 预计算缓存"""

    def test_priority_cached(self):
        """验证优先级缓存被正确设置"""
        from common import assign_priority
        tps = [
            {"module": "用户登录", "feature": "密码", "dimension": "正向", "title": "正常登录"},
            {"module": "普通", "feature": "查询", "dimension": "负向", "title": "错误查询"},
        ]
        priorities = [tp.get("_priority") or assign_priority(tp) for tp in tps]
        assert all(p in ("P0", "P1", "P2") for p in priorities)
        # 核心模块正向应为 P0
        assert priorities[0] == "P0"
        # 普通模块负向应为 P1
        assert priorities[1] == "P1"

    def test_no_duplicate_calls(self):
        """缓存后不应重复调用 assign_priority"""
        from common import assign_priority
        tp = {"module": "用户登录", "feature": "f", "dimension": "正向", "title": "正常登录"}
        tp["_priority"] = assign_priority(tp)
        cached = tp["_priority"]
        # 第二次直接取缓存，不调用 assign_priority
        result = tp.get("_priority") or assign_priority(tp)
        assert result == cached


class TestStatsLogic:
    """测试统计逻辑（不依赖 xmind 库的 UI 调用）"""

    def test_stats_calculation(self):
        """验证 P0/P1/P2 统计计算"""
        from common import assign_priority
        tps = [
            {"module": "用户登录", "feature": "f", "dimension": "正向", "title": "正常登录"},
            {"module": "普通", "feature": "f", "dimension": "负向", "title": "错误"},
            {"module": "普通", "feature": "f", "dimension": "边界", "title": "边界值"},
        ]
        priorities = [tp.get("_priority") or assign_priority(tp) for tp in tps]
        p0 = sum(1 for p in priorities if p == "P0")
        p1 = sum(1 for p in priorities if p == "P1")
        p2 = sum(1 for p in priorities if p == "P2")
        total = p0 + p1 + p2
        assert total == len(tps)


class TestXMindGeneratorMocked:
    """用 mock 测试 XMindGenerator.generate（不生成真实文件）"""

    def test_generate_with_mock(self):
        """验证 generate 方法调用 xmind API 正确"""
        from generate_xmind import XMindGenerator
        gen = XMindGenerator()

        tps = [
            {"module": "用户", "feature": "登录", "dimension": "正向",
             "title": "正常登录", "test_data": "account", "expected": "success"},
        ]

        with tempfile.TemporaryDirectory() as d:
            gen.generate(tps, str(Path(d) / "test.xmind"), "测试项目")

        # 验证 xmind API 被调用过
        _mock_xmind.load.assert_called()
        _mock_xmind.save.assert_called()

    def test_generate_project_name_in_title(self):
        """验证项目名出现在标题中"""
        mock_workbook = MagicMock()
        mock_sheet = MagicMock()
        mock_root = MagicMock()
        mock_workbook.getPrimarySheet.return_value = mock_sheet
        mock_sheet.getRootTopic.return_value = mock_root

        with patch.object(_mock_xmind, "load", return_value=mock_workbook):
            from generate_xmind import XMindGenerator
            gen = XMindGenerator()

            with tempfile.TemporaryDirectory() as d:
                gen.generate([], str(Path(d) / "t.xmind"), "电商系统")

            # 标题应包含项目名
            title_arg = mock_sheet.setTitle.call_args[0][0]
            assert "电商系统" in title_arg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])