#!/usr/bin/env python3
"""
生成 XMind 格式测试用例（v2 — 使用 xmind 库生成正确格式）

用法:
    python generate_xmind.py <testpoints.md> [--output testcases.xmind] [--project PROJECT]

依赖:
    pip install XMind (已在 Hermes venv 中安装)
"""

import argparse
import re
import sys
from pathlib import Path

from common import TestPointParser, assign_priority, filter_by_dimensions, DIMENSION_ALIASES

try:
    import xmind
except ImportError:
    print("错误: 缺少依赖库 XMind", file=sys.stderr)
    print("请运行: pip install XMind", file=sys.stderr)
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════
# XMind 生成器
# ═══════════════════════════════════════════════════════════════

class XMindGenerator:
    """使用 xmind 库生成标准格式的 .xmind 文件"""

    def generate(self, test_points: list, output_path: str, project_name: str = ""):
        """生成 XMind 脑图文件"""
        workbook = xmind.load(output_path)

        sheet = workbook.getPrimarySheet()
        root = sheet.getRootTopic()

        title = f"{project_name} 测试用例" if project_name else "测试用例"
        sheet.setTitle(title)
        root.setTitle(title)

        # 按 模块→功能点→测试维度 构建树
        tree = {}
        for tp in test_points:
            mod = tp["module"] or "未分类"
            feat = tp["feature"] or "未分类"
            dim = tp["dimension"] or "未分类"
            tree.setdefault(mod, {})
            tree[mod].setdefault(feat, {})
            tree[mod][feat].setdefault(dim, [])
            tree[mod][feat][dim].append(tp)

        for module_name, features in tree.items():
            mod_topic = root.addSubTopic()
            mod_topic.setTitle(module_name)

            for feat_name, dimensions in features.items():
                feat_topic = mod_topic.addSubTopic()
                feat_topic.setTitle(feat_name)

                for dim_name, tps in dimensions.items():
                    dim_topic = feat_topic.addSubTopic()
                    dim_topic.setTitle(f"[{dim_name}] ({len(tps)} 条)")

                    for tp in tps:
                        priority = assign_priority(tp)
                        tc_title = f"[{priority}] {tp['title']}"

                        tc_topic = dim_topic.addSubTopic()
                        tc_topic.setTitle(tc_title)

                        # 添加测试数据子节点
                        if tp.get("test_data"):
                            dt = tc_topic.addSubTopic()
                            dt.setTitle(f"数据: {tp['test_data'][:60]}")

                        # 添加预期结果子节点
                        if tp.get("expected"):
                            et = tc_topic.addSubTopic()
                            et.setTitle(f"预期: {tp['expected'][:60]}")

        # 统计节点
        self._add_stats(root, test_points)

        xmind.save(workbook, output_path)

    def _add_stats(self, root, test_points: list):
        """添加统计信息节点"""
        total = len(test_points)
        p0 = sum(1 for tp in test_points if assign_priority(tp) == "P0")
        p1 = sum(1 for tp in test_points if assign_priority(tp) == "P1")
        p2 = sum(1 for tp in test_points if assign_priority(tp) == "P2")

        dims = {}
        mods = set()
        for tp in test_points:
            dims[tp["dimension"]] = dims.get(tp["dimension"], 0) + 1
            mods.add(tp["module"])

        stats = root.addSubTopic()
        stats.setTitle(f"📊 统计")

        stats.addSubTopic().setTitle(f"总用例: {total} 个")
        stats.addSubTopic().setTitle(f"模块: {len(mods)} 个")

        pri = stats.addSubTopic()
        pri.setTitle("优先级分布")
        pri.addSubTopic().setTitle(f"P0: {p0} 个")
        pri.addSubTopic().setTitle(f"P1: {p1} 个")
        pri.addSubTopic().setTitle(f"P2: {p2} 个")

        dim = stats.addSubTopic()
        dim.setTitle("维度分布")
        for d, c in sorted(dims.items()):
            dim.addSubTopic().setTitle(f"{d}: {c} 个")


# ═══════════════════════════════════════════════════════════════
# 主函数
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="生成 XMind 格式测试用例")
    parser.add_argument("input", help="测试点 Markdown 文件路径")
    parser.add_argument("-o", "--output", default="testcases.xmind", help="输出文件路径")
    parser.add_argument("--project", default="", help="项目名称（可选）")
    parser.add_argument(
        "-d", "--dimensions", default="all",
        help="测试维度过滤: all|basic|positive,negative,boundary,exception,performance,security"
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ 文件不存在: {args.input}", file=sys.stderr)
        return 1

    print(f"📖 读取测试点文件: {args.input}")
    parser = TestPointParser()
    test_points = parser.parse_file(args.input)

    if not test_points:
        print("⚠️  未解析到任何测试点", file=sys.stderr)
        return 1

    print(f"✅ 解析到 {len(test_points)} 个测试点")

    # 维度过滤
    if args.dimensions != "all":
        test_points = filter_by_dimensions(test_points, args.dimensions)
        print(f"🔍 过滤后剩余 {len(test_points)} 个测试点")

    # 如果输出文件已存在，先删除，避免 xmind 追加旧 sheet
    if Path(args.output).exists():
        Path(args.output).unlink()

    print("🔨 生成 XMind 脑图文件...")
    generator = XMindGenerator()
    generator.generate(test_points, args.output, args.project)

    p0 = sum(1 for tp in test_points if assign_priority(tp) == "P0")
    p1 = sum(1 for tp in test_points if assign_priority(tp) == "P1")
    p2 = sum(1 for tp in test_points if assign_priority(tp) == "P2")

    print(f"\n✅ 测试用例生成完成！")
    print(f"📊 统计信息：")
    print(f"  - 测试模块：{len(set(tp['module'] for tp in test_points))} 个")
    print(f"  - 用例总数：{len(test_points)} 个")
    print(f"  - P0（高）: {p0} 个")
    print(f"  - P1（中）: {p1} 个")
    print(f"  - P2（低）: {p2} 个")

    size = Path(args.output).stat().st_size
    print(f"\n📁 输出文件: {args.output} ({size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
