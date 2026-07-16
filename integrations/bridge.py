#!/usr/bin/env python3
"""
Integration Bridge — Core Engine 和 Adapter Layer 之间的唯一连接点

将 Core Engine 的产物（testcases.xlsx）转换为 Canonical Model。
"""

from pathlib import Path
from typing import List, Optional

from integrations.models import TestCase, TestResult


def _normalize_status(val: Optional[str]) -> str:
    """标准化执行结果状态"""
    if not val:
        return ""
    val = str(val).strip()
    mapping = {
        "通过": "passed",
        "失败": "failed",
        "阻塞": "blocked",
        "跳过": "skipped",
        "未执行": "",
        "": "",
    }
    return mapping.get(val, val)


class IntegrationBridge:
    """桥接层 — 将 Core Engine 的产物转换为 Canonical Model"""

    @staticmethod
    def excel_to_testcases(xlsx_path: str) -> List[TestCase]:
        """读取 testcases.xlsx → List[TestCase]

        12 列格式：用例编号 | 模块 | 功能点 | 测试维度 | 用例标题 | 优先级 |
                  前置条件 | 步骤 | 测试数据 | 预期结果 | 备注 | 执行结果
        """
        try:
            from openpyxl import load_workbook
        except ImportError:
            raise ImportError("需要 openpyxl 来读取 Excel 文件")

        wb = load_workbook(xlsx_path, data_only=True)
        ws = wb.active
        if ws is None:
            wb.close()
            return []

        cases = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or len(row) < 10:
                continue

            tc = TestCase(
                id=str(row[0] or ""),
                title=str(row[4] or ""),
                module=str(row[1] or ""),
                feature=str(row[2] or ""),
                dimension=str(row[3] or ""),
                priority=str(row[5] or ""),
                precondition=str(row[6] or ""),
                steps=str(row[7] or "").split("\n") if row[7] else [],
                test_data=str(row[8] or ""),
                expected_result=str(row[9] or ""),
                status=_normalize_status(str(row[11]) if len(row) > 11 else None),
            )
            cases.append(tc)

        wb.close()
        return cases

    @staticmethod
    def excel_to_results(xlsx_path: str) -> List[TestResult]:
        """读取 testcases.xlsx 的执行结果列 → List[TestResult]"""
        try:
            from openpyxl import load_workbook
        except ImportError:
            raise ImportError("需要 openpyxl 来读取 Excel 文件")

        wb = load_workbook(xlsx_path, data_only=True)
        ws = wb.active
        if ws is None:
            wb.close()
            return []

        results = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or len(row) < 12:
                continue
            tc_id = str(row[0] or "")
            status_raw = str(row[11] or "").strip()
            if not status_raw:
                continue

            results.append(TestResult(
                test_case_id=tc_id,
                status=_normalize_status(status_raw),
                comment=str(row[10] or ""),
            ))

        wb.close()
        return results

    @staticmethod
    def testcases_to_excel(cases: List[TestCase], output_path: str) -> str:
        """反向：Canonical → Excel（用于 pull 后写回）"""
        try:
            from openpyxl import Workbook
        except ImportError:
            raise ImportError("需要 openpyxl 来写入 Excel 文件")

        wb = Workbook()
        ws = wb.active
        ws.title = "测试用例"

        headers = ["用例编号", "所属模块", "功能点", "测试维度", "用例标题",
                    "优先级", "前置条件", "测试步骤", "测试数据", "预期结果",
                    "备注", "执行结果"]
        ws.append(headers)

        for tc in cases:
            ws.append([
                tc.id, tc.module, tc.feature, tc.dimension, tc.title,
                tc.priority, tc.precondition,
                "\n".join(tc.steps) if tc.steps else "",
                tc.test_data, tc.expected_result, "", tc.status,
            ])

        wb.save(output_path)
        wb.close()
        return output_path
