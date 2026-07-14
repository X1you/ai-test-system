#!/usr/bin/env python3
"""
生成 XMind 格式测试用例（JSON content + zip）
读取测试点 Markdown 文件，生成 XMind 脑图文件

用法:
    python generate_xmind.py <testpoints.md> [--output testcases.xmind]
"""

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path


# ═══════════════════════════════════════════════════════════════
# 测试点解析器
# ═══════════════════════════════════════════════════════════════

class TestPointParser:
    """解析测试点 Markdown 文件"""

    def parse_content(self, content: str) -> list:
        test_points = []
        current_module = ""
        current_feature = ""
        current_dimension = ""
        counter = 0

        for line in content.split("\n"):
            line = line.rstrip()

            # 模块
            m = re.match(r"^##\s+模块[一二三四五六七八九十]+[：:]\s*(.+)", line)
            if m:
                current_module = m.group(1).strip()
                continue

            # 功能点
            m = re.match(r"^###\s+功能点\s*[\d.]+[：:]\s*(.+)", line)
            if m:
                current_feature = m.group(1).strip()
                continue

            # 测试维度
            m = re.match(r"^####\s+测试维度[：:]\s*(.+)", line)
            if m:
                current_dimension = m.group(1).strip()
                continue

            # 测试点
            m = re.match(r"^-\s+测试点\s*[\d.]+[：:]\s*(.+)", line)
            if m:
                counter += 1
                test_points.append({
                    "module": current_module,
                    "feature": current_feature,
                    "dimension": current_dimension,
                    "title": m.group(1).strip(),
                    "test_data": "",
                    "expected": "",
                    "number": counter,
                })
                continue

            # 测试数据
            m = re.match(r"^\s+-\s+测试数据[：:]\s*(.+)", line)
            if m and test_points:
                test_points[-1]["test_data"] = m.group(1).strip()
                continue

            # 预期结果
            m = re.match(r"^\s+-\s+预期结果[：:]\s*(.+)", line)
            if m and test_points:
                test_points[-1]["expected"] = m.group(1).strip()
                continue

        return test_points

    def parse_file(self, file_path: str) -> list:
        content = Path(file_path).read_text(encoding="utf-8")
        return self.parse_content(content)


# ═══════════════════════════════════════════════════════════════
# 优先级分配
# ═══════════════════════════════════════════════════════════════

def assign_priority(tp: dict) -> str:
    title = tp["title"]
    dimension = tp["dimension"]

    # P0: 核心功能正向、高风险安全、关键异常
    if "正向" in dimension:
        if any(k in title for k in ["登录", "注册", "创建", "新增", "提交", "支付",
                                     "核心", "主流程", "关键", "基础", "校验", "验证"]):
            return "P0"
        return "P1"
    if "安全" in dimension:
        if any(k in title for k in ["越权", "篡改", "注入", "泄露", "认证", "敏感"]):
            return "P0"
        return "P1"
    if "异常" in dimension:
        if any(k in title for k in ["并发", "核心", "关键"]):
            return "P0"
        return "P1"
    if "负向" in dimension:
        if any(k in title for k in ["越权", "未授权", "未登录", "注入"]):
            return "P0"
        return "P1"
    if "性能" in dimension:
        if any(k in title for k in ["核心", "主流程", "并发", "高并发"]):
            return "P1"
        return "P2"
    return "P1"


# ═══════════════════════════════════════════════════════════════
# XMind Writer
# ═══════════════════════════════════════════════════════════════

