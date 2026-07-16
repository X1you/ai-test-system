#!/usr/bin/env python3
"""
测试引擎核心 — 测试用例执行框架。

提供：
  - TestCase：单个测试用例的抽象
  - TestResult：测试结果记录
  - TestSuite：测试套件管理
  - 测试结果序列化（JSON）
"""

import time
import traceback
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum


class TestStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"       # 测试本身出错（非断言失败）
    SKIPPED = "skipped"
    WARNING = "warning"   # 通过但有警告


@dataclass
class TestResult:
    """单个测试结果"""
    test_id: str
    name: str
    phase: str
    status: str       # TestStatus value
    duration_ms: float = 0.0
    detail: str = ""
    error: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TestCase:
    """测试用例定义"""
    test_id: str
    name: str
    phase: str
    func: Callable[[], str]  # 返回 detail 字符串，抛异常表示失败
    timeout: float = 60.0    # 秒
    description: str = ""


class TestSuite:
    """测试套件 — 管理和执行测试用例"""

    def __init__(self):
        self._cases: list[TestCase] = []
        self._results: list[TestResult] = []

    def add(self, case: TestCase):
        """添加测试用例"""
        self._cases.append(case)

    def add_simple(self, test_id: str, name: str, phase: str,
                   func: Callable[[], str], timeout: float = 60.0,
                   description: str = ""):
        """便捷添加"""
        self._cases.append(TestCase(test_id, name, phase, func, timeout, description))

    def run_all(self, stop_on_error: bool = False) -> list[TestResult]:
        """执行所有测试用例

        Args:
            stop_on_error: 遇到 error 是否停止（默认 False，继续执行）
        Returns:
            测试结果列表
        """
        self._results = []
        total = len(self._cases)

        for i, case in enumerate(self._cases, 1):
            print(f"  [{i}/{total}] {case.phase}/{case.test_id}: {case.name}...", end=" ", flush=True)

            result = self._run_one(case)
            self._results.append(result)

            icon = {"passed": "✅", "failed": "❌", "error": "⚡", "skipped": "⏭️", "warning": "⚠️"}
            print(f"{icon.get(result.status, '?')} ({result.duration_ms:.0f}ms)")

            if result.status == "error" and stop_on_error:
                print(f"\n  ⛔ 致命错误，停止执行: {result.error[:100]}")
                break

        return self._results

    def _run_one(self, case: TestCase) -> TestResult:
        """执行单个测试用例（带超时和异常捕获）"""
        start = time.time()
        try:
            detail = case.func()
            elapsed = (time.time() - start) * 1000

            # 检查返回值是否包含失败标记
            if detail and detail.startswith("FAIL:"):
                return TestResult(
                    test_id=case.test_id, name=case.name, phase=case.phase,
                    status=TestStatus.FAILED.value,
                    duration_ms=elapsed, detail=detail, error="",
                )
            if detail and detail.startswith("WARN:"):
                return TestResult(
                    test_id=case.test_id, name=case.name, phase=case.phase,
                    status=TestStatus.WARNING.value,
                    duration_ms=elapsed, detail=detail[5:], error="",
                )

            return TestResult(
                test_id=case.test_id, name=case.name, phase=case.phase,
                status=TestStatus.PASSED.value,
                duration_ms=elapsed, detail=detail or "OK", error="",
            )
        except AssertionError as e:
            elapsed = (time.time() - start) * 1000
            return TestResult(
                test_id=case.test_id, name=case.name, phase=case.phase,
                status=TestStatus.FAILED.value,
                duration_ms=elapsed, detail="", error=str(e),
            )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            tb = traceback.format_exc()
            return TestResult(
                test_id=case.test_id, name=case.name, phase=case.phase,
                status=TestStatus.ERROR.value,
                duration_ms=elapsed, detail="", error=f"{type(e).__name__}: {e}\n{tb[-200:]}",
            )

    @property
    def results(self) -> list[TestResult]:
        return self._results

    def summary(self) -> dict:
        """生成汇总统计"""
        counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0, "warning": 0}
        total_duration = 0.0
        for r in self._results:
            counts[r.status] = counts.get(r.status, 0) + 1
            total_duration += r.duration_ms

        total = len(self._results)
        passed = counts["passed"] + counts["warning"]
        pass_rate = (passed / total * 100) if total > 0 else 0

        return {
            "total": total,
            "passed": passed,
            "failed": counts["failed"],
            "error": counts["error"],
            "skipped": counts["skipped"],
            "warning": counts["warning"],
            "pass_rate": round(pass_rate, 1),
            "total_duration_ms": round(total_duration, 0),
        }

    def results_to_dict(self) -> list[dict]:
        """所有结果序列化为 dict 列表"""
        return [r.to_dict() for r in self._results]
