#!/usr/bin/env python3
"""
生成 Excel 格式测试用例
读取测试点 Markdown 文件，生成结构化的 .xlsx 文件

用法:
    python generate_excel.py <testpoints.md> [--output testcases.xlsx] [--dimensions all|basic|positive,negative]
"""

import argparse
import re
import sys
from pathlib import Path

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
except ImportError:
    print("错误: 缺少依赖库 openpyxl", file=sys.stderr)
    print("请运行: pip install openpyxl", file=sys.stderr)
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════
# 测试点解析器
# ═══════════════════════════════════════════════════════════════

class TestPointParser:
    """解析测试点 Markdown 文件"""

    def __parse(self, content: str) -> list:
        """解析 Markdown 内容，返回结构化的测试点列表"""
        test_points = []
        current_module = ""
        current_feature = ""
        current_dimension = ""
        current_number = 0

        for line in content.split("\n"):
            line = line.rstrip()

            # 模块
            # ## 模块一：订单创建  或  ## 模块一：订单创建
            m = re.match(r"^##\s+模块[一二三四五六七八九十]+[：:]\s*(.+)", line)
            if m:
                current_module = m.group(1).strip()
                continue

            # 功能点
            # ### 功能点 1.1：下单流程
            m = re.match(r"^###\s+功能点\s*[\d.]+[：:]\s*(.+)", line)
            if m:
                current_feature = m.group(1).strip()
                continue

            # 测试维度
            # #### 测试维度：正向测试
            m = re.match(r"^####\s+测试维度[：:]\s*(.+)", line)
            if m:
                current_dimension = m.group(1).strip()
                continue

            # 测试点
            # - 测试点 1.1.1：正常下单流程
            m = re.match(r"^-\s+测试点\s*[\d.]+[：:]\s*(.+)", line)
            if m:
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
        """解析文件"""
        content = Path(file_path).read_text(encoding="utf-8")
        return self.__parse(content)


# ═══════════════════════════════════════════════════════════════
# 用例生成器
# ═════════════════════════════════════════════════════　　　　　　

