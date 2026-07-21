#!/usr/bin/env python3
"""
Step3 分模块调用单元测试（P3-A）

验证核心逻辑：模块提取、输出合并、编号重排、降级策略。
不依赖真实 LLM（mock chat_with_retry）。
"""

import re
from unittest.mock import MagicMock, patch

import pytest

from core.steps.step3_testpoints import Step3Testpoints


# ── 测试数据 ──

SAMPLE_ANALYSIS_4_MODULES = """# 需求拆解

## 模块一：用户管理
- 功能点 1.1：注册
  - 可测项：邮箱格式校验、密码强度校验
- 功能点 1.2：登录
  - 可测项：密码验证、Token 生成

## 模块二：知识库管理
- 功能点 2.1：文档导入
  - 可测项：Markdown 解析、文件大小限制
- 功能点 2.2：全文搜索
  - 可测项：中文分词、模糊匹配

## 模块三：Pipeline 编排
- 功能点 3.1：流程启动
  - 可测项：参数校验、权限检查
- 功能点 3.2：进度追踪
  - 可测项：实时日志、状态更新

## 模块四：报告生成
- 功能点 4.1：Excel 导出
  - 可测项：格式校验、数据完整性
- 功能点 4.2：Markdown 报告
  - 可测项：模板渲染、统计图表

==========================================

## 待确认事项
（省略）
"""

SAMPLE_ANALYSIS_1_MODULE = """# 需求拆解

## 模块一：简单功能
- 功能点 1.1：基本操作
  - 可测项：基本验证
"""

MODULE_OUTPUT_TEMPLATE = """### 功能点 1.1：{feature}

#### 测试维度：正向测试
- 测试点 1.1.1：{feature} 正向
  - 描述：验证正常流程
  - 预期结果：成功
  - 优先级：P0

#### 测试维度：负向测试
- 测试点 1.1.2：{feature} 负向
  - 描述：验证异常输入
  - 预期结果：拒绝
  - 优先级：P1
"""


class TestExtractModules:
    """模块提取测试"""

    def test_extract_4_modules(self):
        modules = Step3Testpoints._extract_modules(SAMPLE_ANALYSIS_4_MODULES)
        assert len(modules) == 4
        assert modules[0]["name"] == "用户管理"
        assert modules[1]["name"] == "知识库管理"
        assert modules[2]["name"] == "Pipeline 编排"
        assert modules[3]["name"] == "报告生成"

    def test_extract_module_content_boundaries(self):
        modules = Step3Testpoints._extract_modules(SAMPLE_ANALYSIS_4_MODULES)
        # 模块1的内容应包含"注册"但不包含"文档导入"
        assert "注册" in modules[0]["content"]
        assert "文档导入" not in modules[0]["content"]
        # 模块2应包含"全文搜索"但不包含"流程启动"
        assert "全文搜索" in modules[1]["content"]
        assert "流程启动" not in modules[1]["content"]

    def test_extract_single_module(self):
        modules = Step3Testpoints._extract_modules(SAMPLE_ANALYSIS_1_MODULE)
        assert len(modules) == 1

    def test_extract_no_modules_fallback(self):
        """无模块标题时返回全文作为一个模块"""
        text = "这是一段没有模块标题的普通文本需求分析"
        modules = Step3Testpoints._extract_modules(text)
        assert len(modules) == 1
        assert modules[0]["name"] == "全部"

    def test_extract_alternative_format(self):
        """备用格式：## 1. 模块名"""
        text = "## 1. 第一个模块\n- 功能A\n\n## 2. 第二个模块\n- 功能B"
        modules = Step3Testpoints._extract_modules(text)
        assert len(modules) == 2
        assert modules[0]["name"] == "第一个模块"
        assert modules[1]["name"] == "第二个模块"


class TestMergeOutputs:
    """输出合并与编号重排测试"""

    def test_merge_renumbers_modules(self):
        """合并后模块编号应从 1 开始连续"""
        step = _make_step()
        modules = [
            {"name": "用户管理", "content": ""},
            {"name": "知识库管理", "content": ""},
        ]
        results = {
            "用户管理": "### 功能点 1.1：注册\n- 测试点 1.1.1：正向\n- 测试点 1.1.2：负向",
            "知识库管理": "### 功能点 1.1：导入\n- 测试点 1.1.1：正向\n- 测试点 1.1.2：负向",
        }
        merged = step._merge_module_outputs(modules, results)
        # 第一个模块编号应为 1.x.y
        assert "## 模块一：用户管理" in merged
        assert "## 模块二：知识库管理" in merged
        # 第一个模块的内容中编号从 1 开始
        assert "测试点 1.1.1" in merged
        # 第二个模块的编号应被重排为 2.x.y
        assert "测试点 2.1.1" in merged

    def test_merge_skips_missing_results(self):
        """模块生成失败时不包含在合并结果中"""
        step = _make_step()
        modules = [
            {"name": "模块A", "content": ""},
            {"name": "模块B", "content": ""},
        ]
        results = {"模块A": "内容A"}
        merged = step._merge_module_outputs(modules, results)
        assert "模块A" in merged
        # 模块B不在结果中，不应出现
        assert "模块B" not in merged

    def test_merge_preserves_dimension_headers(self):
        """合并后测试维度标题应保留"""
        step = _make_step()
        modules = [{"name": "测试模块", "content": ""}]
        results = {
            "测试模块": "#### 测试维度：正向测试\n- 测试点 1.1.1：验证"
        }
        merged = step._merge_module_outputs(modules, results)
        assert "#### 测试维度：正向测试" in merged


