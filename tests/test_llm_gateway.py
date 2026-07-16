#!/usr/bin/env python3
"""
LLM Gateway 测试 — 多 Provider 路由 + 故障转移

测试范围：
  - 主 Provider 调用
  - 故障转移到备选 Provider
  - 调用统计
  - 空备选列表
  - 所有 Provider 都失败
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestLLMGatewayInit:
    """LLM Gateway 初始化"""

    def test_primary_only(self):
        """只有主 Provider 无备选"""
        from core.llm_gateway import LLMGateway

        config = {
            "llm": {
                "provider": "deepseek",
                "api_key": "sk-test",
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-v4",
            }
        }
        gateway = LLMGateway(config)
        assert gateway.primary.provider == "deepseek"
        assert len(gateway.fallback_chain) == 0

    def test_with_fallbacks(self):
        """带备选 Provider 列表"""
        from core.llm_gateway import LLMGateway

        config = {
            "llm": {
                "provider": "deepseek",
                "api_key": "sk-test",
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-v4",
                "fallback": [
                    {
                        "provider": "openai",
                        "api_key": "sk-openai",
                        "base_url": "https://api.openai.com",
                        "model": "gpt-4",
                    },
                ],
            }
        }
        gateway = LLMGateway(config)
        assert len(gateway.fallback_chain) == 1
        assert gateway.fallback_chain[0].provider == "openai"

    def test_fallback_with_invalid_config_skipped(self):
        """备选 Provider 配置错误时跳过"""
        from core.llm_gateway import LLMGateway

        config = {
            "llm": {
                "provider": "deepseek",
                "api_key": "sk-test",
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-v4",
                "fallback": [
                    {
                        "provider": "bad",
                        "api_key": "",  # 空 API key
                        "base_url": "",
                        "model": "",
                    },
                ],
            }
        }
        gateway = LLMGateway(config)
        assert len(gateway.fallback_chain) == 0


class TestLLMGatewayChat:
    """LLM Gateway chat 调用"""

    @pytest.mark.asyncio
    async def test_chat_primary_success(self):
        """主 Provider 调用成功"""
        from core.llm_gateway import LLMGateway

        config = {
            "llm": {
                "provider": "deepseek",
                "api_key": "sk-test",
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-v4",
            }
        }
        gateway = LLMGateway(config)

        with patch.object(gateway, '_call_provider', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = "Hello, World!"
            result = await gateway.chat("Hi")
            assert result == "Hello, World!"
            mock_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_failover_to_fallback(self):
        """主 Provider 失败 → 转移到备选"""
        from core.llm_gateway import LLMGateway

        config = {
            "llm": {
                "provider": "primary",
                "api_key": "sk-test",
                "base_url": "https://api.primary.com",
                "model": "primary-model",
                "fallback": [
                    {
                        "provider": "backup",
                        "api_key": "sk-backup",
                        "base_url": "https://api.backup.com",
                        "model": "backup-model",
                    },
                ],
            }
        }
        gateway = LLMGateway(config)

        with patch.object(gateway, '_call_provider', new_callable=AsyncMock) as mock_call:
            # 第一次调用失败，第二次成功
            mock_call.side_effect = [Exception("Primary failed"), "Backup response"]
            result = await gateway.chat("Hi")
            assert result == "Backup response"
            assert mock_call.call_count == 2
            assert gateway.stats["failovers"] == 1

    @pytest.mark.asyncio
    async def test_chat_all_providers_fail(self):
        """所有 Provider 都失败"""
        from core.llm_gateway import LLMGateway

        config = {
            "llm": {
                "provider": "primary",
                "api_key": "sk-test",
                "base_url": "https://api.primary.com",
                "model": "p",
                "fallback": [
                    {
                        "provider": "backup",
                        "api_key": "sk-backup",
                        "base_url": "https://api.backup.com",
                        "model": "b",
                    },
                ],
            }
        }
        gateway = LLMGateway(config)

        with patch.object(gateway, '_call_provider', new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = Exception("All failed")
            with pytest.raises(Exception):
                await gateway.chat("Hi")
            assert mock_call.call_count == 2

    @pytest.mark.asyncio
    async def test_chat_stats_updated(self):
        """调用统计更新 — _call_provider 被 mock，stats 不会更新，但 primary stats 会更新"""
        from core.llm_gateway import LLMGateway

        config = {
            "llm": {
                "provider": "deepseek",
                "api_key": "sk-test",
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-v4",
            }
        }
        gateway = LLMGateway(config)

        # 直接调用 _call_provider 测试统计更新
        with patch.object(gateway.primary, 'async_chat', new_callable=AsyncMock, return_value="response"):
            result = await gateway._call_provider(gateway.primary, "prompt", None)
            assert result == "response"
            stats = gateway.stats
            assert stats["total_calls"] == 1
            assert stats["provider_calls"].get("deepseek", 0) == 1


class TestLLMGatewayStats:
    """LLM Gateway 统计"""

    def test_initial_stats(self):
        """初始统计全为零"""
        from core.llm_gateway import LLMGateway

        config = {
            "llm": {
                "provider": "deepseek",
                "api_key": "sk-test",
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-v4",
            }
        }
        gateway = LLMGateway(config)
        stats = gateway.stats
        assert stats["total_calls"] == 0
        assert stats["total_tokens"] == 0
        assert stats["failovers"] == 0

    def test_repr(self):
        """字符串表示"""
        from core.llm_gateway import LLMGateway

        config = {
            "llm": {
                "provider": "deepseek",
                "api_key": "sk-test",
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-v4",
            }
        }
        gateway = LLMGateway(config)
        repr_str = repr(gateway)
        assert "deepseek" in repr_str
        assert "LLMGateway" in repr_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
