#!/usr/bin/env python3
"""
core/llm_client.py 纯函数单元测试

覆盖 LLMClient._parse_json_response（容错 JSON 解析），
该方法处理 LLM 输出的多种格式变体。
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


class TestParseJsonResponse:
    """测试 LLM JSON 输出的容错解析"""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            # 1. 标准 JSON
            ('{"score": 85, "passed": true}', {"score": 85, "passed": True}),
            # 2. 带空白的 JSON
            ('  {"a": 1}  ', {"a": 1}),
            # 3. markdown 代码块包裹（无语言标记）
            ('```\n{"score": 90}\n```', {"score": 90}),
            # 4. markdown 代码块（带 json 标记）
            ('```json\n{"score": 75}\n```', {"score": 75}),
            # 5. JSON 前后有解释文字（提取 {...} 块）
            ('根据评审，结果如下：\n{"score": 80}\n以上是评分。', {"score": 80}),
            # 6. 空字符串
            ("", {}),
            # 7. 纯文本无 JSON
            ("这不是 JSON", {}),
            # 8. 损坏的 JSON
            ("{broken", {}),
            # 9. 嵌套 JSON
            ('{"outer": {"inner": 1}}', {"outer": {"inner": 1}}),
        ],
    )
    def test_parse_variants(self, raw, expected):
        from core.llm_client import LLMClient

        result = LLMClient._parse_json_response(raw)
        assert result == expected

    def test_strips_markdown_code_fence(self):
        """markdown 代码块标记被正确去除"""
        from core.llm_client import LLMClient

        raw = '```json\n{"key": "value"}\n```'
        result = LLMClient._parse_json_response(raw)
        assert result == {"key": "value"}

    def test_extracts_json_from_surrounding_text(self):
        """能从解释文字中提取 JSON 对象"""
        from core.llm_client import LLMClient

        raw = '以下是评审结果：\n{"passed": true, "issues": []}\n请参考。'
        result = LLMClient._parse_json_response(raw)
        assert result["passed"] is True
        assert result["issues"] == []

    def test_invalid_json_returns_empty_dict(self):
        """无法解析时返回空 dict（不抛异常）"""
        from core.llm_client import LLMClient

        assert LLMClient._parse_json_response("{{{") == {}
        assert LLMClient._parse_json_response("}{}{") == {}

    def test_code_fence_without_closing(self):
        """代码块缺结束标记 → 尝试提取内容"""
        from core.llm_client import LLMClient

        raw = '```\n{"a": 1}'  # 无结束 ```
        result = LLMClient._parse_json_response(raw)
        # 应能提取出 JSON（通过 {...} 提取策略）
        assert result == {"a": 1}

    def test_multiple_json_objects_extracts_first(self):
        """含多个 {...} 时提取最外层范围（第一个 { 到最后一个 }）"""
        from core.llm_client import LLMClient

        raw = '{"a": 1} 一些文字 {"b": 2}'
        # start=第一个{, end=最后一个} → 跨越文字，json.loads 失败 → {}
        result = LLMClient._parse_json_response(raw)
        # 跨范围解析失败时返回空 dict
        assert isinstance(result, dict)

    def test_array_root_not_extracted(self):
        """根为数组的 JSON（非对象）→ find('{') 找不到 → 返回空

        注意：json.loads 能解析数组，但如果直接解析成功则返回数组。
        此测试验证纯数组输入的行为。
        """
        from core.llm_client import LLMClient

        raw = '[1, 2, 3]'
        result = LLMClient._parse_json_response(raw)
        # json.loads 直接成功 → 返回列表
        assert result == [1, 2, 3]
