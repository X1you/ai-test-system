#!/usr/bin/env python3
"""
Step0GapAnalysis 纯函数单元测试（无 LLM、无外部服务）。

覆盖两个高价值静态方法：
  - _safe_read_text: 多编码兜底读取 + 二进制检测
  - _extract_gap_count: 四级兜底解析（GAP_COUNT 行 / JSON / 标题计数 / 0）

这些是 Step0 容灾降级的核心逻辑，曾修复过 TC-002/008/010 等真实缺陷。
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# Step0GapAnalysis._safe_read_text
# ============================================================================


class TestSafeReadText:
    """测试多编码兜底读取 + 二进制检测"""

    def test_utf8(self, tmp_path):
        from core.steps.step0_gap_analysis import Step0GapAnalysis

        p = tmp_path / "req.md"
        p.write_text("# 需求\n登录功能", encoding="utf-8")
        text = Step0GapAnalysis._safe_read_text(p)
        assert text is not None
        assert "登录功能" in text

    def test_utf8_with_bom(self, tmp_path):
        """UTF-8 BOM 文件应被 utf-8-sig 正确处理（不残留 BOM 字符）"""
        from core.steps.step0_gap_analysis import Step0GapAnalysis

        p = tmp_path / "bom.md"
        p.write_bytes(b"\xef\xbb\xbf# \xe9\x9c\x80\xe6\xb1\x82")  # BOM + "需求"
        text = Step0GapAnalysis._safe_read_text(p)
        assert text is not None
        assert text.startswith("# 需求")

    def test_gbk(self, tmp_path):
        """GBK 编码文件应被正确解码"""
        from core.steps.step0_gap_analysis import Step0GapAnalysis

        p = tmp_path / "gbk.md"
        p.write_bytes("需求文档".encode("gbk"))
        text = Step0GapAnalysis._safe_read_text(p)
        assert text is not None
        assert "需求文档" in text

    def test_empty_file(self, tmp_path):
        """空文件 → 空字符串（非 None）"""
        from core.steps.step0_gap_analysis import Step0GapAnalysis

        p = tmp_path / "empty.md"
        p.write_bytes(b"")
        assert Step0GapAnalysis._safe_read_text(p) == ""

    def test_binary_file_returns_none(self, tmp_path):
        """纯二进制内容（替换字符占比 >30%）→ None（由调用方降级处理）

        这是 TC-002/010 的核心修复点：二进制文件不应抛 UnicodeDecodeError，
        而是优雅返回 None 触发降级报告。
        """
        from core.steps.step0_gap_analysis import Step0GapAnalysis

        p = tmp_path / "bin.dat"
        # 大量非法字节，errors='replace' 后替换字符占比必然 >30%
        p.write_bytes(bytes(range(256)) * 4)
        assert Step0GapAnalysis._safe_read_text(p) is None


# ============================================================================
# Step0GapAnalysis._extract_gap_count
# ============================================================================


class TestExtractGapCount:
    """测试 gap_count 四级兜底解析"""

    def test_gap_count_line(self):
        """策略1：末尾 GAP_COUNT: N 行"""
        from core.steps.step0_gap_analysis import Step0GapAnalysis

        response = "# 漏洞扫描\n\nGAP_COUNT: 5\n"
        assert Step0GapAnalysis._extract_gap_count(response) == 5

    def test_gap_count_fullwidth_colon(self):
        """策略1：兼容全角冒号"""
        from core.steps.step0_gap_analysis import Step0GapAnalysis

        assert Step0GapAnalysis._extract_gap_count("GAP_COUNT：3") == 3

    def test_gap_count_case_insensitive(self):
        """策略1：大小写不敏感"""
        from core.steps.step0_gap_analysis import Step0GapAnalysis

        assert Step0GapAnalysis._extract_gap_count("gap_count: 7") == 7

    def test_gap_count_takes_last_match(self):
        """★ TC-008 修复：文本中出现历史值时取最后一个匹配

        原 re.search 取第一个会被历史值误导，改为 findall 取最后一个。
        """
        from core.steps.step0_gap_analysis import Step0GapAnalysis

        response = "之前 gap_count: 99 的记录\n\n实际结果\nGAP_COUNT: 4\n"
        assert Step0GapAnalysis._extract_gap_count(response) == 4

    def test_json_fragment(self):
        """策略2：JSON 片段 gap_count: N"""
        from core.steps.step0_gap_analysis import Step0GapAnalysis

        response = '```json\n{"gap_count": 6, "items": []}\n```'
        assert Step0GapAnalysis._extract_gap_count(response) == 6

    def test_json_takes_last(self):
        """策略2：JSON 片段也取最后一个匹配（TC-008 一致性）"""
        from core.steps.step0_gap_analysis import Step0GapAnalysis

        response = '{"gap_count": 1}\n后续\n{"gap_count": 8}'
        assert Step0GapAnalysis._extract_gap_count(response) == 8

    def test_heading_count_numeric(self):
        """策略3：统计 ### 漏洞 N 标题数量"""
        from core.steps.step0_gap_analysis import Step0GapAnalysis

        response = (
            "# 报告\n"
            "### 漏洞 1\n内容\n"
            "### 漏洞 2\n内容\n"
            "### 漏洞 3\n内容\n"
        )
        assert Step0GapAnalysis._extract_gap_count(response) == 3

    def test_heading_count_chinese_numeral(self):
        r"""★ TC-008 修复：中文编号（漏洞一/漏洞二）也应被统计

        原正则 r'###\s*漏洞\s*\d+' 只匹配数字，中文编号会漏。
        """
        from core.steps.step0_gap_analysis import Step0GapAnalysis

        response = "### 漏洞一\n### 漏洞二\n### 漏洞三\n"
        assert Step0GapAnalysis._extract_gap_count(response) == 3

    def test_heading_count_letter(self):
        """策略3：字母编号（漏洞 A）也支持"""
        from core.steps.step0_gap_analysis import Step0GapAnalysis

        response = "### 漏洞 A\n### 漏洞 B\n"
        assert Step0GapAnalysis._extract_gap_count(response) == 2

    def test_empty_response(self):
        """策略4：空响应 → 0"""
        from core.steps.step0_gap_analysis import Step0GapAnalysis

        assert Step0GapAnalysis._extract_gap_count("") == 0

    def test_no_match_returns_zero(self):
        """策略4：无任何可识别格式 → 0"""
        from core.steps.step0_gap_analysis import Step0GapAnalysis

        assert Step0GapAnalysis._extract_gap_count("纯文本报告，无任何标记") == 0

    def test_priority_gap_count_over_json(self):
        """策略1 优先于策略2：同时存在时取 GAP_COUNT 行"""
        from core.steps.step0_gap_analysis import Step0GapAnalysis

        response = '{"gap_count": 99}\n\nGAP_COUNT: 2\n'
        assert Step0GapAnalysis._extract_gap_count(response) == 2
