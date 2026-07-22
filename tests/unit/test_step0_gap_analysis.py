#!/usr/bin/env python3
"""
Step0GapAnalysis.run() 路径单元测试

现有 test_step0_gap_pure.py 已覆盖 _safe_read_text / _extract_gap_count 纯函数。
本文件覆盖 run() 的完整控制流路径（不调用真实 LLM）：
  - 降级保护：外层异常 → gap_count=0，ok=True
  - 多种输入来源：requirements_text / requirements_path(存在/不存在)
  - 编码无法识别 → 降级
  - 无需求输入 / 无 LLM → 跳过
  - LLM 调用失败（LLMError）→ 降级报告
  - LLM 调用成功 → 解析 gap_count，写报告
  - _safe_read_text 异常兜底分支
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from core.llm_client import LLMError
from core.steps.step0_gap_analysis import Step0GapAnalysis


def _make_step(tmp_path, llm=None):
    """构造 Step0 实例，llm 为 MagicMock 或 None"""
    return Step0GapAnalysis(str(tmp_path), config={}, llm=llm)


# ============================================================================
# run() — 成功路径（LLM 返回带 GAP_COUNT）
# ============================================================================


class TestRunSuccess:
    """测试正常 LLM 扫描流程"""

    def test_run_with_text_llm_success(self, tmp_path):
        # 传入文本 + mock LLM 成功 → 解析 gap_count，写报告
        llm = MagicMock()
        llm.chat_with_retry.return_value = (
            "# 漏洞扫描报告\n\n### 漏洞 1：缺失\n### 漏洞 2：歧义\n\nGAP_COUNT: 2\n"
        )
        step = _make_step(tmp_path, llm=llm)
        result = step.run(requirements_text="某需求文档内容")

        assert result.ok is True
        assert result.data["gap_count"] == 2
        assert result.data["degraded"] is False
        # 报告已写入
        report = step._read_output(step.output_file)
        assert report is not None
        assert "GAP_COUNT: 2" in report

    def test_run_with_path_success(self, tmp_path):
        # 传入文件路径 + mock LLM 成功
        req = tmp_path / "req.md"
        req.write_text("# 需求\n登录功能", encoding="utf-8")
        llm = MagicMock()
        llm.chat_with_retry.return_value = "扫描完成\nGAP_COUNT: 3\n"
        step = _make_step(tmp_path, llm=llm)
        result = step.run(requirements_path=str(req))

        assert result.ok is True
        assert result.data["gap_count"] == 3


# ============================================================================
# run() — 降级路径（ok 始终 True）
# ============================================================================


class TestRunDegraded:
    """测试各降级场景（ok=True, gap_count=0）"""

    def test_run_nonexistent_path(self, tmp_path):
        # 需求文档路径不存在 → 降级跳过（覆盖 75-76 行）
        llm = MagicMock()
        step = _make_step(tmp_path, llm=llm)
        result = step.run(requirements_path=str(tmp_path / "nope.md"))
        assert result.ok is True
        assert result.data["gap_count"] == 0
        assert result.data["degraded"] is True

    def test_run_no_input(self, tmp_path):
        # 既无 text 也无 path → 降级跳过（覆盖 90-91 行）
        llm = MagicMock()
        step = _make_step(tmp_path, llm=llm)
        result = step.run()
        assert result.ok is True
        assert result.data["gap_count"] == 0
        assert result.data.get("degraded") is True

    def test_run_no_llm(self, tmp_path):
        # 有文本但无 LLM → 降级跳过（覆盖 95-96 行）
        step = _make_step(tmp_path, llm=None)
        result = step.run(requirements_text="需求")
        assert result.ok is True
        assert result.data["gap_count"] == 0
        assert result.data["degraded"] is True

    def test_run_undecodable_file(self, tmp_path):
        # 二进制文件无法解码 → 降级（覆盖 80-88 行）
        req = tmp_path / "bin.dat"
        req.write_bytes(bytes(range(256)) * 4)  # 高替换字符占比
        llm = MagicMock()
        step = _make_step(tmp_path, llm=llm)
        result = step.run(requirements_path=str(req))
        assert result.ok is True
        assert result.data["gap_count"] == 0
        assert result.data["degraded"] is True

    def test_run_llm_error(self, tmp_path):
        # LLM 调用抛 LLMError → 降级报告（覆盖 107-114 行）
        llm = MagicMock()
        llm.chat_with_retry.side_effect = LLMError("timeout")
        step = _make_step(tmp_path, llm=llm)
        result = step.run(requirements_text="需求")
        assert result.ok is True
        assert result.data["gap_count"] == 0
        assert result.data["degraded"] is True
        assert "timeout" in result.data.get("error", "")


# ============================================================================
# run() — 外层异常保护（44-58 行）
# ============================================================================


class TestRunOuterExceptionGuard:
    """测试最外层 try-except 容灾降级"""

    def test_run_inner_exception_degrades(self, tmp_path):
        # _run_inner 内部抛非 LLMError 异常 → 被外层 catch 降级
        llm = MagicMock()
        step = _make_step(tmp_path, llm=llm)
        with patch.object(step, "_run_inner", side_effect=ValueError("unexpected")):
            result = step.run(requirements_text="需求")
        assert result.ok is True  # 降级不算失败
        assert result.data["gap_count"] == 0
        assert result.data["degraded"] is True

    def test_run_outer_exception_write_fail_still_ok(self, tmp_path):
        # 外层异常 + 降级报告写入也失败 → 仍返回 ok=True（覆盖 55-57 行）
        llm = MagicMock()
        step = _make_step(tmp_path, llm=llm)
        with patch.object(step, "_run_inner", side_effect=ValueError("boom")), \
             patch.object(step, "_write_output", side_effect=OSError("disk full")):
            result = step.run(requirements_text="需求")
        assert result.ok is True
        assert result.data["gap_count"] == 0


# ============================================================================
# _safe_read_text — 异常兜底分支（161-165 行）
# ============================================================================


class TestSafeReadTextFallback:
    """测试 _safe_read_text 多编码兜底（纯二进制降级分支）"""

    def test_binary_file_returns_none(self, tmp_path):
        # 纯二进制（替换字符占比 >30%）→ None
        p = tmp_path / "bin.dat"
        p.write_bytes(bytes(range(256)) * 4)
        assert Step0GapAnalysis._safe_read_text(p) is None

    def test_gb18030_decode(self, tmp_path):
        # gb18030 编码兜底路径
        p = tmp_path / "g.md"
        p.write_bytes("需求内容".encode("gb18030"))
        assert "需求内容" in Step0GapAnalysis._safe_read_text(p)

    def test_partial_binary_returns_text(self, tmp_path):
        # 含少量非法字节但占比 <30% → 返回替换后的文本（非 None）
        p = tmp_path / "mix.md"
        # 正常 UTF-8 文本 + 少量非法字节
        p.write_bytes("正常文本内容较多".encode("utf-8") + b"\xff\xfe")
        result = Step0GapAnalysis._safe_read_text(p)
        assert result is not None
        assert "正常文本" in result
