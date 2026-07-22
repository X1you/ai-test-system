#!/usr/bin/env python3
"""
Step2KBSearch.run() 路径单元测试

现有 test_step_pure_functions.py 已覆盖 _extract_keywords 纯函数。
本文件覆盖 run() 的完整控制流（mock dynamic_kb_manager + subprocess）：
  - 知识库未配置 → skipped
  - 配置读取异常 → skipped
  - vault_path 不存在/为空 → skipped
  - KB_SCRIPT 不存在 → skipped
  - subprocess 超时 → skipped
  - subprocess 返回非零 → skipped
  - 正常执行：命中 > 0 / 空 Vault / 冷启动 / 正常无匹配（三态区分）
"""

import os
import sys
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from core.steps import step2_kb_search
from core.steps.step2_kb_search import Step2KBSearch


def _make_step(tmp_path, llm=None):
    return Step2KBSearch(str(tmp_path), config={}, llm=llm)


def _mock_mgr(configured=True, vault_path="/tmp/fake_vault"):
    """构造一个 mock 的 dynamic_kb_manager"""
    mgr = MagicMock()
    mgr.is_configured.return_value = configured
    if configured:
        mgr.get_config.return_value = {"vault_path": vault_path}
    else:
        mgr.get_config.return_value = None
    return mgr


# ============================================================================
# run() — 各跳过路径
# ============================================================================


class TestRunSkipped:
    """测试各跳过场景（skipped=True）"""

    def test_kb_not_configured(self, tmp_path):
        # 知识库未配置 → skipped（覆盖 40-42 行）
        step = _make_step(tmp_path)
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager",
                   return_value=_mock_mgr(configured=False)):
            result = step.run()
        assert result.ok is True
        assert result.data["skipped"] is True

    def test_kb_config_read_exception(self, tmp_path):
        # 配置读取抛异常 → skipped（覆盖 45-47 行）
        step = _make_step(tmp_path)
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager",
                   side_effect=RuntimeError("db down")):
            result = step.run()
        assert result.ok is True
        assert result.data["skipped"] is True

    def test_vault_path_not_exist(self, tmp_path):
        # vault_path 指向不存在的目录 → skipped（覆盖 49-54 行）
        step = _make_step(tmp_path)
        mgr = _mock_mgr(vault_path=str(tmp_path / "nonexistent_vault"))
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr):
            result = step.run()
        assert result.ok is True
        assert result.data["skipped"] is True

    def test_vault_path_empty(self, tmp_path):
        # vault_path 为空字符串 → skipped
        step = _make_step(tmp_path)
        mgr = _mock_mgr(vault_path="")
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr):
            result = step.run()
        assert result.ok is True
        assert result.data["skipped"] is True

    def test_kb_script_not_exist(self, tmp_path):
        # KB_SCRIPT 不存在 → skipped（覆盖 56-58 行）
        vault = tmp_path / "vault"
        vault.mkdir()
        step = _make_step(tmp_path)
        mgr = _mock_mgr(vault_path=str(vault))
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr), \
             patch.object(step2_kb_search, "KB_SCRIPT", tmp_path / "no_script.py"):
            result = step.run()
        assert result.ok is True
        assert result.data["skipped"] is True

    def test_subprocess_timeout(self, tmp_path):
        # subprocess 超时 → skipped（覆盖 80-82 行）
        vault = tmp_path / "vault"
        vault.mkdir()
        step = _make_step(tmp_path)
        mgr = _mock_mgr(vault_path=str(vault))
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr), \
             patch.object(step2_kb_search, "KB_SCRIPT", Path(__file__)), \
             patch.object(step2_kb_search.subprocess, "run",
                          side_effect=subprocess.TimeoutExpired(cmd="x", timeout=1)):
            result = step.run()
        assert result.ok is True
        assert result.data["skipped"] is True

    def test_subprocess_nonzero_return(self, tmp_path):
        # subprocess 返回非零 → skipped（覆盖 84-86 行）
        vault = tmp_path / "vault"
        vault.mkdir()
        step = _make_step(tmp_path)
        mgr = _mock_mgr(vault_path=str(vault))
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "导出失败"
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr), \
             patch.object(step2_kb_search, "KB_SCRIPT", Path(__file__)), \
             patch.object(step2_kb_search.subprocess, "run", return_value=mock_result):
            result = step.run()
        assert result.ok is True
        assert result.data["skipped"] is True


# ============================================================================
# run() — 正常执行（三态区分）
# ============================================================================


class TestRunSuccess:
    """测试知识库检索正常执行的三态命中区分"""

    def _run_with_vault(self, tmp_path, vault_file_count, hits, keywords=None, analysis=None):
        """公共辅助：创建 vault + mock subprocess 写入 context 文件，返回 result"""
        vault = tmp_path / "vault"
        vault.mkdir()
        for i in range(vault_file_count):
            (vault / f"note{i}.md").write_text(f"note {i}")

        step = _make_step(tmp_path)
        mgr = _mock_mgr(vault_path=str(vault))

        def fake_run(cmd, **kw):
            # 模拟脚本写入 context 文件（根据 --output 参数定位）
            out_idx = cmd.index("--output")
            out_path = Path(cmd[out_idx + 1])
            out_path.write_text("### 命中\n" * hits)
            r = MagicMock()
            r.returncode = 0
            r.stderr = ""
            r.stdout = ""
            return r

        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr), \
             patch.object(step2_kb_search, "KB_SCRIPT", Path(__file__)), \
             patch.object(step2_kb_search.subprocess, "run", side_effect=fake_run):
            kwargs = {}
            if keywords is not None:
                kwargs["keywords"] = keywords
            if analysis is not None:
                kwargs["requirements_analysis"] = analysis
            return step.run(**kwargs)

    def test_hits_nonzero(self, tmp_path):
        # 命中 > 0 → hits 计数正确（覆盖 100-101 行）
        result = self._run_with_vault(tmp_path, vault_file_count=5, hits=3, keywords="登录")
        assert result.ok is True
        assert result.data["hits"] == 3
        assert result.data["skipped"] is False

    def test_empty_vault_zero_files(self, tmp_path):
        # Vault 为空（0 文件）→ 场景1 警告（覆盖 104-111 行）
        result = self._run_with_vault(tmp_path, vault_file_count=0, hits=0, keywords="x")
        assert result.ok is True
        assert result.data["hits"] == 0

    def test_cold_start_few_files(self, tmp_path):
        # 冷启动（<3 文件）→ 场景2 警告（覆盖 112-118 行）
        result = self._run_with_vault(tmp_path, vault_file_count=2, hits=0, keywords="x")
        assert result.ok is True
        assert result.data["hits"] == 0

    def test_normal_no_match(self, tmp_path):
        # 正常无匹配（>=3 文件，0 命中）→ 场景3（覆盖 119-125 行）
        result = self._run_with_vault(tmp_path, vault_file_count=5, hits=0, keywords="无关词")
        assert result.ok is True
        assert result.data["hits"] == 0

    def test_extract_keywords_from_analysis(self, tmp_path):
        # 无 keywords 但有 analysis → 自动提取关键词（覆盖 61-64 行）
        result = self._run_with_vault(
            tmp_path, vault_file_count=5, hits=1,
            analysis="模块一：登录\n功能点 1.1：验证",
        )
        assert result.ok is True
        assert result.data["hits"] == 1

    def test_default_keyword_when_none(self, tmp_path):
        # 无 keywords 且无 analysis → 默认关键词"测试"（覆盖 63-64 行）
        result = self._run_with_vault(tmp_path, vault_file_count=5, hits=1)
        assert result.ok is True
        assert result.data["hits"] == 1