class TestCaseGenerator:
    """根据测试点生成测试用例"""

    DIMENSION_MAP = {
        "正向测试": "positive",
        "负向测试": "negative",
        "边界测试": "boundary",
        "异常测试": "exception",
        "性能测试": "performance",
        "安全测试": "security",
    }

    def __generate_steps(self, tp: dict) -> str:
        """根据测试点生成测试步骤"""
        title = tp["title"]
        dimension = tp["dimension"]

        # 正向测试 - 按业务流程生成步骤
        if "正向" in dimension:
            if "下单" in title:
                return ("1. 登录系统\n"
                        "2. 进入购物车页面\n"
                        "3. 选择商品\n"
                        "4. 点击\"提交订单\"按钮")
            if "支付" in title:
                return ("1. 进入待支付订单页面\n"
                        "2. 选择支付方式\n"
                        "3. 点击\"确认支付\"按钮\n"
                        "4. 在支付页面完成支付操作")
            if "查询" in title or "列表" in title:
                return ("1. 登录系统\n"
                        "2. 进入订单列表页面\n"
                        "3. 执行查询操作")
            if "退款" in title:
                return ("1. 进入订单详情页面\n"
                        "2. 点击\"申请退款\"按钮\n"
                        "3. 填写退款原因\n"
                        "4. 提交退款申请")
            return f"1. 按照业务流程执行: {title}"

        # 负向测试
        if "负向" in dimension:
            return f"1. 准备条件: {tp['test_data']}\n2. 执行操作: {title}"

        # 边界测试
        if "边界" in dimension:
            return f"1. 设置边界数据: {tp['test_data']}\n2. 执行操作: {title}"

        # 异常测试
        if "异常" in dimension:
            return (f"1. 模拟异常场景: {tp['test_data']}\n"
                    f"2. 执行操作: {title}\n"
                    f"3. 观察系统响应")

        # 性能测试
        if "性能" in dimension:
            if "并发" in title or "高并发" in title:
                return ("1. 使用性能测试工具(如 JMeter)模拟并发用户\n"
                        "2. 按测试数据设置并发数量和脚本\n"
                        "3. 执行测试并记录响应时间、成功率等指标\n"
                        "4. 分析性能数据")
            if "响应时间" in title:
                return ("1. 执行正常业务操作\n"
                        "2. 记录请求发送到响应接收的时间差\n"
                        "3. 重复多次取平均值")
            return f"1. 使用性能测试工具执行: {title}\n2. 记录性能指标"

        # 安全测试
        if "安全" in dimension:
            if "越权" in title:
                return ("1. 使用用户A的账号登录\n"
                        "2. 尝试访问/操作用户B的数据\n"
                        "3. 观察系统响应")
            if "注入" in title or "XSS" in title or "SQL" in title:
                return (f"1. 在输入框中输入恶意代码: {tp['test_data']}\n"
                        "2. 提交请求\n"
                        "3. 检查系统是否执行了恶意代码或报错")
            if "篡改" in title:
                return ("1. 使用抓包工具(如 Burp Suite)拦截请求\n"
                        "2. 篡改关键参数\n"
                        "3. 发送篡改后的请求\n"
                        "4. 检查系统是否验证了数据")
            return f"1. 按照安全测试方法执行: {title}"

        return f"1. 执行操作: {title}"

    def __assign_priority(self, tp: dict) -> str:
        """分配优先级"""
        title = tp["title"]
        dimension = tp["dimension"]
        module = tp["module"]

        # P0: 核心流程的正向、资金/安全的异常
        if "正向" in dimension:
            if any(k in title for k in ["下单", "支付", "退款", "登录", "注册"]):
                return "P0"
            return "P1"

        # 安全测试优先级较高
        if "安全" in dimension:
            if any(k in title for k in ["越权", "篡改", "注入", "泄露"]):
                return "P0"
            return "P1"

        # 性能测试优先级一般
        if "性能" in dimension:
            return "P2"

        # 异常测试 - 关键场景 P0
        if "异常" in dimension:
            if any(k in title for k in ["并发", "支付", "回调"]):
                return "P0"
            return "P1"

        # 边界测试
        if "边界" in dimension:
            return "P1"

        # 负向测试
        if "负向" in dimension:
            return "P1"

        return "P1"

    def __generate_precondition(self, tp: dict) -> str:
        """生成前置条件"""
        title = tp["title"]
        dimension = tp["dimension"]
        module = tp["module"]

        if "下单" in title or "订单创建" in module:
            return "用户已登录，购物车中有商品"

        if "支付" in title:
            return "用户已登录，有待支付订单"

        if "退款" in title:
            return "用户已登录，有已支付的订单"

        if "查询" in title or "列表" in title or "详情" in title:
            return "用户已登录"

        if "统计" in title or "导出" in title:
            return "管理员已登录"

        if "登录" in title:
            return "用户在登录页面"

        if "异常" in dimension or "安全" in dimension:
            return "测试环境已就绪，准备好测试工具"

        return "用户已登录系统"

    def generate(self, test_points: list) -> list:
        """生成测试用例"""
        test_cases = []
        for i, tp in enumerate(test_points, 1):
            test_cases.append({
                "id": f"TC-{i:03d}",
                "module": tp["module"],
                "feature": tp["feature"],
                "dimension": tp["dimension"],
                "title": tp["title"],
                "priority": self.__assign_priority(tp),
                "precondition": self.__generate_precondition(tp),
                "steps": self.__generate_steps(tp),
                "test_data": tp["test_data"],
                "预留": tp["expected"],
            })
        return test_cases

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

    def filter_by_dimensions(self, test_points: list, dimensions: str) -> list:
        """按测试维度过滤"""
        if dimensions == "all":
            return test_points

        # 解析关键词
        keywords = []
        for part in dimensions.split(","):
            part = part.strip()
            # 先尝试英文别名
            if part in self.DIMENSION_ALIASES:
                keywords.extend(self.DIMENSION_ALIASES[part])
            else:
                keywords.append(part)

        return [tp for tp in test_points
                if any(k in tp["dimension"] for k in keywords)]


# ═══════════════════════════════════════════════════════════════
# Excel 写入器
# ═════════════════════════════════　　　　　　　　　　　　　　　　

