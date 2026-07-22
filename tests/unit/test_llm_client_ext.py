#!/usr/bin/env python3
"""
core/llm_client.py 补充单元测试

覆盖（不调用真实 LLM API）：
  - __init__ 错误路径：缺 model / 缺 api_key
  - enable_cache
  - chat(): 缓存命中 / 正常调用 / 异常包装 / usage 统计 / 缓存写入
  - async_chat(): 缓存命中 / 正常调用 / 异常包装（asyncio.run 驱动）
  - chat_with_retry(): 多次失败后重试 / 最终失败抛 last_error / 成功直接返回
  - evaluate(): 正常解析 / 解析失败降级 / score 判定 passed
  - stats 属性 / __repr__
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from core.llm_client import LLMClient, LLMError


# ============================================================================
# 辅助：构造 client（mock 掉 OpenAI 构造，不连真实网络）
# ============================================================================


def _make_client(**overrides) -> LLMClient:
    """构造一个不触网的真实 LLMClient（OpenAI 构造被 patch 掉）"""
    cfg = {
        "provider": "test-provider",
        "model": "test-model",
        "api_key": "sk-test",
        "base_url": "http://localhost",
        "temperature": 0.3,
        "max_tokens": 128,
        "timeout": 5,
        "retry": 2,
    }
    cfg.update(overrides)
    with patch("core.llm_client.OpenAI"), patch("core.llm_client.AsyncOpenAI"):
        return LLMClient(cfg)


def _mk_choice(content, total_tokens: int = 0):
    """构造一个假的 chat.completions.create 响应"""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = MagicMock(total_tokens=total_tokens) if total_tokens else None
    return resp


# ============================================================================
# __init__ 错误路径
# ============================================================================


class TestInitErrors:
    """测试构造校验"""

    def test_missing_model_raises(self):
        # 缺 model 字段应抛 LLMError
        with patch("core.llm_client.OpenAI"):
            with pytest.raises(LLMError, match="model"):
                LLMClient({"api_key": "k"})

    def test_missing_api_key_raises(self):
        # 缺 api_key 应抛 LLMError（覆盖第 49 行）
        with patch("core.llm_client.OpenAI"):
            with pytest.raises(LLMError, match="API Key"):
                LLMClient({"model": "m"})

    def test_repr(self):
        # __repr__ 应包含 provider 和 model（覆盖第 306 行）
        c = _make_client()
        r = repr(c)
        assert "test-provider" in r
        assert "test-model" in r


# ============================================================================
# enable_cache
# ============================================================================


class TestEnableCache:
    """测试缓存挂载"""

    def test_enable_cache_sets_flag(self):
        # enable_cache 后 _use_cache 应为 True（覆盖 70-71 行）
        c = _make_client()
        assert c._use_cache is False
        cache = MagicMock()
        c.enable_cache(cache)
        assert c._use_cache is True
        assert c._cache is cache


# ============================================================================
# chat()
# ============================================================================


class TestChat:
    """测试同步单轮对话"""

    def test_chat_success(self):
        # 正常调用返回内容，_call_count +1（覆盖 111-118 行）
        c = _make_client()
        c.client.chat.completions.create.return_value = _mk_choice("hello", 42)
        result = c.chat("hi")
        assert result == "hello"
        assert c._call_count == 1
        assert c._total_tokens == 42

    def test_chat_with_system_prompt(self):
        # 带 system 时 messages 应含 system 角色行
        c = _make_client()
        c.client.chat.completions.create.return_value = _mk_choice("ok")
        c.chat("hi", system="you are bot")
        sent = c.client.chat.completions.create.call_args.kwargs["messages"]
        assert sent[0]["role"] == "system"
        assert sent[1]["role"] == "user"

    def test_chat_no_usage(self):
        # usage 为 None 时不累加 token（走 response.usage falsy 分支）
        c = _make_client()
        c.client.chat.completions.create.return_value = _mk_choice("x", 0)
        c.chat("hi")
        assert c._total_tokens == 0

    def test_chat_empty_content_returns_empty(self):
        # content 为 None 时返回空字符串（message.content or ""）
        c = _make_client()
        c.client.chat.completions.create.return_value = _mk_choice(None)
        # _mk_choice(None) → msg.content=None
        assert c.chat("hi") == ""

    def test_chat_exception_wrapped(self):
        # 底层异常应包装为 LLMError（覆盖 120-121 行）
        c = _make_client()
        c.client.chat.completions.create.side_effect = RuntimeError("network down")
        with pytest.raises(LLMError, match="LLM 调用失败"):
            c.chat("hi")

    def test_chat_cache_hit(self):
        # 缓存命中直接返回，不调用 API（覆盖 99-102 行）
        c = _make_client()
        cache = MagicMock()
        cache.get.return_value = "cached-result"
        c.enable_cache(cache)
        # temperature=0 才走缓存
        result = c.chat("prompt", system="sys", temperature=0)
        assert result == "cached-result"
        assert c._call_count == 1
        c.client.chat.completions.create.assert_not_called()

    def test_chat_cache_miss_writes_cache(self):
        # 缓存未命中 → 调用 API → 结果写回缓存（覆盖 116-117 行）
        c = _make_client()
        cache = MagicMock()
        cache.get.return_value = None
        c.enable_cache(cache)
        c.client.chat.completions.create.return_value = _mk_choice("fresh")
        result = c.chat("p", temperature=0)
        assert result == "fresh"
        cache.set.assert_called_once()

    def test_chat_custom_temperature_overrides(self):
        # 传入 temperature 覆盖默认值
        c = _make_client()
        c.client.chat.completions.create.return_value = _mk_choice("ok")
        c.chat("hi", temperature=0.9)
        assert c.client.chat.completions.create.call_args.kwargs["temperature"] == 0.9


# ============================================================================
# async_chat()
# ============================================================================


class TestAsyncChat:
    """测试异步单轮对话（用 asyncio.run 驱动）"""

    def test_async_chat_success(self):
        # 正常异步调用返回内容（覆盖 130-165 行主体）
        c = _make_client()
        c._async_client = MagicMock()
        c._async_client.chat.completions.create = AsyncMock(
            return_value=_mk_choice("async-hello", 10)
        )
        result = asyncio.run(c.async_chat("hi"))
        assert result == "async-hello"
        assert c._call_count == 1
        assert c._total_tokens == 10

    def test_async_chat_with_system(self):
        # 带 system 异步调用
        c = _make_client()
        c._async_client = MagicMock()
        c._async_client.chat.completions.create = AsyncMock(
            return_value=_mk_choice("ok")
        )
        asyncio.run(c.async_chat("hi", system="bot"))
        sent = c._async_client.chat.completions.create.call_args.kwargs["messages"]
        assert sent[0]["role"] == "system"

    def test_async_chat_creates_client_if_none(self):
        # _async_client 为 None 时应惰性创建 AsyncOpenAI
        c = _make_client()
        assert c._async_client is None
        fake_async = MagicMock()
        fake_async.chat.completions.create = AsyncMock(
            return_value=_mk_choice("lazy")
        )
        with patch("core.llm_client.AsyncOpenAI", return_value=fake_async):
            result = asyncio.run(c.async_chat("hi"))
        assert result == "lazy"

    def test_async_chat_exception_wrapped(self):
        # 异步底层异常应包装为 LLMError（覆盖 167-168 行）
        c = _make_client()
        c._async_client = MagicMock()
        c._async_client.chat.completions.create = AsyncMock(
            side_effect=RuntimeError("async fail")
        )
        with pytest.raises(LLMError, match="异步调用失败"):
            asyncio.run(c.async_chat("hi"))

    def test_async_chat_cache_hit(self):
        # 缓存命中异步路径（覆盖 138-142 行）
        c = _make_client()
        cache = MagicMock()
        cache.get.return_value = "cached-async"
        c.enable_cache(cache)
        c._async_client = MagicMock()
        c._async_client.chat.completions.create = AsyncMock()
        result = asyncio.run(c.async_chat("p", temperature=0))
        assert result == "cached-async"
        c._async_client.chat.completions.create.assert_not_called()

    def test_async_chat_cache_miss_writes(self):
        # 缓存未命中 → 异步调用 → 写回缓存（覆盖 163-164 行）
        c = _make_client()
        cache = MagicMock()
        cache.get.return_value = None
        c.enable_cache(cache)
        c._async_client = MagicMock()
        c._async_client.chat.completions.create = AsyncMock(
            return_value=_mk_choice("fresh-async")
        )
        result = asyncio.run(c.async_chat("p", temperature=0))
        assert result == "fresh-async"
        cache.set.assert_called_once()


# ============================================================================
# chat_with_retry()
# ============================================================================


class TestChatWithRetry:
    """测试带重试的对话"""

    def test_success_first_try(self):
        # 第一次就成功，不重试
        c = _make_client()
        with patch.object(c, "chat", return_value="ok") as m:
            result = c.chat_with_retry("hi")
        assert result == "ok"
        assert m.call_count == 1

    def test_retries_then_success(self):
        # 前两次失败，第三次成功（覆盖重试循环 + sleep）
        c = _make_client()
        with patch.object(c, "chat", side_effect=[LLMError("e1"), LLMError("e2"), "ok"]) as m, \
             patch("core.llm_client.time.sleep"):
            result = c.chat_with_retry("hi", retries=2, delay=0)
        assert result == "ok"
        assert m.call_count == 3

    def test_all_fail_raises_last_error(self):
        # 全部失败 → 抛出 last_error（覆盖第 205 行）
        c = _make_client()
        last = LLMError("final")
        with patch.object(c, "chat", side_effect=last), \
             patch("core.llm_client.time.sleep"):
            with pytest.raises(LLMError, match="final"):
                c.chat_with_retry("hi", retries=1, delay=0)

    def test_uses_config_retry_count_default(self):
        # 不传 retries 时用 self.retry_count
        c = _make_client(retry=3)
        mock_chat = MagicMock(side_effect=LLMError("x"))
        with patch.object(c, "chat", mock_chat), \
             patch("core.llm_client.time.sleep"):
            with pytest.raises(LLMError):
                c.chat_with_retry("hi", delay=0)
        assert mock_chat.call_count == 4  # retry_count + 1


# ============================================================================
# evaluate()
# ============================================================================


class TestEvaluate:
    """测试质量自检 evaluate"""

    def test_evaluate_pass(self):
        # score >= 70 → passed=True（覆盖 223-254 行正常路径）
        c = _make_client()
        raw = '{"score": 85, "issues": ["小问题"], "suggestions": ["建议"]}'
        with patch.object(c, "chat", return_value=raw):
            result = c.evaluate("content", "criteria")
        assert result["score"] == 85
        assert result["passed"] is True
        assert result["issues"] == ["小问题"]

    def test_evaluate_fail_low_score(self):
        # score < 70 → passed=False
        c = _make_client()
        raw = '{"score": 40, "issues": ["严重"], "suggestions": []}'
        with patch.object(c, "chat", return_value=raw):
            result = c.evaluate("c", "cr")
        assert result["passed"] is False

    def test_evaluate_missing_issues_suggestions_setdefault(self):
        # 缺 issues/suggestions 字段 → setdefault 补空列表（覆盖 252-253 行）
        c = _make_client()
        raw = '{"score": 90}'
        with patch.object(c, "chat", return_value=raw):
            result = c.evaluate("c", "cr")
        assert result["issues"] == []
        assert result["suggestions"] == []

    def test_evaluate_chat_exception_returns_degraded(self):
        # chat 抛异常 → 返回降级结果（覆盖 255-261 行）
        c = _make_client()
        with patch.object(c, "chat", side_effect=LLMError("boom")):
            result = c.evaluate("c", "cr")
        assert result["score"] == 0
        assert result["passed"] is False
        assert result["suggestions"] == []
        assert any("自检解析失败" in i for i in result["issues"])

    def test_evaluate_score_defaults_to_zero(self):
        # 无 score 字段 → 默认 0
        c = _make_client()
        raw = '{"issues": []}'
        with patch.object(c, "chat", return_value=raw):
            result = c.evaluate("c", "cr")
        assert result["score"] == 0
        assert result["passed"] is False


# ============================================================================
# stats 属性
# ============================================================================


class TestStats:
    """测试调用统计属性"""

    def test_stats_initial(self):
        # 初始统计：call_count=0, total_tokens=0
        c = _make_client()
        s = c.stats
        assert s["call_count"] == 0
        assert s["total_tokens"] == 0
        assert s["provider"] == "test-provider"
        assert s["model"] == "test-model"

    def test_stats_after_calls(self):
        # 调用后统计应更新
        c = _make_client()
        c.client.chat.completions.create.return_value = _mk_choice("x", 5)
        c.chat("a")
        c.chat("b")
        assert c.stats["call_count"] == 2
        assert c.stats["total_tokens"] == 10
