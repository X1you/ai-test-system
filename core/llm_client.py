#!/usr/bin/env python3
"""
LLM 抽象层 — 多协议统一调用

支持的协议（protocols）：
  - openai_compatible : OpenAI 兼容协议（覆盖 DeepSeek/GLM/OpenAI/Moonshot/Qwen 等）
  - anthropic         : Anthropic Messages API（裸 HTTP 调，无需 anthropic SDK）
  - custom_http       : 自定义 HTTP 端点（用户自填 body 模板 + 响应字段路径）

设计目标：
  - 单 LLMClient 类多协议：根据 config["protocol"] 自动选择实现
  - 向后兼容：旧 LLMClient(config) 调用方式不破坏（默认 openai_compatible）
  - 共享 chat/async_chat/evaluate/chat_with_retry/enable_cache/stats 接口
  - 模块级 OpenAI/AsyncOpenAI 名字保留（测试 patch 用）

核心方法：
  - chat()            单轮对话（同步）
  - async_chat()      单轮对话（异步）
  - chat_with_retry() 带重试的对话
  - evaluate()        质量自检（返回评分 + 问题清单）
  - test_connection() 健康检查用最小请求
"""

import asyncio
import json
import re
import sys
import time
from abc import ABC, abstractmethod
from typing import Any

from openai import AsyncOpenAI, OpenAI

from core.llm_cache import LLMCache
from core.llm_usage import usage_stats


class LLMError(Exception):
    """LLM 调用异常"""


# ─── 协议实现常量 ───

PROTOCOL_OPENAI = "openai_compatible"
PROTOCOL_ANTHROPIC = "anthropic"
PROTOCOL_CUSTOM_HTTP = "custom_http"

# 所有内置协议集合（用于校验）
SUPPORTED_PROTOCOLS = frozenset({PROTOCOL_OPENAI, PROTOCOL_ANTHROPIC, PROTOCOL_CUSTOM_HTTP})


# ============================================================================
# 抽象基类
# ============================================================================


