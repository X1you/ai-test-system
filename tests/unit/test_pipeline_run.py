#!/usr/bin/env python3
"""
core/pipeline.py 单元测试（不修改业务代码）。

覆盖范围（已有 test_pipeline_ingest_and_hash/interrupted_resume 覆盖的不再重复）：
  - 数据流恢复：_read_prd_content / _recover_total_duration /
    _recover_gap_count_from_file / _count_cases_from_excel / _read_output / _read_kb_context
  - 状态管理：load_state / save_state / mark_done / is_done / _step_output_file / _compute_file_hash
  - run() 完整执行路径（mock 所有 Step 类，驱动数据流注入与 skip/失败分支）
  - resume() / _pause / status / _init_llm / 辅助展示方法

用 unittest.mock 模拟 LLM 与各 Step，tmp_path 隔离。
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def pipeline(tmp_path):
    """构造一个 Pipeline 实例（无真实 LLM）。"""
    from core.pipeline import Pipeline

    config = {"llm": {"provider": "test", "model": "test-model", "api_key": "k", "base_url": "x"}}
    return Pipeline(config, str(tmp_path))


# ============================================================================
# 数据流恢复方法
# ============================================================================


class TestReadPrdContent:
    """测试 _read_prd_content（编码兜底）"""

    def test_existing_file(self, pipeline, tmp_path):
        prd = tmp_path / "prd.md"
        prd.write_text("# 需求\n登录功能", encoding="utf-8")
        assert "登录功能" in pipeline._read_prd_content(str(prd))

    def test_nonexistent_file_returns_empty(self, pipeline, tmp_path):
        assert pipeline._read_prd_content(str(tmp_path / "nope.md")) == ""


class TestRecoverTotalDuration:
    """测试 _recover_total_duration（断点续跑 ROI 恢复）"""

    def test_no_json_returns_zero(self, pipeline):
        assert pipeline._recover_total_duration() == 0

    def test_sum_durations(self, pipeline, tmp_path):
        cases = [
            {"estimated_duration": 10},
            {"estimated_duration": 5},
            {"estimated_duration": 8},
        ]
        (tmp_path / "testcases.json").write_text(
            json.dumps(cases, ensure_ascii=False), encoding="utf-8"
        )
        assert pipeline._recover_total_duration() == 23

    def test_invalid_json_returns_zero(self, pipeline, tmp_path):
        (tmp_path / "testcases.json").write_text("not json", encoding="utf-8")
        assert pipeline._recover_total_duration() == 0

    def test_non_list_json_returns_zero(self, pipeline, tmp_path):
        (tmp_path / "testcases.json").write_text('{"k":1}', encoding="utf-8")
        assert pipeline._recover_total_duration() == 0

    def test_non_dict_entries_skipped(self, pipeline, tmp_path):
        (tmp_path / "testcases.json").write_text(
            json.dumps([{"estimated_duration": 5}, "str", 123]),
            encoding="utf-8",
        )
        assert pipeline._recover_total_duration() == 5


class TestRecoverGapCount:
    """测试 _recover_gap_count_from_file（Step0 产物恢复）"""

    def test_no_report_returns_zero(self, pipeline):
        # 报告不存在 → 0（会打 WARN）
        assert pipeline._recover_gap_count_from_file() == 0

    def test_extract_from_report(self, pipeline, tmp_path):
        (tmp_path / "requirement_gap_analysis.md").write_text(
            "# 漏洞扫描\n\nGAP_COUNT: 7\n", encoding="utf-8"
        )
        assert pipeline._recover_gap_count_from_file() == 7

    def test_zero_with_marker_not_warned(self, pipeline, tmp_path):
        """报告明确 GAP_COUNT: 0（有标记）→ 返回 0，不算篡改"""
        (tmp_path / "requirement_gap_analysis.md").write_text(
            "# 报告\nGAP_COUNT: 0\n", encoding="utf-8"
        )
        assert pipeline._recover_gap_count_from_file() == 0

    def test_read_error_returns_zero(self, pipeline, tmp_path):
        """读取异常 → 0（不抛）"""
        report = tmp_path / "requirement_gap_analysis.md"
        report.write_text("ok", encoding="utf-8")
        with patch.object(Path, "read_text", side_effect=Exception("boom")):
            assert pipeline._recover_gap_count_from_file() == 0


class TestCountCasesFromExcel:
    """测试 _count_cases_from_excel"""

    def _make_xlsx(self, path, rows):
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.append(["编号"])
        for r in rows:
            ws.append([r])
        wb.save(str(path))
        wb.close()

    def test_no_file_returns_zero(self, pipeline, tmp_path):
        assert pipeline._count_cases_from_excel() == 0

    def test_counts_data_rows(self, pipeline, tmp_path):
        self._make_xlsx(tmp_path / "testcases.xlsx", ["TC-1", "TC-2", "TC-3"])
        assert pipeline._count_cases_from_excel() == 3

    def test_only_header_returns_zero(self, pipeline, tmp_path):
        self._make_xlsx(tmp_path / "testcases.xlsx", [])
        assert pipeline._count_cases_from_excel() == 0

    def test_corrupt_file_returns_zero(self, pipeline, tmp_path):
        (tmp_path / "testcases.xlsx").write_bytes(b"not xlsx")
        assert pipeline._count_cases_from_excel() == 0


class TestReadOutputAndKbContext:
    """测试 _read_output / _read_kb_context"""

    def test_read_output_existing(self, pipeline, tmp_path):
        (tmp_path / "foo.md").write_text("hello", encoding="utf-8")
        assert pipeline._read_output("foo.md") == "hello"

    def test_read_output_missing_returns_empty(self, pipeline):
        assert pipeline._read_output("nope.md") == ""

    def test_read_output_decode_error_returns_empty(self, pipeline, tmp_path):
        f = tmp_path / "bad.md"
        f.write_bytes(b"\xff\xfe\x00bad")
        assert pipeline._read_output("bad.md") == ""

    def test_read_kb_context_existing(self, pipeline, tmp_path):
        (tmp_path / "knowledge-context.md").write_text("KB内容", encoding="utf-8")
        assert pipeline._read_kb_context() == "KB内容"

    def test_read_kb_context_missing(self, pipeline):
        assert pipeline._read_kb_context() == ""


# ============================================================================
# 状态管理
# ============================================================================


class TestStateManagement:
    """测试 load_state / save_state / mark_done / is_done / _step_output_file"""

    def test_load_state_default(self, pipeline):
        state = pipeline.load_state()
        assert state["completed_steps"] == []
        assert state["mode"] == "semi"
        assert "started" in state

    def test_save_load_roundtrip(self, pipeline):
        state = pipeline.load_state()
        state["completed_steps"] = [0, 1]
        pipeline.save_state(state)
        loaded = pipeline.load_state()
        assert loaded["completed_steps"] == [0, 1]
        assert "updated" in loaded

    def test_mark_done_appends_and_persists(self, pipeline):
        from core.steps.base import StepResult

        state = pipeline.load_state()
        pipeline.mark_done(state, 1, StepResult(ok=True, data={"x": 1}))
        assert 1 in state["completed_steps"]
        assert state["step_results"]["1"]["ok"] is True
        # 持久化到了磁盘
        reloaded = pipeline.load_state()
        assert 1 in reloaded["completed_steps"]

    def test_mark_done_idempotent(self, pipeline):
        """重复 mark_done 同一步不重复 append"""
        from core.steps.base import StepResult

        state = pipeline.load_state()
        pipeline.mark_done(state, 2, StepResult(ok=True))
        pipeline.mark_done(state, 2, StepResult(ok=True))
        assert state["completed_steps"].count(2) == 1

    def test_mark_done_with_output_file_records_hash(self, pipeline, tmp_path):
        """mark_done 记录输出文件 hash（篡改检测用）"""
        from core.steps.base import StepResult

        (tmp_path / "requirements_analysis.md").write_text("内容", encoding="utf-8")
        state = pipeline.load_state()
        pipeline.mark_done(state, 1, StepResult(ok=True))
        assert "1" in state.get("output_hashes", {})

    def test_is_done(self, pipeline):
        from core.steps.base import StepResult

        state = pipeline.load_state()
        assert pipeline.is_done(state, 1) is False
        pipeline.mark_done(state, 1, StepResult(ok=True))
        assert pipeline.is_done(state, 1) is True

    def test_step_output_file_mapping(self, pipeline):
        assert pipeline._step_output_file(1) == "requirements_analysis.md"
        assert pipeline._step_output_file(4) == "testcases.xlsx"
        assert pipeline._step_output_file(99) == ""


class TestComputeFileHash:
    """测试 _compute_file_hash"""

    def test_existing_file(self, tmp_path):
        from core.pipeline import Pipeline

        f = tmp_path / "a.txt"
        f.write_bytes(b"hello")
        h = Pipeline._compute_file_hash(f)
        assert len(h) == 64

    def test_missing_file(self, tmp_path):
        from core.pipeline import Pipeline

        assert Pipeline._compute_file_hash(tmp_path / "nope") is None


# ============================================================================
# _init_llm
# ============================================================================


class TestInitLlm:
    """测试 _init_llm 初始化"""

    def test_success(self, pipeline):
        with patch("core.pipeline.LLMClient") as MockClient:
            pipeline._init_llm()
            MockClient.assert_called_once()

    def test_idempotent(self, pipeline):
        """重复调用不重复初始化"""
        with patch("core.pipeline.LLMClient") as MockClient:
            pipeline._init_llm()
            pipeline._init_llm()
            MockClient.assert_called_once()

    def test_failure_reraises(self, pipeline):
        from core.llm_client import LLMError

        with patch("core.pipeline.LLMClient", side_effect=LLMError("bad key")):
            with pytest.raises(LLMError):
                pipeline._init_llm()


# ============================================================================
# _pause — WebUI 非交互模式
# ============================================================================


class TestPause:
    """测试 _pause（WebUI 非交互模式直接跳过）"""

    def test_non_interactive_returns_true(self, pipeline):
        """interactive=False → 直接返回 True（WebUI 状态机管暂停）"""
        pipeline.interactive = False
        assert pipeline._pause("Step 1") is True

    def test_interactive_stop(self, pipeline, monkeypatch):
        """CLI 模式输入 s → 停止"""
        monkeypatch.setattr("builtins.input", lambda *a: "s")
        assert pipeline._pause("Step 1") is False

    def test_interactive_continue(self, pipeline, monkeypatch):
        """CLI 模式输入回车 → 继续"""
        monkeypatch.setattr("builtins.input", lambda *a: "")
        assert pipeline._pause("Step 1") is True

    def test_interactive_eof_continues(self, pipeline, monkeypatch):
        """非交互环境 EOFError → 默认继续"""
        monkeypatch.setattr("builtins.input", MagicMock(side_effect=EOFError))
        assert pipeline._pause("Step 1") is True


# ============================================================================
# resume()
# ============================================================================


class TestResume:
    """测试 resume() 断点续跑入口"""

    def test_no_state_returns_none(self, pipeline, monkeypatch):
        """无 requirements_file → 返回 None"""
        monkeypatch.setattr("builtins.input", lambda *a: "")
        pipeline.interactive = False  # 防止 _pause 卡住
        # 不写 state，直接 resume
        assert pipeline.resume() is None

    def test_resume_calls_run(self, pipeline, monkeypatch):
        """有 state → 调用 run()"""
        pipeline.interactive = False
        # 预置 state
        state = pipeline.load_state()
        state["requirements_file"] = "/fake/path.md"
        pipeline.save_state(state)

        called = {}
        def fake_run(req, **kw):
            called["req"] = req
            called["mode"] = kw.get("mode")
            return state
        monkeypatch.setattr(pipeline, "run", fake_run)
        pipeline.resume()
        assert called["req"] == "/fake/path.md"
        assert called["mode"] == "auto"


# ============================================================================
# run() — 完整执行路径（mock 所有 Step）
# ============================================================================


def _patch_all_steps(monkeypatch):
    """把 pipeline.run() 内用到的所有 Step 类替换为返回成功的 MagicMock。

    每个 mock Step 的 .run() 返回 ok=True 的 StepResult。
    """
    from core.steps.base import StepResult

    ok_result = StepResult(ok=True, data={"gap_count": 3})
    ok_result1 = StepResult(ok=True, data={})
    ok_result4 = StepResult(ok=True, data={
        "case_count": 5, "total_duration": 30, "methodology": "llm_v3", "negative_ratio": 0.5
    })

    def make_step_cls(result=None):
        cls = MagicMock()
        instance = MagicMock()
        instance.run.return_value = result or ok_result1
        cls.return_value = instance
        return cls

    # 用 side_effect 按调用顺序返回不同结果
    step0_cls = MagicMock()
    step0_inst = MagicMock()
    step0_inst.run.return_value = StepResult(ok=True, data={"gap_count": 3, "degraded": False})
    step0_cls.return_value = step0_inst

    step4_cls = MagicMock()
    step4_inst = MagicMock()
    step4_inst.run.return_value = ok_result4
    step4_cls.return_value = step4_inst

    monkeypatch.setattr("core.pipeline.Step0GapAnalysis", step0_cls)
    monkeypatch.setattr("core.pipeline.Step1Analysis", make_step_cls())
    monkeypatch.setattr("core.pipeline.Step2KBSearch", make_step_cls())
    monkeypatch.setattr("core.pipeline.Step3Testpoints", make_step_cls())
    monkeypatch.setattr("core.pipeline.Step4Generate", step4_cls)
    monkeypatch.setattr("core.pipeline.Step5Review", make_step_cls())
    monkeypatch.setattr("core.pipeline.Step6HumanTest", make_step_cls())
    monkeypatch.setattr("core.pipeline.Step7Report", make_step_cls())


class TestRunExecution:
    """测试 run() 全流程驱动"""

    def test_auto_mode_full_run(self, pipeline, tmp_path, monkeypatch):
        """auto 模式：所有步骤成功，完整跑完 0-7"""
        _patch_all_steps(monkeypatch)
        pipeline.interactive = False  # 跳过 pause
        # mock LLM 初始化
        monkeypatch.setattr("core.pipeline.LLMClient", MagicMock())
        # mock 知识库回灌（未配置 → 返回0，不阻塞）
        # 预置需求文档
        req = tmp_path / "req.md"
        req.write_text("# 需求", encoding="utf-8")

        # 需要预置 step2 依赖的 requirements_analysis.md（run 直接 read_text）
        (tmp_path / "requirements_analysis.md").write_text("# 分析", encoding="utf-8")
        (tmp_path / "testpoints.md").write_text("# 测试点", encoding="utf-8")

        state = pipeline.run(str(req), mode="auto")

        assert state is not None
        # 所有步骤都应完成
        assert set(state["completed_steps"]) >= {0, 1, 2, 3, 4, 5, 7}

    def test_step1_failure_auto_terminates(self, pipeline, tmp_path, monkeypatch):
        """auto 模式 Step1 失败 → 终止"""
        from core.steps.base import StepResult

        _patch_all_steps(monkeypatch)
        pipeline.interactive = False
        monkeypatch.setattr("core.pipeline.LLMClient", MagicMock())

        # Step0 成功，Step1 失败
        step1_cls = MagicMock()
        step1_inst = MagicMock()
        step1_inst.run.return_value = StepResult(ok=False, error="LLM 挂了")
        step1_cls.return_value = step1_inst
        monkeypatch.setattr("core.pipeline.Step1Analysis", step1_cls)

        req = tmp_path / "req.md"
        req.write_text("# 需求", encoding="utf-8")
        state = pipeline.run(str(req), mode="auto")
        # Step1 失败终止，1 不应在 completed
        assert 1 not in state["completed_steps"]

    def test_step4_failure_terminates(self, pipeline, tmp_path, monkeypatch):
        """Step4 失败 → 终止（Step4 是关键步骤）"""
        from core.steps.base import StepResult

        _patch_all_steps(monkeypatch)
        pipeline.interactive = False
        monkeypatch.setattr("core.pipeline.LLMClient", MagicMock())

        step4_cls = MagicMock()
        step4_inst = MagicMock()
        step4_inst.run.return_value = StepResult(ok=False, error="生成失败")
        step4_cls.return_value = step4_inst
        monkeypatch.setattr("core.pipeline.Step4Generate", step4_cls)

        req = tmp_path / "req.md"
        req.write_text("# 需求", encoding="utf-8")
        (tmp_path / "requirements_analysis.md").write_text("# 分析", encoding="utf-8")
        (tmp_path / "testpoints.md").write_text("# 测试点", encoding="utf-8")

        state = pipeline.run(str(req), mode="auto")
        assert 4 not in state["completed_steps"]

    def test_skip_completed_steps(self, pipeline, tmp_path, monkeypatch):
        """已完成的步骤被跳过"""
        _patch_all_steps(monkeypatch)
        pipeline.interactive = False
        monkeypatch.setattr("core.pipeline.LLMClient", MagicMock())

        # 预置全部步骤已完成的状态 + 产物文件
        state = pipeline.load_state()
        state["completed_steps"] = [0, 1, 2, 3, 4, 5, 6, 7]
        for meta_file in [
            "requirement_gap_analysis.md", "requirements_analysis.md",
            "knowledge-context.md", "testpoints.md", "testcases.xlsx",
            "test_case_review_report.md", "test_report.md",
        ]:
            (tmp_path / meta_file).write_text("done", encoding="utf-8")
        # 补充 output_hashes（篡改检测需要）
        from core.pipeline import Pipeline
        state["output_hashes"] = {}
        for i, f in enumerate([
            "requirement_gap_analysis.md", "requirements_analysis.md",
            "knowledge-context.md", "testpoints.md", "testcases.xlsx",
            "test_case_review_report.md", "testcases.xlsx", "test_report.md",
        ]):
            h = Pipeline._compute_file_hash(tmp_path / f)
            if h:
                state["output_hashes"][str(i)] = h
        # step6 需要 _has_results 返回 True 才跳过
        state["step_results"] = {str(i): {"ok": True} for i in range(8)}
        pipeline.save_state(state)

        req = tmp_path / "req.md"
        req.write_text("# 需求", encoding="utf-8")

        state = pipeline.run(str(req), mode="auto")
        # 跳过的步骤仍在 completed
        assert set(state["completed_steps"]) == {0, 1, 2, 3, 4, 5, 6, 7}

    def test_step6_human_pause(self, pipeline, tmp_path, monkeypatch):
        """Step6 人工步骤未填结果 → 暂停返回（不继续到 Step7）"""
        from core.steps.base import StepResult

        _patch_all_steps(monkeypatch)
        pipeline.interactive = False
        monkeypatch.setattr("core.pipeline.LLMClient", MagicMock())

        # Step6 返回 human=True（需要人工）
        step6_cls = MagicMock()
        step6_inst = MagicMock()
        step6_inst.run.return_value = StepResult(ok=False, error="等待人工", human=True)
        step6_cls.return_value = step6_inst
        monkeypatch.setattr("core.pipeline.Step6HumanTest", step6_cls)

        req = tmp_path / "req.md"
        req.write_text("# 需求", encoding="utf-8")
        (tmp_path / "requirements_analysis.md").write_text("# 分析", encoding="utf-8")
        (tmp_path / "testpoints.md").write_text("# 测试点", encoding="utf-8")

        state = pipeline.run(str(req), mode="auto")
        # Step7 不应执行
        assert 7 not in state["completed_steps"]
        assert 6 not in state["completed_steps"]

    def test_step0_gap_count_injected(self, pipeline, tmp_path, monkeypatch):
        """Step0 的 gap_count 注入 context（数据流闭环）"""
        _patch_all_steps(monkeypatch)
        pipeline.interactive = False
        monkeypatch.setattr("core.pipeline.LLMClient", MagicMock())

        req = tmp_path / "req.md"
        req.write_text("# 需求", encoding="utf-8")
        (tmp_path / "requirements_analysis.md").write_text("# 分析", encoding="utf-8")
        (tmp_path / "testpoints.md").write_text("# 测试点", encoding="utf-8")

        pipeline.run(str(req), mode="auto")
        # _patch_all_steps 里 Step0 返回 gap_count=3
        assert pipeline.context["gap_count"] == 3

    def test_step4_context_injected(self, pipeline, tmp_path, monkeypatch):
        """Step4 的 case_count/total_duration 注入 context"""
        _patch_all_steps(monkeypatch)
        pipeline.interactive = False
        monkeypatch.setattr("core.pipeline.LLMClient", MagicMock())

        req = tmp_path / "req.md"
        req.write_text("# 需求", encoding="utf-8")
        (tmp_path / "requirements_analysis.md").write_text("# 分析", encoding="utf-8")
        (tmp_path / "testpoints.md").write_text("# 测试点", encoding="utf-8")

        pipeline.run(str(req), mode="auto")
        assert pipeline.context["case_count"] == 5
        assert pipeline.context["total_duration"] == 30


# ============================================================================
# status() / 展示方法（不崩即可）
# ============================================================================


class TestDisplayMethods:
    """测试 status / banner / summary 等展示方法（验证不抛异常）"""

    def test_status_no_crash(self, pipeline, capsys):
        pipeline.status()
        captured = capsys.readouterr()
        assert "Pipeline 状态" in captured.out

    def test_print_banner(self, pipeline, capsys):
        pipeline._print_banner("auto", "req.md")
        out = capsys.readouterr().out
        assert "Pipeline 启动" in out

    def test_print_step6_guide(self, pipeline, tmp_path, capsys):
        pipeline._print_step6_guide(tmp_path / "tc.xlsx", 10)
        out = capsys.readouterr().out
        assert "Step 6" in out

    def test_show_step_summary(self, pipeline, capsys):
        pipeline._show_step_summary()
        # 不抛异常即可
        capsys.readouterr()

    def test_print_summary(self, pipeline, capsys):
        state = pipeline.load_state()
        pipeline._print_summary(state)
        out = capsys.readouterr().out
        assert "执行完成" in out
