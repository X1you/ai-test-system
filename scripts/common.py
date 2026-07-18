#!/usr/bin/env python3
"""
共享工具模块 — generate_excel.py 和 generate_xmind.py 的公共代码

包含:
- TestPointParser: 测试点 Markdown 解析
- assign_priority: 优先级分配逻辑
- filter_by_dimensions: 维度过滤
- 常量和别名映射
"""

import re
import sys
from pathlib import Path

# ═══════════════════════════════════════════════════════════════
# 常量：核心模块/功能点/操作关键词
# ═══════════════════════════════════════════════════════════════

# 出现在这些模块/功能点中的用例，优先级整体提升一级（P1→P0, P2→P1）
CORE_MODULES = {
    "用户管理", "用户注册", "用户登录", "密码找回",
    "认证", "权限", "订单", "支付", "交易",
}
CORE_FEATURES = {
    "注册", "登录", "认证", "授权", "权限",
    "创建", "新建", "提交", "下单", "支付",
    "核心流程", "主流程", "全流程",
}
# 核心操作关键词
CORE_ACTION_KW = [
    "登录", "注册", "创建", "新增", "提交", "支付", "下单",
    "核心", "主流程", "关键", "基础", "全流程",
]

# 维度关键词映射（英文 -> 中文）
DIMENSION_ALIASES = {
    "positive": ["正向"],
    "negative": ["负向"],
    "boundary": ["边界"],
    "exception": ["异常"],
    "performance": ["性能"],
    "security": ["安全"],
    "basic": ["正向", "负向", "边界", "异常"],
}


# ═══════════════════════════════════════════════════════════════
# 测试点解析器
# ═══════════════════════════════════════════════════════════════

class TestPointParser:
    """解析测试点 Markdown 文件"""

    # 预编译正则，避免在逐行解析循环中重复编译
    _RE_MODULE = re.compile(r"^##\s+模块[一二三四五六七八九十百千]+[：:]\s*(.+)")
    _RE_FEATURE = re.compile(r"^###\s+功能点\s*[\d.]+[：:]\s*(.+)")
    _RE_DIMENSION = re.compile(r"^####\s+(?:测试维度[：:]\s*)?(.+)")
    _RE_POINT = re.compile(r"^-\s+测试点\s*[\d.]+[：:]\s*(.+)")
    _RE_TEST_DATA = re.compile(r"^\s+-\s+测试数据[：:]\s*(.+)")
    _RE_EXPECTED = re.compile(r"^\s+-\s+预期结果[：:]\s*(.+)")

    def parse(self, content: str) -> list:
        """解析 Markdown 内容，返回结构化的测试点列表

        依次识别模块（##）、功能点（###）、测试维度（####）、
        测试点（- 测试点 N:）、测试数据和预期结果。
        """
        test_points = []
        current_module = ""
        current_feature = ""
        current_dimension = ""
        current_number = 0

        for line in content.split("\n"):
            line = line.rstrip()

            if m := self._RE_MODULE.match(line):
                current_module = m.group(1).strip()
                continue

            if m := self._RE_FEATURE.match(line):
                current_feature = m.group(1).strip()
                continue

            # 测试维度（兼容两种格式）
            #   #### 测试维度：正向测试
            #   #### 正向测试
            if m := self._RE_DIMENSION.match(line):
                current_dimension = m.group(1).strip()
                continue

            if m := self._RE_POINT.match(line):
                current_number += 1
                test_points.append({
                    "module": current_module,
                    "feature": current_feature,
                    "dimension": current_dimension,
                    "title": m.group(1).strip(),
                    "test_data": "",
                    "expected": "",
                    "number": current_number,
                })
                continue

            if m := self._RE_TEST_DATA.match(line):
                if test_points:
                    test_points[-1]["test_data"] = m.group(1).strip()
                continue

            if m := self._RE_EXPECTED.match(line):
                if test_points:
                    test_points[-1]["expected"] = m.group(1).strip()

        return test_points

    def parse_file(self, file_path: str) -> list:
        """解析文件"""
        content = Path(file_path).read_text(encoding="utf-8")
        return self.parse(content)


# ═══════════════════════════════════════════════════════════════
# 优先级分配
# ═══════════════════════════════════════════════════════════════