class BaseLLMClient(ABC):
    """协议无关的 LLM 客户端抽象基类。

    所有具体协议（OpenAI 兼容 / Anthropic / Custom HTTP）都继承本类。
    共享逻辑：enable_cache / chat_with_retry / evaluate / stats / __repr__
    协议特定逻辑：__init__ 校验 + chat / async_chat 实际调用
    """

    # 子类必须定义：协议名称
    protocol: str = "unknown"

    def __init__(self, config: dict):
        """
        Args:
            config: 单个 provider 的配置字典
                必含: model
                可选: provider, name, base_url, temperature, max_tokens, timeout, retry, protocol
                api_key: 默认需要（OpenAI 协议）；Custom HTTP 协议可空

        字段语义：
          - name: 用户起的别名（唯一标识，用于断路器、统计、UI 显示）
          - provider: vendor 标识（OpenAI/DeepSeek/GLM/Anthropic 等，统计维度）
        """
        # 三个字段优先级：name > provider > 兜底 "unknown"
        _id = config.get("name") or config.get("provider") or "unknown"
        self.name = _id
        self.provider = config.get("provider") or _id
        self.model = config.get("model", "")
        self.temperature = config.get("temperature", 0.3)
        self.max_tokens = config.get("max_tokens", 8192)
        self.timeout = config.get("timeout", 120)
        self.retry_count = config.get("retry", 2)
        self.base_url = config.get("base_url", "")

        self.api_key = config.get("api_key", "")

        if not self.model:
            raise LLMError(
                f"[{self.provider}] LLM model 未配置。请设置 model 字段。"
            )
        # api_key 校验下放到子类（OpenAI/Anthropic 必填，Custom HTTP 可空）

        # 调用统计
        self._call_count = 0
        self._total_tokens = 0
        self._error_count = 0
        self._last_error: str | None = None

        # 缓存层（可选）
        self._cache: LLMCache | None = None
        self._use_cache = config.get("cache_enabled", False)

    # ─── 抽象方法（子类必须实现）───

    @abstractmethod
    def _do_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        timeout: float | None = None,
    ) -> tuple[str, int]:
        """同步单轮对话底层调用。

        Args:
            timeout: 可选覆盖客户端默认 timeout（健康检查/测试场景用）。
                     None 表示使用 self.timeout（构建时确定的默认值）。

        Returns:
            (content, total_tokens)
        """

    @abstractmethod
    async def _async_do_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        timeout: float | None = None,
    ) -> tuple[str, int]:
        """异步单轮对话底层调用。

        Args:
            timeout: 可选覆盖客户端默认 timeout（健康检查/测试场景用）。
                     None 表示使用 self.timeout（构建时确定的默认值）。

        Returns:
            (content, total_tokens)
        """

    # ─── 共享方法 ───

    def enable_cache(self, cache: LLMCache) -> None:
        """挂载 LLM 调用缓存"""
        self._cache = cache
        self._use_cache = True

    def _build_messages(self, prompt: str, system: str | None) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return messages

    def chat(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float | None = None,
    ) -> str:
        """单轮对话（同步）"""
        messages = self._build_messages(prompt, system)
        temp = temperature if temperature is not None else self.temperature
        max_tokens = self.max_tokens

        # 缓存命中（仅在 temperature=0 时启用，避免采样结果变化）
        if self._cache and self._use_cache and temp == 0:
            cached = self._cache.get(self.model, system or "", prompt, temp)
            if cached is not None:
                self._call_count += 1
                return cached

        try:
            _start = time.monotonic()
            content, tokens = self._do_chat(messages, temp, max_tokens)
            self._call_count += 1
            self._total_tokens += tokens
            if self._cache and self._use_cache and temp == 0:
                self._cache.set(self.model, system or "", prompt, content, temp)
            usage_stats.record_call(
                provider=self.provider,
                model=self.model,
                success=True,
                tokens=tokens,
                latency_ms=(time.monotonic() - _start) * 1000,
            )
            return content
        except Exception as e:
            self._error_count += 1
            self._last_error = str(e)[:200]
            usage_stats.record_call(
                provider=self.provider,
                model=self.model,
                success=False,
                latency_ms=(time.monotonic() - _start) * 1000,
                error_msg=str(e),
            )
            raise LLMError(f"[{self.provider}] LLM 调用失败: {e}") from e

    async def async_chat(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float | None = None,
    ) -> str:
        """单轮对话（异步）"""
        messages = self._build_messages(prompt, system)
        temp = temperature if temperature is not None else self.temperature
        max_tokens = self.max_tokens

        if self._cache and self._use_cache and temp == 0:
            cached = self._cache.get(self.model, system or "", prompt, temp)
            if cached is not None:
                self._call_count += 1
                return cached

        try:
            _start = time.monotonic()
            content, tokens = await self._async_do_chat(messages, temp, max_tokens)
            self._call_count += 1
            self._total_tokens += tokens
            if self._cache and self._use_cache and temp == 0:
                self._cache.set(self.model, system or "", prompt, content, temp)
            usage_stats.record_call(
                provider=self.provider,
                model=self.model,
                success=True,
                tokens=tokens,
                latency_ms=(time.monotonic() - _start) * 1000,
            )
            return content
        except Exception as e:
            self._error_count += 1
            self._last_error = str(e)[:200]
            usage_stats.record_call(
                provider=self.provider,
                model=self.model,
                success=False,
                latency_ms=(time.monotonic() - _start) * 1000,
                error_msg=str(e),
            )
            raise LLMError(f"[{self.provider}] LLM 异步调用失败: {e}") from e

    def chat_with_retry(
        self,
        prompt: str,
        system: str | None = None,
        retries: int | None = None,
        delay: float = 2.0,
    ) -> str:
        """带重试的对话"""
        max_attempts = (retries if retries is not None else self.retry_count) + 1
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                return self.chat(prompt, system=system)
            except LLMError as e:
                last_error = e
                if attempt < max_attempts:
                    print(
                        f"  ⚠️  LLM 调用失败（第 {attempt}/{max_attempts} 次），"
                        f"{delay}s 后重试: {e}",
                        file=sys.stderr,
                    )
                    time.sleep(delay)

        raise last_error  # type: ignore[misc]

    def evaluate(self, content: str, criteria: str) -> dict:
        """质量自检 — LLM 回头评估自己的输出"""
        eval_prompt = f"""请作为一个严格的质量审查员，评估以下内容的质量。

评估标准：
{criteria}

待评估内容：
---
{content}
---

请以严格的 JSON 格式返回评估结果（不要包含 markdown 代码块标记）：
{{
    "score": <0-100的整数>,
    "issues": ["问题1", "问题2"],
    "suggestions": ["建议1", "建议2"]
}}

要求：
- score 低于 70 表示不合格，需要改进
- issues 列出具体的质量问题（空列表表示没问题）
- suggestions 给出可操作的改进建议
"""
        try:
            raw = self.chat(eval_prompt, system="你是测试质量审查专家。", temperature=0.1)
            result = self._parse_json_response(raw)
            score = int(result.get("score", 0))
            result["score"] = score
            result["passed"] = score >= 70
            result.setdefault("issues", [])
            result.setdefault("suggestions", [])
            return result
        except Exception as e:
            return {
                "score": 0,
                "passed": False,
                "issues": [f"自检解析失败: {e}"],
                "suggestions": [],
            }

    def test_connection(self, timeout: float = 10.0) -> dict:
        """健康检查用最小请求（max_tokens=1，验证连通性 + API Key 有效性）。

        Returns:
            {
                "ok": bool,
                "status": "ok" | "degraded: <reason>" | "not_configured",
                "latency_ms": int,
                "provider": str,
                "model": str,
                "protocol": str,
            }
        """
        if not self.api_key or not self.model:
            # Custom HTTP 协议允许 api_key 留空（自建代理场景）
            # 若 model 和 api_key 都为空才算 not_configured
            missing: list[str] = []
            if not self.model:
                missing.append("model")
            if not self.api_key and self.protocol != PROTOCOL_CUSTOM_HTTP:
                missing.append("api_key")
            # Custom HTTP 还需要 endpoint
            if self.protocol == PROTOCOL_CUSTOM_HTTP and not (self.base_url or getattr(self, "endpoint", "")):
                missing.append("endpoint")
            if missing:
                return {
                    "ok": False,
                    "status": "not_configured" if len(missing) > 1 else f"missing: {missing[0]}",
                    "latency_ms": 0,
                    "provider": self.provider,
                    "model": self.model,
                    "protocol": self.protocol,
                }
        start = time.monotonic()
        try:
            messages = [{"role": "user", "content": "hi"}]
            # 不同协议 max_tokens 处理不同
            # 显式传入 timeout，覆盖客户端构建时设定的默认值（健康检查应快速失败）
            content, _ = self._do_chat(messages, 0.0, 1, timeout=timeout)
            latency_ms = int((time.monotonic() - start) * 1000)
            return {
                "ok": True,
                "status": "ok",
                "latency_ms": latency_ms,
                "provider": self.provider,
                "model": self.model,
                "protocol": self.protocol,
            }
        except Exception as e:
            latency_ms = int((time.monotonic() - start) * 1000)
            err = str(e)[:200]
            return {
                "ok": False,
                "status": f"degraded: {err}",
                "latency_ms": latency_ms,
                "provider": self.provider,
                "model": self.model,
                "protocol": self.protocol,
            }

    async def async_test_connection(self, timeout: float = 10.0) -> dict:
        """异步版健康检查"""
        if not self.api_key or not self.model:
            # Custom HTTP 协议允许 api_key 留空（自建代理场景）
            # 若 model 和 api_key 都为空才算 not_configured
            missing: list[str] = []
            if not self.model:
                missing.append("model")
            if not self.api_key and self.protocol != PROTOCOL_CUSTOM_HTTP:
                missing.append("api_key")
            # Custom HTTP 还需要 endpoint
            if self.protocol == PROTOCOL_CUSTOM_HTTP and not (self.base_url or getattr(self, "endpoint", "")):
                missing.append("endpoint")
            if missing:
                return {
                    "ok": False,
                    "status": "not_configured" if len(missing) > 1 else f"missing: {missing[0]}",
                    "latency_ms": 0,
                    "provider": self.provider,
                    "model": self.model,
                    "protocol": self.protocol,
                }
        start = time.monotonic()
        try:
            messages = [{"role": "user", "content": "hi"}]
            # 显式传入 timeout，覆盖客户端默认 timeout（健康检查应快速失败）
            content, _ = await self._async_do_chat(messages, 0.0, 1, timeout=timeout)
            latency_ms = int((time.monotonic() - start) * 1000)
            return {
                "ok": True,
                "status": "ok",
                "latency_ms": latency_ms,
                "provider": self.provider,
                "model": self.model,
                "protocol": self.protocol,
            }
        except Exception as e:
            latency_ms = int((time.monotonic() - start) * 1000)
            err = str(e)[:200]
            return {
                "ok": False,
                "status": f"degraded: {err}",
                "latency_ms": latency_ms,
                "provider": self.provider,
                "model": self.model,
                "protocol": self.protocol,
            }

    @staticmethod
    def _parse_json_response(raw: str) -> dict:
        """容错解析 LLM 的 JSON 输出"""
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {}

    @property
    def stats(self) -> dict:
        """调用统计"""
        return {
            "provider": self.provider,
            "model": self.model,
            "protocol": self.protocol,
            "call_count": self._call_count,
            "total_tokens": self._total_tokens,
            "error_count": self._error_count,
            "last_error": self._last_error,
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(provider={self.provider}, model={self.model})"


# ============================================================================
# 协议 1：OpenAI 兼容（覆盖 DeepSeek/GLM/OpenAI/Moonshot/Qwen 等）
# ============================================================================


class OpenAICompatibleClient(BaseLLMClient):
    """OpenAI Chat Completions 协议客户端。

    适用于：
      - OpenAI 官方（https://api.openai.com/v1）
      - DeepSeek（https://api.deepseek.com/v1）
      - 智谱 GLM（https://open.bigmodel.cn/api/paas/v4）
      - 月之暗面 Moonshot（https://api.moonshot.cn/v1）
      - 通义千问（https://dashscope.aliyuncs.com/compatible-mode/v1）
      - 其他任何兼容 OpenAI /v1/chat/completions 的服务
    """

    protocol = PROTOCOL_OPENAI

    def __init__(self, config: dict):
        super().__init__(config)
        if not self.api_key:
            raise LLMError(
                f"[{self.provider}] OpenAI 兼容协议需要 API Key。"
            )
        # OpenAI SDK 期望 base_url 不含 /chat/completions 后缀
        # 防御：用户可能误填完整端点，自动剥离并写回 self.base_url
        base = (self.base_url or "").rstrip("/")
        if base.endswith("/chat/completions"):
            base = base[: -len("/chat/completions")]
        self.base_url = base
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=base,
            timeout=self.timeout,
        )
        self._async_client: AsyncOpenAI | None = None

    def _get_async_client(self) -> AsyncOpenAI:
        if self._async_client is None:
            base = (self.base_url or "").rstrip("/")
            if base.endswith("/chat/completions"):
                base = base[: -len("/chat/completions")]
            self._async_client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=base,
                timeout=self.timeout,
            )
        return self._async_client

    def _do_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        timeout: float | None = None,
    ) -> tuple[str, int]:
        # timeout 覆盖：每次调用临时构造新 client 是昂贵操作，
        # 因此通过 OpenAI SDK 的 per-call timeout 覆盖（SDK 支持）
        call_kwargs: dict = {"model": self.model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}  # type: ignore[arg-type]
        if timeout is not None:
            call_kwargs["timeout"] = timeout
        response = self.client.chat.completions.create(**call_kwargs)
        content = response.choices[0].message.content or ""
        tokens = response.usage.total_tokens if response.usage else 0
        return content, tokens

    async def _async_do_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        timeout: float | None = None,
    ) -> tuple[str, int]:
        client = self._get_async_client()
        call_kwargs: dict = {"model": self.model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}  # type: ignore[arg-type]
        if timeout is not None:
            call_kwargs["timeout"] = timeout
        response = await client.chat.completions.create(**call_kwargs)
        content = response.choices[0].message.content or ""
        tokens = response.usage.total_tokens if response.usage else 0
        return content, tokens


