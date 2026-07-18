#!/usr/bin/env python3
"""测试 KB 缓存服务（P3-C 优化）。

覆盖 web/services/kb_cache.py 的核心行为：
  - 单例复用（不重复初始化）
  - TTL 缓存命中
  - 缓存失效（invalidate_status / invalidate_search / invalidate_all）
  - 单例不可用时回退 subprocess
  - 配置变化时单例重建

设计：用 mock 隔离真实 vault，避免测试依赖外部环境。
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def reset_cache():
    """每个测试前后重置 kb_cache 模块状态，避免测试间污染。"""
    import web.services.kb_cache as kc

    # 测试前重置
    kc._kb_instance = None
    kc._kb_vault_path = None
    kc._status_cache = (0, None)
    kc._search_cache.clear()

    yield

    # 测试后重置
    kc._kb_instance = None
    kc._kb_vault_path = None
    kc._status_cache = (0, None)
    kc._search_cache.clear()


@pytest.fixture
def mock_config():
    """模拟启用知识库的配置。"""
    return {
        "knowledge_base": {
            "enabled": True,
            "vault_path": "/tmp/fake_vault",
        }
    }


# ═══════════════════════════════════════════════════════════════
# 单例复用
# ═══════════════════════════════════════════════════════════════


class TestSingletonReuse:
    """测试 get_kb_manager 的单例复用。"""

    def test_singleton_reused_across_calls(self, mock_config):
        """多次调用返回同一个实例。"""
        import web.services.kb_cache as kc

        with patch("web.services.kb_cache.load_config", return_value=mock_config):
            with patch("core.kb.kb_manager_mcp.KnowledgeBaseManager") as MockKB:
                mock_instance = MagicMock()
                MockKB.return_value = mock_instance

                m1 = kc.get_kb_manager()
                m2 = kc.get_kb_manager()
                m3 = kc.get_kb_manager()

                # 三次调用只构造一次
                assert MockKB.call_count == 1
                assert m1 is m2 is m3 is mock_instance

    def test_singleton_rebuilt_when_vault_changes(self, mock_config):
        """vault_path 变化时单例重建。"""
        import web.services.kb_cache as kc

        config1 = {"knowledge_base": {"enabled": True, "vault_path": "/tmp/v1"}}
        config2 = {"knowledge_base": {"enabled": True, "vault_path": "/tmp/v2"}        }

        configs = iter([config1, config1, config2, config2])

        with patch("web.services.kb_cache.load_config", side_effect=lambda: next(configs)):
            with patch("core.kb.kb_manager_mcp.KnowledgeBaseManager") as MockKB:
                kc.get_kb_manager()  # v1
                kc.get_kb_manager()  # v1 (复用)
                kc.get_kb_manager()  # v2 (重建)
                kc.get_kb_manager()  # v2 (复用)

                # vault 变化一次 → 构造两次
                assert MockKB.call_count == 2

    def test_returns_none_when_disabled(self):
        """知识库未启用 → 返回 None。"""
        import web.services.kb_cache as kc

        with patch("web.services.kb_cache.load_config",
                   return_value={"knowledge_base": {"enabled": False}}):
            assert kc.get_kb_manager() is None

    def test_returns_none_when_no_vault_path(self):
        """vault_path 未配置 → 返回 None。"""
        import web.services.kb_cache as kc

        with patch("web.services.kb_cache.load_config",
                   return_value={"knowledge_base": {"enabled": True}}):
            assert kc.get_kb_manager() is None

    def test_init_failure_returns_none(self, mock_config):
        """单例初始化失败（vault 不存在）→ 返回 None，不抛异常。"""
        import web.services.kb_cache as kc

        with patch("web.services.kb_cache.load_config", return_value=mock_config):
            with patch("core.kb.kb_manager_mcp.KnowledgeBaseManager",
                       side_effect=FileNotFoundError("vault 不存在")):
                assert kc.get_kb_manager() is None


# ═══════════════════════════════════════════════════════════════
# TTL 缓存
# ═══════════════════════════════════════════════════════════════


class TestStatusCache:
    """测试 get_status 的 TTL 缓存。"""

    def test_cache_hit_avoids_repeated_calls(self, mock_config):
        """缓存命中时不重复调用 mgr.status()。"""
        import web.services.kb_cache as kc

        mock_mgr = MagicMock()
        mock_mgr.status.return_value = {"total": 42}

        with patch("web.services.kb_cache.load_config", return_value=mock_config):
            with patch.object(kc, "get_kb_manager", return_value=mock_mgr):
                kc.get_status()  # 冷
                kc.get_status()  # 热
                kc.get_status()  # 热

                # 只调用一次 status()
                assert mock_mgr.status.call_count == 1

    def test_cache_expires_after_ttl(self, mock_config):
        """超过 TTL 后缓存过期，重新查询。"""
        import web.services.kb_cache as kc

        mock_mgr = MagicMock()
        mock_mgr.status.return_value = {"total": 42}

        with patch("web.services.kb_cache.load_config", return_value=mock_config):
            with patch.object(kc, "get_kb_manager", return_value=mock_mgr):
                # 模拟时间：首次查询
                with patch("web.services.kb_cache.time.time",
                           side_effect=[100, 100, 100 + kc.STATUS_TTL + 1, 100 + kc.STATUS_TTL + 1]):
                    kc.get_status()  # t=100 冷
                    kc.get_status()  # t=100 热
                    kc.get_status()  # t=161 过期，重查

                # 过期后重查 → 调用两次
                assert mock_mgr.status.call_count == 2


class TestSearchCache:
    """测试 search 的按 query 缓存。"""

    def test_different_queries_cached_separately(self, mock_config):
        """不同 query 各自缓存。"""
        import web.services.kb_cache as kc

        mock_mgr = MagicMock()
        mock_mgr.search.return_value = [{"title": "结果"}]

        with patch("web.services.kb_cache.load_config", return_value=mock_config):
            with patch.object(kc, "get_kb_manager", return_value=mock_mgr):
                kc.search("关键词A")
                kc.search("关键词B")
                kc.search("关键词A")  # 命中缓存
                kc.search("关键词B")  # 命中缓存

                # 两个不同 query → 两次调用
                assert mock_mgr.search.call_count == 2

    def test_same_query_cache_hit(self, mock_config):
        """相同 query 第二次命中缓存。"""
        import web.services.kb_cache as kc

        mock_mgr = MagicMock()
        mock_mgr.search.return_value = [{"title": "x"}]

        with patch("web.services.kb_cache.load_config", return_value=mock_config):
            with patch.object(kc, "get_kb_manager", return_value=mock_mgr):
                kc.search("同义词")
                kc.search("同义词")
                kc.search("同义词")

                assert mock_mgr.search.call_count == 1


# ═══════════════════════════════════════════════════════════════
# 缓存失效
# ═══════════════════════════════════════════════════════════════


class TestCacheInvalidation:
    """测试写入后的缓存失效（import/add 场景）。"""

    def test_invalidate_status_clears_cache(self, mock_config):
        """invalidate_status 后下次 get_status 重新查询。"""
        import web.services.kb_cache as kc

        mock_mgr = MagicMock()
        mock_mgr.status.return_value = {"total": 42}

        with patch("web.services.kb_cache.load_config", return_value=mock_config):
            with patch.object(kc, "get_kb_manager", return_value=mock_mgr):
                kc.get_status()
                kc.invalidate_status()
                kc.get_status()

                assert mock_mgr.status.call_count == 2  # 失效后重查

    def test_invalidate_search_clears_all_queries(self, mock_config):
        """invalidate_search 清除所有 query 的缓存。"""
        import web.services.kb_cache as kc

        mock_mgr = MagicMock()
        mock_mgr.search.return_value = []

        with patch("web.services.kb_cache.load_config", return_value=mock_config):
            with patch.object(kc, "get_kb_manager", return_value=mock_mgr):
                kc.search("A")
                kc.search("B")
                assert mock_mgr.search.call_count == 2

                kc.invalidate_search()
                kc.search("A")
                kc.search("B")

                assert mock_mgr.search.call_count == 4  # 全部重查

    def test_invalidate_all_clears_both(self, mock_config):
        """invalidate_all 同时清 status 和 search。"""
        import web.services.kb_cache as kc

        mock_mgr = MagicMock()
        mock_mgr.status.return_value = {"total": 1}
        mock_mgr.search.return_value = []

        with patch("web.services.kb_cache.load_config", return_value=mock_config):
            with patch.object(kc, "get_kb_manager", return_value=mock_mgr):
                kc.get_status()
                kc.search("x")
                kc.invalidate_all()
                kc.get_status()
                kc.search("x")

                assert mock_mgr.status.call_count == 2
                assert mock_mgr.search.call_count == 2


# ═══════════════════════════════════════════════════════════════
# 回退 subprocess
# ═══════════════════════════════════════════════════════════════


class TestSubprocessFallback:
    """单例不可用时回退 subprocess（向后兼容）。"""

    def test_status_fallback_when_singleton_none(self):
        """get_kb_manager 返回 None → get_status 回退 subprocess。"""
        import web.services.kb_cache as kc

        with patch.object(kc, "get_kb_manager", return_value=None):
            with patch.object(kc, "_status_via_subprocess",
                               return_value={"total": 99}) as mock_sub:
                result = kc.get_status()
                assert result == {"total": 99}
                mock_sub.assert_called_once()

    def test_search_fallback_when_singleton_none(self):
        """get_kb_manager 返回 None → search 回退 subprocess。"""
        import web.services.kb_cache as kc

        with patch.object(kc, "get_kb_manager", return_value=None):
            with patch.object(kc, "_search_via_subprocess",
                               return_value=[{"title": "fallback"}]) as mock_sub:
                result = kc.search("test")
                assert len(result) == 1
                mock_sub.assert_called_once_with("test", 20)
