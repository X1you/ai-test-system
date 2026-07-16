#!/usr/bin/env python3
"""
LLM 抽象层 — 统一调用 OpenAI 兼容协议

支持 DeepSeek / GLM / OpenAI / Moonshot / 通义千问 等所有兼容 OpenAI API 的模型。

核心方法：
  - chat()            单轮对话
  - chat_with_retry() 带重试的对话
  - evaluate()        质量自检（返回评分 + 问题清单）
"""

import json
import sys
import time

from openai import AsyncOpenAI, OpenAI

from core.llm_cache import LLMCache


class LLMError(Exception):
    """LLM 调用异常"""


class LLMClient:
    """统一 LLM 调用客户端"""

    def __init__(self, config: dict):
        """
        Args:
            config: llm 配置段（config["llm"]）
        """
        self.provider = config.get("provider", "unknown")
        self.model = config.get("model", "")
        self.temperature = config.get("temperature", 0.3)
        self.max_tokens = config.get("max_tokens", 8192)
        self.timeout = config.get("timeout", 120)
        self.retry_count = config.get("retry", 2)

        api_key = config.get("api_key", "")
        base_url = config.get("base_url", "")

        if not self.model:
            raise LLMError(
                "LLM model 未配置。请在 config.yaml 的 llm 段中设置 model 字段。"
            )
        if not api_key:
            raise LLMError(
                "LLM API Key 未配置。请在 .env 中设置 LLM_API_KEY，"
                "或在 config.yaml 中填写 api_key。"
            )

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=self.timeout,
        )

        self._async_client: AsyncOpenAI | None = None
        self._call_count = 0
        self._total_tokens = 0

        # 缓存层（可选）
        self._cache: LLMCache | None = None
        self._use_cache = config.get("cache_enabled", False)

    def enable_cache(self, cache: LLMCache):
        """挂载 LLM 调用缓存"""
        self._cache = cache
        self._use_cache = True

    def chat(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float | None = None,
    ) -> str:
        """
        单轮对话

        Args:
            prompt: 用户提示词
            system: 系统提示词（角色定义等）
            temperature: 覆盖默认温度

        Returns:
            LLM 生成的文本
        """
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        temp = temperature if temperature is not None else self.temperature

        # 检查缓存
        if self._cache and self._use_cache and temp == 0:
            cached = self._cache.get(self.model, system or "", prompt, temp)
            if cached is not None:
                self._call_count += 1
                return cached

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore[arg-type]
                temperature=temp,
                max_tokens=self.max_tokens,
            )
            self._call_count += 1
            if response.usage:
                self._total_tokens += response.usage.total_tokens

            result = response.choices[0].message.content or ""
            if self._cache and self._use_cache and temp == 0:
                self._cache.set(self.model, system or "", prompt, result, temp)
            return result

        except Exception as e:
            raise LLMError(f"[{self.provider}] LLM 调用失败: {e}") from e

    async def async_chat(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float | None = None,
    ) -> str:
        """异步单轮对话 — 使用 AsyncOpenAI 原生异步"""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        temp = temperature if temperature is not None else self.temperature

        # 检查缓存
        if self._cache and self._use_cache and temp == 0:
            cached = self._cache.get(self.model, system or "", prompt, temp)
            if cached is not None:
                self._call_count += 1
                return cached

        if self._async_client is None:
            self._async_client = AsyncOpenAI(
                api_key=self.client.api_key,
                base_url=self.client.base_url,
                timeout=self.timeout,
            )

        try:
            response = await self._async_client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore[arg-type]
                temperature=temp,
                max_tokens=self.max_tokens,
            )
            self._call_count += 1
            if response.usage:
                self._total_tokens += response.usage.total_tokens

            result = response.choices[0].message.content or ""
            if self._cache and self._use_cache and temp == 0:
                self._cache.set(self.model, system or "", prompt, result, temp)
            return result

        except Exception as e:
            raise LLMError(f"[{self.provider}] LLM 异步调用失败: {e}") from e

    def chat_with_retry(
        self,
        prompt: str,
        system: str | None = None,
        retries: int | None = None,
        delay: float = 2.0,
    ) -> str:
        """
        带重试的对话

        Args:
            prompt: 用户提示词
            system: 系统提示词
            retries: 重试次数（默认用配置中的值）
            delay: 重试间隔（秒）

        Returns:
            LLM 生成的文本
        """
        max_attempts = (retries if retries is not None else self.retry_count) + 1
        last_error = None

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
        """
        质量自检 — LLM 回头评估自己的输出

        Args:
            content: 待评估的内容
            criteria: 评估标准（如"模块覆盖完整吗？待确认事项有没有遗漏？"）

        Returns:
            {
                "score": int,           # 0-100
                "passed": bool,         # score >= 70 为通过
                "issues": List[str],    # 发现的问题
                "suggestions": List[str]  # 改进建议
            }
        """
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

    @staticmethod
    def _parse_json_response(raw: str) -> dict:
        """容错解析 LLM 的 JSON 输出"""
        text = raw.strip()

        # 去掉可能的 markdown 代码块标记
        if text.startswith("```"):
            lines = text.split("\n")
            # 去掉首尾 ``` 行
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试提取第一个 { ... } 块
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
            "call_count": self._call_count,
            "total_tokens": self._total_tokens,
        }

    def __repr__(self) -> str:
        return f"LLMClient(provider={self.provider}, model={self.model})"