# ============================================================================
# 协议 2：Anthropic（Claude 全系列）
# ============================================================================


class AnthropicClient(BaseLLMClient):
    """Anthropic Messages API 客户端（裸 HTTP 实现，不依赖 anthropic SDK）。

    API 端点：POST {base_url}/v1/messages
    必填头：x-api-key, anthropic-version: 2023-06-01, content-type: application/json
    必填字段：model, max_tokens（Anthropic 强制要求 max_tokens，不像 OpenAI 可选）
    """

    protocol = PROTOCOL_ANTHROPIC
    ANTHROPIC_VERSION = "2023-06-01"

    def __init__(self, config: dict):
        super().__init__(config)
        if not self.api_key:
            raise LLMError(
                f"[{self.provider}] Anthropic 协议需要 API Key (x-api-key)。"
            )
        if not self.base_url:
            self.base_url = "https://api.anthropic.com"
        else:
            base = self.base_url.rstrip("/")
            # 防御：用户可能误填 /v1/messages
            if base.endswith("/v1/messages"):
                base = base[: -len("/v1/messages")]
            self.base_url = base
        # 兜底 max_tokens：Anthropic 强制必填，且不能超过 4096（Claude 3）
        if self.max_tokens > 4096:
            self.max_tokens = 4096
        # 延迟导入 httpx（openai>=1.0 已传递依赖 httpx，但显式声明更稳）
        import httpx

        self._httpx = httpx

    def _endpoint(self) -> str:
        base = (self.base_url or "").rstrip("/")
        if base.endswith("/v1"):
            return f"{base}/messages"
        return f"{base}/v1/messages"

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": self.ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

    def _build_body(
        self, messages: list[dict[str, str]], temperature: float, max_tokens: int
    ) -> dict:
        # Anthropic API：system 字段独立，不在 messages 里
        system_text = None
        user_messages = []
        for m in messages:
            if m["role"] == "system":
                system_text = m["content"]
            else:
                user_messages.append(m)
        body: dict[str, Any] = {
            "model": self.model,
            "messages": user_messages,
            "max_tokens": max_tokens,
        }
        if system_text:
            body["system"] = system_text
        if temperature is not None:
            body["temperature"] = temperature
        return body

    def _do_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        timeout: float | None = None,
    ) -> tuple[str, int]:
        body = self._build_body(messages, temperature, max_tokens)
        resp = self._httpx.post(
            self._endpoint(),
            headers=self._headers(),
            json=body,
            timeout=timeout if timeout is not None else self.timeout,
        )
        if resp.status_code >= 400:
            # Anthropic 错误响应是 JSON
            try:
                err = resp.json()
                msg = err.get("error", {}).get("message", resp.text[:200])
            except Exception:
                msg = resp.text[:200]
            raise RuntimeError(f"Anthropic {resp.status_code}: {msg}")
        data = resp.json()
        # 响应结构：{"content": [{"type": "text", "text": "..."}, ...], "usage": {"input_tokens":N, "output_tokens":N}}
        content_parts = data.get("content", [])
        text = "".join(p.get("text", "") for p in content_parts if p.get("type") == "text")
        usage = data.get("usage", {})
        tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        return text, tokens

    async def _async_do_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        timeout: float | None = None,
    ) -> tuple[str, int]:
        body = self._build_body(messages, temperature, max_tokens)
        effective_timeout = timeout if timeout is not None else self.timeout
        async with self._httpx.AsyncClient(timeout=effective_timeout) as client:
            resp = await client.post(
                self._endpoint(),
                headers=self._headers(),
                json=body,
            )
        if resp.status_code >= 400:
            try:
                err = resp.json()
                msg = err.get("error", {}).get("message", resp.text[:200])
            except Exception:
                msg = resp.text[:200]
            raise RuntimeError(f"Anthropic {resp.status_code}: {msg}")
        data = resp.json()
        content_parts = data.get("content", [])
        text = "".join(p.get("text", "") for p in content_parts if p.get("type") == "text")
        usage = data.get("usage", {})
        tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        return text, tokens


