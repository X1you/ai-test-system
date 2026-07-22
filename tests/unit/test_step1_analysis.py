#!/usr/bin/env python3
"""
Step1Analysis.run() 路径单元测试

现有 test_step1_step7.py 已覆盖 _split_response 纯函数和 run() 错误路径。
本文件覆盖：
  - run() 完整成功路径（mock LLM + self_check 满分短路）
  - run() 成功路径（mock LLM + self_check 未过 → 重跑）
  - run() 重跑失败兜底（LLMError → 用原始输出）
  - run() LLM 主调用失败（LLMError → ok=False）
  - _safe_read_requirement 各路径（含二进制降级 + read_bytes 异常兜底）
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from core.llm_client import LLMError
from core.steps.step1_analysis import Step1Analysis


def _make_step(tmp_path, llm=None, config=None):
    """构造 Step1 实例"""
    return Step1Analysis(str(tmp_path), config=config or {}, llm=llm)


# ============================================================================
# run() — 成功路径
# ============================================================================


class TestRunSuccess:
    """测试需求分析成功流程"""

    def test_run_success_self_check_disabled(self, tmp_path):
        # config 无 self_check → self_check 短路满分，不重跑
        llm = MagicMock()
        response = (
            "# 需求拆解\n\n## 模块一：登录\n- 功能点 1.1：账号登录\n"
            "\n==========================================\n\n"
            "1. **待确认A**\n"
        )
        llm.chat_with_retry.return_value = response
        step = _make_step(tmp_path, llm=llm)
        result = step.run(requirements_text="# 需求文档\n登录功能")

        assert result.ok is True
        assert result.data["modules"] >= 1
        # 文件已写入
        assert step._read_output("requirements_analysis.md") is not None
        assert step._read_output("clarification_needed.md") is not None

    def test_run_success_with_self_check_pass(self, tmp_path):
        # 开启 self_check 且通过（>=70）→ 不重跑
        llm = MagicMock()
        llm.chat_with_retry.return_value = (
            "# 拆解\n## 模块一：A\n- 功能点 1.1：x\n"
            "\n==========================================\n\n1. **确认**\n"
        )
        llm.evaluate.return_value = {"score": 90, "passed": True, "issues": [], "suggestions": []}
        cfg = {"pipeline": {"self_check": True}}
        step = _make_step(tmp_path, llm=llm, config=cfg)
        result = step.run(requirements_text="需求")
        assert result.ok is True
        assert result.data["check_score"] == 90
        llm.chat.assert_not_called()  # 通过不重跑

    def test_run_self_check_fail_retry_success(self, tmp_path):
        # self_check 未过 → 带 issues 重跑一次（覆盖 96-108 行）
        llm = MagicMock()
        first = "# 拆解\n## 模块一：A\n- 功能点 1.1：x"
        retry = "# 改进拆解\n## 模块一：A\n- 功能点 1.1：y"
        llm.chat_with_retry.return_value = first
        llm.chat.return_value = retry
        llm.evaluate.return_value = {
            "score": 50, "passed": False,
            "issues": ["覆盖不全"], "suggestions": ["补充"],
        }
        cfg = {"pipeline": {"self_check": True}}
        step = _make_step(tmp_path, llm=llm, config=cfg)
        result = step.run(requirements_text="需求")
        assert result.ok is True
        llm.chat.assert_called_once()  # 触发了重跑
        # 写入的是重跑后的内容
        assert "改进拆解" in step._read_output("requirements_analysis.md")

    def test_run_self_check_fail_retry_error_uses_original(self, tmp_path):
        # self_check 未过 + 重跑抛 LLMError → 用原始输出（覆盖 109-110 行）
        llm = MagicMock()
        first = "# 拆解\n## 模块一：A\n- 功能点 1.1：x"
        llm.chat_with_retry.return_value = first
        llm.chat.side_effect = LLMError("retry boom")
        llm.evaluate.return_value = {
            "score": 40, "passed": False, "issues": ["x"], "suggestions": [],
        }
        cfg = {"pipeline": {"self_check": True}}
        step = _make_step(tmp_path, llm=llm, config=cfg)
        result = step.run(requirements_text="需求")
        assert result.ok is True
        # 仍写入原始输出
        assert "拆解" in step._read_output("requirements_analysis.md")

    def test_run_no_clarification_section(self, tmp_path):
        # LLM 输出无待确认部分 → 只写 analysis，不写 clarification
        llm = MagicMock()
        llm.chat_with_retry.return_value = "# 纯拆解\n## 模块一：A"
        step = _make_step(tmp_path, llm=llm)
        result = step.run(requirements_text="需求")
        assert result.ok is True
        assert step._read_output("requirements_analysis.md") is not None
        # 无分隔 → clarification_md 为空，不写 clarification_needed.md
        assert step._read_output("clarification_needed.md") is None
        assert result.data["clarifications"] == 0


# ============================================================================
# run() — LLM 调用失败
# ============================================================================


class TestRunLLMError:
    """测试 LLM 主调用失败"""

    def test_run_llm_with_retry_raises(self, tmp_path):
        # chat_with_retry 抛 LLMError → ok=False（覆盖 71-73 行）
        llm = MagicMock()
        llm.chat_with_retry.side_effect = LLMError("api down")
        step = _make_step(tmp_path, llm=llm)
        result = step.run(requirements_text="需求")
        assert result.ok is False
        assert "api down" in result.error

    def test_run_empty_analysis_after_split(self, tmp_path):
        # LLM 输出拆分后 analysis_md 为空 → 格式异常（覆盖 78-80 行）
        llm = MagicMock()
        # 分隔线在最前面 → analysis 部分为空
        llm.chat_with_retry.return_value = "\n==========================================\n待确认"
        step = _make_step(tmp_path, llm=llm)
        result = step.run(requirements_text="需求")
        assert result.ok is False
        assert "格式异常" in result.error


# ============================================================================
# _safe_read_requirement — 多编码 + 降级
# ============================================================================


class TestSafeReadRequirement:
    """测试需求文档安全读取"""

    def test_utf8(self, tmp_path):
        p = tmp_path / "r.md"
        p.write_text("# 需求\n登录", encoding="utf-8")
        assert "登录" in Step1Analysis._safe_read_requirement(p)

    def test_gbk(self, tmp_path):
        p = tmp_path / "g.md"
        p.write_bytes("需求文档".encode("gbk"))
        assert "需求文档" in Step1Analysis._safe_read_requirement(p)

    def test_empty_file(self, tmp_path):
        p = tmp_path / "e.md"
        p.write_bytes(b"")
        assert Step1Analysis._safe_read_requirement(p) == ""

    def test_binary_returns_none(self, tmp_path):
        # 纯二进制 → None（覆盖 46-49 行 run 中 content is None 分支）
        p = tmp_path / "b.dat"
        p.write_bytes(bytes(range(256)) * 4)
        assert Step1Analysis._safe_read_requirement(p) is None

    def test_run_binary_file_error(self, tmp_path):
        # run() 读取二进制文件 → content None → 报编码错误（覆盖 46-49 行）
        p = tmp_path / "b.dat"
        p.write_bytes(bytes(range(256)) * 4)
        llm = MagicMock()
        step = _make_step(tmp_path, llm=llm)
        result = step.run(requirements_path=str(p))
        assert result.ok is False
        assert "编码" in result.error

    def test_gb18030_decode(self, tmp_path):
        # gb18030 编码兜底路径
        p = tmp_path / "g.md"
        p.write_bytes("需求内容".encode("gb18030"))
        assert "需求内容" in Step1Analysis._safe_read_requirement(p)

    def test_partial_binary_returns_text(self, tmp_path):
        # 含少量非法字节但占比 <30% → 返回替换后的文本
        p = tmp_path / "mix.md"
        p.write_bytes("正常文本内容较多".encode("utf-8") + b"\xff\xfe")
        result = Step1Analysis._safe_read_requirement(p)
        assert result is not None
        assert "正常文本" in result