def assign_priority(tp: dict) -> str:
    """分配优先级 - 基于模块、功能点、维度和测试类型的多级决策"""
    title = tp["title"]
    dimension = tp["dimension"]
    module = tp.get("module", "")
    feature = tp.get("feature", "")

    is_core_module = any(k in module for k in CORE_MODULES)
    is_core_feature = any(k in feature for k in CORE_FEATURES)
    is_core = is_core_module or is_core_feature

    # ── 正向测试 ──
    if "正向" in dimension:
        if any(k in title for k in CORE_ACTION_KW):
            return "P0"
        if any(k in title for k in ["校验", "验证", "完整性"]):
            return "P0"
        if any(k in title for k in ["集成", "串联", "全流程", "恢复", "续跑"]):
            return "P0"
        if is_core:
            return "P0"
        return "P1"

    # ── 安全测试 ──
    if "安全" in dimension:
        high_risk = ["越权", "篡改", "注入", "泄露", "认证", "敏感", "暴力", "破解"]
        if any(k in title for k in high_risk):
            return "P0"
        return "P1"

    # ── 异常测试 ──
    if "异常" in dimension:
        critical = ["并发", "支付", "核心", "关键", "数据丢失", "中断", "失败"]
        if any(k in title for k in critical):
            return "P0"
        if is_core:
            return "P0"
        return "P1"

    # ── 负向测试 ──
    if "负向" in dimension:
        if any(k in title for k in ["越权", "未授权", "未登录", "注入", "锁定", "限制", "封禁"]):
            return "P0"
        if is_core and any(k in title for k in ["错误", "失败", "无效", "重复", "空"]):
            return "P0"
        return "P1"

    # ── 边界测试 ──
    if "边界" in dimension:
        if is_core and any(k in title for k in ["密码", "Token", "有效期", "锁定", "次数", "频率"]):
            return "P0"
        return "P1"

    # ── 性能测试 ──
    if "性能" in dimension:
        if is_core or any(k in title for k in ["核心", "主流程", "并发", "高并发"]):
            return "P1"
        # 非核心性能测试降为 P2，给低优先级场景留出粒度空间
        return "P2"

    # ── 未匹配到已知维度的测试点 ──
    # 兜底为 P1，保证不会遗漏
    return "P1"


# ═══════════════════════════════════════════════════════════════
# 维度过滤
# ═══════════════════════════════════════════════════════════════

def filter_by_dimensions(test_points: list, dimensions: str) -> list:
    """按测试维度过滤

    Args:
        test_points: 测试点列表
        dimensions: 维度字符串，支持 "all" / "basic" / "positive,negative" 等

    Returns:
        过滤后的测试点列表。
        已知维度名通过 DIMENSION_ALIASES 映射为中文关键词；
        未知维度名直接作为关键词使用（允许自定义维度），不会报错。
    """
    if dimensions == "all" or not dimensions.strip():
        return test_points

    keywords = []
    has_known = False
    for part in dimensions.split(","):
        part = part.strip()
        if not part:
            continue
        if part in DIMENSION_ALIASES:
            keywords.extend(DIMENSION_ALIASES[part])
            has_known = True
        else:
            # 未知维度名直接当作关键词使用（允许自定义维度）
            keywords.append(part)

    if not keywords:
        print(f"⚠️  未识别的测试维度: {dimensions}", file=sys.stderr)
        print(f"   支持的维度: {', '.join(DIMENSION_ALIASES.keys())}", file=sys.stderr)
        return []

    result = [tp for tp in test_points
              if any(k in tp["dimension"] for k in keywords)]

    # 所有关键词都未知且结果为空 → 可能是拼写错误，给出提示
    if not has_known and not result:
        print(f"⚠️  未识别的测试维度: {dimensions}", file=sys.stderr)
        print(f"   支持的维度: {', '.join(DIMENSION_ALIASES.keys())}", file=sys.stderr)

    return result


# ═══════════════════════════════════════════════════════════════
# 优先级过滤
# ═══════════════════════════════════════════════════════════════

def filter_by_priorities(test_cases: list, priorities: str) -> list:
    """按优先级过滤（P0/P1/P2）

    Args:
        test_cases: 测试用例/测试点列表，每项须含 "priority" 或可通过 assign_priority 推断
        priorities: 优先级字符串，如 "P0,P1" 或 "all"

    Returns:
        过滤后的列表。未指定 priority 的测试点会动态调用 assign_priority。
    """
    if priorities == "all":
        return test_cases

    allowed = {p.strip().upper() for p in priorities.split(",") if p.strip()}
    result = []
    for tc in test_cases:
        pri = tc.get("priority")
        if pri is None:
            pri = assign_priority(tc)
        if pri in allowed:
            result.append(tc)
    return result