# ============================================================================
# 协议 3：Custom HTTP（自建 LLM 代理 / 自定义网关）
# ============================================================================


class CustomHTTPClient(BaseLLMClient):
    """自定义 HTTP 端点客户端。

    用户在 config 中提供：
      - endpoint: 完整 URL（含 protocol+host+path）
      - method: HTTP 方法（默认 POST）
      - headers: 额外请求头（dict，可选）
      - body_template: JSON 字符串模板，含以下占位符：
          {{prompt}}      用户消息内容
          {{system}}      系统提示（可空）
          {{model}}       模型名
          {{messages}}    OpenAI 格式 messages 数组（JSON 字符串）
      - response_path: 从响应 JSON 中取文本字段的路径（如 "data.text" 或 "choices[0].message.content"）
        支持简单点号路径 + [index] 数组下标
    """

    protocol = PROTOCOL_CUSTOM_HTTP

    def __init__(self, config: dict):
        super().__init__(config)
        # Custom HTTP 校验更宽松：api_key 可选（自建代理可能不需要）
        # 但 model + endpoint 必填
        self.endpoint = config.get("endpoint", "") or self.base_url
        self.method = (config.get("method", "POST") or "POST").upper()
        self.extra_headers = config.get("headers", {}) or {}
        self.body_template = config.get("body_template", "") or ""
        self.response_path = config.get("response_path", "text") or "text"
        if not self.endpoint:
            raise LLMError(
                f"[{self.provider}] Custom HTTP 协议需要 endpoint 配置"
            )
        if not self.body_template:
            # 兜底模板：把 prompt 放到 prompt 字段
            self.body_template = '{"model": "{{model}}", "prompt": "{{prompt}}"}'
        import httpx

        self._httpx = httpx

    def _render_body(self, messages: list[dict[str, str]]) -> str:
        """渲染 body 模板，把占位符替换为真实值"""
        # 提取 system 和 prompt
        system_text = ""
        user_prompt = ""
        for m in messages:
            if m["role"] == "system":
                system_text = m["content"]
            elif m["role"] == "user":
                user_prompt = m["content"]
        body = self.body_template
        body = body.replace("{{model}}", self.model)
        body = body.replace("{{system}}", system_text)
        body = body.replace("{{prompt}}", user_prompt)
        body = body.replace("{{messages}}", json.dumps(messages, ensure_ascii=False))
        return body

    def _extract_text(self, data: Any) -> str:
        """按 response_path 从响应中取文本"""
        path = self.response_path.strip()
        if not path:
            return str(data)
        cur: Any = data
        # 支持 a.b[0].c 语法
        for token in re.findall(r"\w+|\[\d+\]", path):
            if token.startswith("["):
                idx = int(token[1:-1])
                if isinstance(cur, list) and 0 <= idx < len(cur):
                    cur = cur[idx]
                else:
                    return ""
            else:
                if isinstance(cur, dict):
                    cur = cur.get(token)
                else:
                    return ""
        if cur is None:
            return ""
        return str(cur)

    def _do_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        timeout: float | None = None,
    ) -> tuple[str, int]:
        body_str = self._render_body(messages)
        try:
            body_json = json.loads(body_str)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"body_template 不是合法 JSON: {e}")
        headers = {"content-type": "application/json", **self.extra_headers}
        if self.api_key:
            headers.setdefault("authorization", f"Bearer {self.api_key}")
        resp = self._httpx.request(
            self.method,
            self.endpoint,
            headers=headers,
            json=body_json,
            timeout=timeout if timeout is not None else self.timeout,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            data = resp.json()
        except Exception:
            # 非 JSON 响应：直接当文本
            return resp.text, 0
        text = self._extract_text(data)
        # 自定义协议无标准 token 统计字段，返回 0
        return text, 0

    async def _async_do_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        timeout: float | None = None,
    ) -> tuple[str, int]:
        body_str = self._render_body(messages)
        try:
            body_json = json.loads(body_str)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"body_template 不是合法 JSON: {e}")
        headers = {"content-type": "application/json", **self.extra_headers}
        if self.api_key:
            headers.setdefault("authorization", f"Bearer {self.api_key}")
        effective_timeout = timeout if timeout is not None else self.timeout
        async with self._httpx.AsyncClient(timeout=effective_timeout) as client:
            resp = await client.request(
                self.method,
                self.endpoint,
                headers=headers,
                json=body_json,
            )
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            data = resp.json()
        except Exception:
            return resp.text, 0
        text = self._extract_text(data)
        return text, 0