class XMindWriter:
    """生成 XMind 文件（.xmind 本质是 zip 包含 content.json）"""

    def build_tree(self, test_points: list) -> dict:
        """构建树结构: module -> feature -> dimension -> [test_points]"""
        tree = {}
        for tp in test_points:
            module = tp["module"]
            feature = tp["feature"]
            dimension = tp["dimension"]

            tree.setdefault(module, {})
            tree[module].setdefault(feature, {})
            tree[module][feature].setdefault(dimension, [])
            tree[module][feature][dimension].append(tp)
        return tree

    def build_content_json(self, tree: dict, test_points: list, project_name: str) -> list:
        """构建 XMind content.json"""
        root_children = []
        tc_counter = 0
        p0_count = 0
        p1_count = 0
        p2_count = 0

        for module_name, features in tree.items():
            module_node = {
                "id": f"mod-{module_name}",
                "title": module_name,
                "children": {"attached": []}
            }

            for feature_name, dimensions in features.items():
                feature_node = {
                    "id": f"feat-{feature_name}",
                    "title": feature_name,
                    "children": {"attached": []}
                }

                for dim_name, tps in dimensions.items():
                    dim_node = {
                        "id": f"dim-{module_name}-{dim_name}",
                        "title": dim_name,
                        "children": {"attached": []}
                    }

                    for tp in tps:
                        tc_counter += 1
                        tc_id = f"TC-{tc_counter:03d}"
                        priority = assign_priority(tp)

                        if priority == "P0":
                            p0_count += 1
                        elif priority == "P1":
                            p1_count += 1
                        else:
                            p2_count += 1

                        tc_node = {
                            "id": tc_id,
                            "title": f"{tc_id}: {tp['title']} [{priority}]",
                            "children": {"attached": [
                                {"id": f"{tc_id}-pre", "title": f"前置条件: {tp.get('precondition', '见测试点')}"},
                                {"id": f"{tc_id}-data", "title": f"测试数据: {tp['test_data']}" if tp['test_data'] else "测试数据: 无"},
                                {"id": f"{tc_id}-exp", "title": f"预期结果: {tp['expected']}" if tp['expected'] else "预期结果: 见测试点"},
                            ]}
                        }
                        dim_node["children"]["attached"].append(tc_node)

                    feature_node["children"]["attached"].append(dim_node)
                module_node["children"]["attached"].append(feature_node)

            root_children.append(module_node)

        # 统计节点
        stats_node = {
            "id": "stats",
            "title": f"📊 统计（共 {tc_counter} 个用例）",
            "children": {"attached": [
                {"id": "stats-p0", "title": f"P0（高）: {p0_count} 个"},
                {"id": "stats-p1", "title": f"P1（中）: {p1_count} 个"},
                {"id": "stats-p2", "title": f"P2（低）: {p2_count} 个"},
            ]}
        }
        root_children.append(stats_node)

        return [{
            "id": "sheet",
            "class": "sheet",
            "title": "测试用例",
            "rootTopic": {
                "id": "root",
                "title": f"{project_name} 测试用例",
                "children": {"attached": root_children}
            }
        }]

    def write(self, test_points: list, output_path: str, project_name: str = "测试项目"):
        tree = self.build_tree(test_points)
        content_json = self.build_content_json(tree, test_points, project_name)

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("content.json", json.dumps(content_json, ensure_ascii=False, indent=2))
            zf.writestr("metadata.json", json.dumps({
                "creator": {"name": "Hermes Test Case Generator", "version": "1.0.0"},
            }, ensure_ascii=False, indent=2))


# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="生成 XMind 格式测试用例")
    parser.add_argument("input", help="测试点 Markdown 文件路径")
    parser.add_argument("-o", "--output", default="testcases.xmind", help="输出文件路径")
    parser.add_argument("-n", "--name", default="测试项目", help="项目名称")
    args = parser.parse_args()

    # 1. 解析
    print(f"📖 读取测试点文件: {args.input}")
    tp_parser = TestPointParser()
    test_points = tp_parser.parse_file(args.input)

    if not test_points:
        print("⚠️  未解析到任何测试点，请检查文件格式", file=sys.stderr)
        return 1

    print(f"✅ 解析到 {len(test_points)} 个测试点")

    # 2. 统计
    p0 = sum(1 for tp in test_points if assign_priority(tp) == "P0")
    p1 = sum(1 for tp in test_points if assign_priority(tp) == "P1")
    p2 = sum(1 for tp in test_points if assign_priority(tp) == "P2")
    modules = len(set(tp["module"] for tp in test_points))

    print(f"\n✅ 测试用例生成完成！")
    print(f"📊 统计信息：")
    print(f"  - 测试模块：{modules} 个")
    print(f"  - 用例总数：{len(test_points)} 个")
    print(f"  - P0（高）: {p0} 个")
    print(f"  - P1（中）: {p1} 个")
    print(f"  - P2（低）: {p2} 个")

    # 3. 写入
    print(f"\n📁 写入文件: {args.output}")
    writer = XMindWriter()
    writer.write(test_points, args.output, project_name=args.name)

    print(f"\n✅ 文件已保存: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())