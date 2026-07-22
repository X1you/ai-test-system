#!/usr/bin/env python3
"""
Step6HumanTest.run() 路径单元测试

现有 test_step_pure_functions.py 已覆盖 _check_has_results 纯函数。
本文件覆盖 run() 主流程和 _generate_execution_guide：
  - run()：已有执行结果 → ok=True 继续
  - run()：无执行结果 → 生成指引，返回 human=True 等待
  - _generate_execution_guide：脚本不存在 → 返回 0
  - _generate_execution_guide：脚本执行成功 + 提取用例数
  - _generate_execution_guide：脚本执行异常 → 返回 0（容灾）
  - _generate_execution_guide：成功但输出无「N 条用例」→ 返回 0
"""

import os
import sys
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from core.steps.step6_human_test import Step6HumanTest


def _make_step(tmp_path, llm=None):
    return Step6HumanTest(str(tmp_path), config={}, llm=llm)


def _make_xlsx_with_results(path, filled=True):
    """构造带「执行结果」列的 xlsx"""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["用例编号", "执行结果"])
    ws.append(["TC-1", "通过" if filled else ""])
    wb.save(str(path))
    wb.close()


# ============================================================================
# run() — 主流程
# ============================================================================


class TestRun:
    """测试 Step6 run() 主流程"""

    def test_run_has_results_continue(self, tmp_path):
        # Excel 已填执行结果 → ok=True，继续下一步（覆盖 28-30 行）
        xlsx = tmp_path / "testcases.xlsx"
        _make_xlsx_with_results(xlsx, filled=True)
        step = _make_step(tmp_path)
        result = step.run()
        assert result.ok is True
        assert result.human is False

    def test_run_no_results_generate_guide_human(self, tmp_path):
        # 未填执行结果 → 生成指引，返回 human=True 等待（覆盖 32-42 行）
        xlsx = tmp_path / "testcases.xlsx"
        _make_xlsx_with_results(xlsx, filled=False)
        step = _make_step(tmp_path)
        with patch.object(Step6HumanTest, "_generate_execution_guide", return_value=5):
            result = step.run()
        assert result.ok is False
        assert result.human is True
        assert "人工执行" in result.error

    def test_run_no_excel_generate_guide(self, tmp_path):
        # 无 Excel 文件 → _check_has_results 返回 False → 生成指引
        step = _make_step(tmp_path)
        with patch.object(Step6HumanTest, "_generate_execution_guide", return_value=0):
            result = step.run()
        assert result.ok is False
        assert result.human is True


# ============================================================================
# _generate_execution_guide
# ============================================================================


class TestGenerateExecutionGuide:
    """测试执行指引生成（静态方法）"""

    def test_script_not_exist_returns_zero(self, tmp_path):
        # 引导脚本不存在 → 返回 0（覆盖 51 行 if not exists 分支）
        xlsx = str(tmp_path / "tc.xlsx")
        guide = str(tmp_path / "guide.md")
        # __file__ 的 resolve().parents[2] 指向项目根，其下 scripts/ 存在；
        # 用 monkeypatch 不可用（静态方法），改 patch __file__ 指向 tmp_path 下不存在的脚本
        with patch("core.steps.step6_human_test.__file__", str(tmp_path / "step6.py")):
            count = Step6HumanTest._generate_execution_guide(xlsx, guide)
        assert count == 0

    def test_script_success_extracts_count(self, tmp_path):
        # 脚本执行成功 + 输出含「N 条用例」→ 返回 N（覆盖 57-61 行）
        xlsx = str(tmp_path / "tc.xlsx")
        guide = str(tmp_path / "guide.md")
        # 让脚本路径存在：patch __file__ 使 resolve().parents[2]/scripts/... 指向真实文件
        # parents[2] 需 == tmp_path，故 __file__ 嵌套 2 层：tmp_path/a/b/step6.py
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        fake_script = scripts_dir / "generate_execution_guide.py"
        fake_script.write_text("# fake")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "已处理 42 条用例，生成指引完成"
        mock_result.stderr = ""

        nested = tmp_path / "a" / "b" / "step6.py"
        with patch("core.steps.step6_human_test.__file__", str(nested)), \
             patch("subprocess.run", return_value=mock_result):
            count = Step6HumanTest._generate_execution_guide(xlsx, guide)
        # resolve().parents[2] of tmp_path/a/b/step6.py → tmp_path → scripts/ 存在
        assert count == 42

    def test_script_success_no_count_pattern_returns_zero(self, tmp_path):
        # 脚本成功但输出无「N 条用例」→ 返回 0（覆盖 61 行 else 分支）
        xlsx = str(tmp_path / "tc.xlsx")
        guide = str(tmp_path / "guide.md")
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "generate_execution_guide.py").write_text("# fake")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "完成，无数字"
        mock_result.stderr = ""
        nested = tmp_path / "a" / "b" / "step6.py"
        with patch("core.steps.step6_human_test.__file__", str(nested)), \
             patch("subprocess.run", return_value=mock_result):
            count = Step6HumanTest._generate_execution_guide(xlsx, guide)
        assert count == 0

    def test_script_exception_returns_zero(self, tmp_path):
        # 脚本执行抛异常 → 返回 0（容灾，覆盖 62-64 行）
        xlsx = str(tmp_path / "tc.xlsx")
        guide = str(tmp_path / "guide.md")
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "generate_execution_guide.py").write_text("# fake")
        nested = tmp_path / "a" / "b" / "step6.py"
        with patch("core.steps.step6_human_test.__file__", str(nested)), \
             patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="x", timeout=5)):
            count = Step6HumanTest._generate_execution_guide(xlsx, guide)
        assert count == 0
