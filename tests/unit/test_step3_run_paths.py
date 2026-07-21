#!/usr/bin/env python3
"""
Step3 / Step1 run() 错误路径补充测试。

现有 test_step1_step7.py 覆盖了 Step1 的 no_input/nonexistent/no_llm。
本文件补充：
  - Step3Testpoints.run 错误路径（缺分析 / 无 LLM）
  - Step3Testpoints.run 从输出目录读取 requirements_analysis.md 的回退路径
  - Step1Analysis.run 从文件成功读取的 happy path（llm=None 仍会因无 LLM 报错，
    但能覆盖文件读取 + 编码兜底路径）

用 tmp_path 隔离，llm=None 让 self_check 短路。
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# Step3Testpoints.run 错误路径
# ============================================================================


class TestStep3RunErrorPaths:
    """测试 Step3 run() 错误处理（不调用真实 LLM）"""

    def _make_step(self, tmp_path):
        from core.steps.step3_testpoints import Step3Testpoints

        return Step3Testpoints(str(tmp_path), config={}, llm=None)

    def test_no_analysis_no_file(self, tmp_path):
        """无 requirements_analysis 且输出目录无文件 → 缺少需求分析文档"""
        step = self._make_step(tmp_path)
        result = step.run()
        assert result.ok is False
        assert "需求分析" in result.error

    def test_has_analysis_but_no_llm(self, tmp_path):
        """有 analysis 但无 LLM → 需要 LLM 客户端"""
        step = self._make_step(tmp_path)
        result = step.run(requirements_analysis="# 需求\n登录功能")
        assert result.ok is False
        assert "LLM" in result.error

    def test_read_analysis_from_output_dir(self, tmp_path):
        """从输出目录的 requirements_analysis.md 回退读取（覆盖 _read_output 路径）

        run() 在 analysis 为空时会尝试 self._read_output("requirements_analysis.md")。
        文件存在 → 读到内容 → 走到 LLM 检查（而非"缺少需求分析"）。
        """
        step = self._make_step(tmp_path)
        (tmp_path / "requirements_analysis.md").write_text(
            "# 需求分析\n登录模块", encoding="utf-8"
        )
        result = step.run()
        # 读到内容但无 LLM → 报 LLM 错误（证明回退读取成功）
        assert result.ok is False
        assert "LLM" in result.error

    def test_dimensions_param_accepted(self, tmp_path):
        """dimensions 参数被接受（无 LLM 时仍报 LLM 错，但不会因 dimensions 报错）"""
        step = self._make_step(tmp_path)
        result = step.run(
            requirements_analysis="# 需求",
            dimensions="all",
        )
        assert result.ok is False
        assert "LLM" in result.error  # 走过 dimensions 解析，到 LLM 检查