class ExcelWriter:
    """写入 Excel 文件，带格式化"""

    # 表头定义
    HEADERS = [
        ("用例编号", 12),
        ("所属模块", 16),
        ("功能点", 20),
        ("测试维度", 12),
        ("用例标题", 30),
        ("优先级", 10),
        ("前置条件", 25),
        ("测试步骤", 45),
        ("测试数据", 25),
        ("预期结果", 40),
        ("备注", 15),
        ("执行结果", 12),
    ]

    # 优先级颜色
    PRIORITY_FILLS = {
        "P0": PatternFill(start_color="FFCDD2", fill_type="solid"),  # 浅红
        "P1": PatternFill(start_color="FFE0B2", fill_type="solid"),  # 浅橙
        "P2": PatternFill(start_color="C8E6C9", fill_type="solid"),  # 浅绿
    }

    def __write(self, test_cases: list, output_path: str):
        wb = Workbook()
        ws = wb.active
        ws.title = "测试用例"

        # ── 表头 ──
        header_font = Font(name="微软雅黑", bold=True, color="FFFFFF", size=11)
        header_fill = PatternFill(start_color="2F4F4F", fill_type="solid")
        thin_border = Border(
            left=Side(style="thin"), right=Side(style="thin"),
            top=Side(style="thin"), bottom=Side(style="thin"),
        )

        for col, (header, width) in enumerate(self.HEADERS, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = thin_border
            ws.column_dimensions[get_column_letter(col)].width = width

        ws.row_dimensions[1].height = 30

        # ── 数据行 ──
        data_font = Font(name="微软雅黑", size=10)
        for row_idx, tc in enumerate(test_cases, 2):
            row_data = [
                tc["id"], tc["module"], tc["feature"], tc["dimension"],
                tc["title"], tc["priority"], tc["precondition"],
                tc["steps"], tc["test_data"], tc["预留"], "", ""
            ]
            for col, value in enumerate(row_data, 1):
                cell = ws.cell(row=row_idx, column=col, value=value)
                cell.font = data_font
                cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
                cell.border = thin_border

            # 优先级着色
            if tc["priority"] in self.PRIORITY_FILLS:
                ws.cell(row=row_idx, column=6).fill = self.PRIORITY_FILLS[tc["priority"]]

            # 行高根据步骤数调整
            step_count = tc["steps"].count("\n") + 1
            ws.row_dimensions[row_idx].height = max(30, step_count * 18)

        # ── 冻结首行 ──
        ws.freeze_panes = "A2"

        # ── 自动筛选 ──
        last_col = get_column_letter(len(self.HEADERS))
        ws.auto_filter.ref = f"A1:{last_col}{len(test_cases)+1}"

        wb.save(output_path)

    def write(self, test_cases: list, output_path: str):
        self.__write(test_cases, output_path)


# ═════════════════════════════════════════ 计数助手 ═══════════════════════════

def count_stats(test_cases: list) -> dict:
    """统计用例分布"""
    stats = {
        "total": len(test_cases),
        "modules": set(),
        "features": set(),
        "dimensions": {},
        "priorities": {},
    }
    for tc in test_cases:
        stats["modules"].add(tc["module"])
        stats["features"].add(tc["feature"])
        stats["dimensions"][tc["dimension"]] = stats["dimensions"].get(tc["dimension"], 0) + 1
        stats["priorities"][tc["priority"]] = stats["priorities"].get(tc["priority"], 0) + 1
    return stats


# ═══════════════ SkillScript ┐ ═══════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="生成 Excel 格式测试用例")
    parser.add_argument("input", help="测试点 Markdown 文件路径")
    parser.add_argument("-o", "--output", default="testcases.xlsx", help="输出文件路径")
    parser.add_argument(
        "-d", "--dimensions",
        default="all",
        help="测试维度过滤: all|basic|positive,negative,boundary,exception,performance,security"
    )
    args = parser.parse_args()

    # 1. 解析测试点
    print(f"📖 读取测试点文件: {args.input}")
    test_point_parser = TestPointParser()
    test_points = test_point_parser.parse_file(args.input)

    if not test_points:
        print("⚠️  未解析到任何测试点，请检查文件格式", file=sys.stderr)
        return 1

    print(f"✅ 解析到 {len(test_points)} 个测试点")

    # 2. 过滤
    if args.dimensions != "all":
        test_points = TestCaseGenerator().filter_by_dimensions(test_points, args.dimensions)
        print(f"🔍 过滤后剩余 {len(test_points)} 个测试点")

    # 3. 生成用例
    print("🔨 生成测试用例...")
    generator = TestCaseGenerator()
    test_cases = generator.generate(test_points)

    # 4. 统计
    stats = count_stats(test_cases)

    print(f"\n✅ 测试用例生成完成！")
    print(f"📊 统计信息：")
    print(f"  - 测试模块：{len(stats['modules'])} 个")
    print(f"  - 功能点：{len(stats['features'])} 个")
    print(f"  - 用例总数：{stats['total']} 个")
    print(f"\n📊 测试维度分布：")
    for dim, count in stats["dimensions"].items():
        print(f"  - {dim}: {count} 个")
    print(f"\n📊 优先级分布：")
    for pri in ["P0", "P1", "P2"]:
        count = stats["priorities"].get(pri, 0)
        print(f"  - {pri}: {count} 个")

    # 5. 写入 Excel
    print(f"\n📁 写入文件: {args.output}")
    excel_writer = ExcelWriter()
    excel_writer.write(test_cases, args.output)

    print(f"\n✅ 文件已保存: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())