class TestRoutingLogic:
    """路由逻辑测试（单次 vs 分模块）"""

    def test_small_doc_uses_single_mode(self):
        """模块数 ≤ 阈值走单次调用"""
        step = _make_step()
        mock_llm = MagicMock()
        mock_llm.chat_with_retry.return_value = "# 测试点清单\n- 测试点 1.1.1：验证"
        step.llm = mock_llm

        with patch("core.steps.step3_testpoints.load_prompt", return_value="模板 {requirements_analysis} {kb_context} {dimensions_config}"):
            with patch.object(step, "self_check", return_value={"score": 85, "passed": True, "issues": []}):
                result = step.run(
                    requirements_analysis=SAMPLE_ANALYSIS_1_MODULE,
                    dimensions="basic",
                )
        assert result.ok
        # 单次调用应只调用一次 chat_with_retry
        assert mock_llm.chat_with_retry.call_count == 1

    def test_large_doc_uses_per_module_mode(self):
        """模块数 > 阈值走分模块调用"""
        step = _make_step()
        mock_llm = MagicMock()
        mock_llm.chat_with_retry.return_value = "### 功能点 1.1：测试\n- 测试点 1.1.1：验证"
        step.llm = mock_llm

        with patch("core.steps.step3_testpoints.load_prompt", return_value_value="模板"):
            with patch.object(step, "self_check", return_value={"score": 85, "passed": True, "issues": []}):
                result = step.run(
                    requirements_analysis=SAMPLE_ANALYSIS_4_MODULES,
                    dimensions="basic",
                )
        assert result.ok
        # 4 模块应调用 4 次 chat_with_retry
        assert mock_llm.chat_with_retry.call_count == 4

    def test_per_module_returns_coverage_info(self):
        """分模块模式返回 modules_covered/modules_total"""
        step = _make_step()
        mock_llm = MagicMock()
        mock_llm.chat_with_retry.return_value = "### 功能点 1.1：测试\n- 测试点 1.1.1：验证"
        step.llm = mock_llm

        with patch("core.steps.step3_testpoints.load_prompt", return_value="模板"):
            with patch.object(step, "self_check", return_value={"score": 85, "passed": True, "issues": []}):
                result = step.run(
                    requirements_analysis=SAMPLE_ANALYSIS_4_MODULES,
                    dimensions="basic",
                )
        assert result.ok
        assert result.data["modules_covered"] == 4
        assert result.data["modules_total"] == 4


class TestConcurrentSafety:
    """并发调用安全性测试"""

    def test_all_modules_called_even_on_partial_failure(self):
        """部分模块 LLM 失败时其他模块仍正常完成"""
        step = _make_step()
        mock_llm = MagicMock()
        call_count = [0]

        def _side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                from core.llm_client import LLMError
                raise LLMError("模拟第2个模块失败")
            return f"### 功能点 1.1：模块{call_count[0]}\n- 测试点 1.1.1：验证"

        mock_llm.chat_with_retry.side_effect = _side_effect
        step.llm = mock_llm

        with patch("core.steps.step3_testpoints.load_prompt", return_value="模板"):
            with patch.object(step, "self_check", return_value={"score": 80, "passed": True, "issues": []}):
                result = step.run(
                    requirements_analysis=SAMPLE_ANALYSIS_4_MODULES,
                    dimensions="basic",
                )
        # 有部分成功就算成功（3/4 覆盖）
        assert result.ok
        assert result.data["modules_covered"] == 3
        assert result.data["modules_total"] == 4


# ── 辅助 ──

def _make_step() -> Step3Testpoints:
    """创建测试用 Step3 实例（不依赖真实输出目录）"""
    from pathlib import Path
    import tempfile
    step = Step3Testpoints.__new__(Step3Testpoints)
    step.output_dir = Path(tempfile.mkdtemp())
    step.llm = None
    step.config = {}
    step.log = lambda msg, level="INFO": None  # type: ignore
    step.self_check = lambda text, criteria="": {"score": 85, "passed": True, "issues": []}  # type: ignore
    step._write_output = lambda filename, content: None  # type: ignore
    step._read_output = lambda filename: None  # type: ignore
    return step