# ============================================================================
# 工厂 + 向后兼容别名
# ============================================================================


def create_llm_client(config: dict) -> BaseLLMClient:
    """根据 config["protocol"] 构造对应协议的 LLM 客户端。

    Args:
        config: 单个 provider 的配置
            protocol 字段可选，未指定时默认 openai_compatible

    Returns:
        BaseLLMClient 子类实例

    Raises:
        LLMError: 协议不支持
    """
    protocol = (config.get("protocol") or PROTOCOL_OPENAI).lower()
    if protocol in (PROTOCOL_OPENAI, "openai", "deepseek", "glm", "moonshot", "qwen"):
        return OpenAICompatibleClient(config)
    if protocol == PROTOCOL_ANTHROPIC:
        return AnthropicClient(config)
    if protocol == PROTOCOL_CUSTOM_HTTP:
        return CustomHTTPClient(config)
    raise LLMError(
        f"不支持的协议: {protocol}。可选: {', '.join(sorted(SUPPORTED_PROTOCOLS))}"
    )


# ─── 向后兼容：LLMClient 别名 ───
# 旧代码 `LLMClient(config)` 仍然可用，行为等价于 `create_llm_client(config)`。
# 旧 config 无 protocol 字段 → 默认 openai_compatible。
LLMClient = OpenAICompatibleClient


__all__ = [
    "LLMError",
    "BaseLLMClient",
    "OpenAICompatibleClient",
    "AnthropicClient",
    "CustomHTTPClient",
    "create_llm_client",
    "LLMClient",
    "PROTOCOL_OPENAI",
    "PROTOCOL_ANTHROPIC",
    "PROTOCOL_CUSTOM_HTTP",
    "SUPPORTED_PROTOCOLS",
    # 保留 OpenAI/AsyncOpenAI 模块级名字（测试 patch 用，向后兼容）
    "OpenAI",
    "AsyncOpenAI",
]
