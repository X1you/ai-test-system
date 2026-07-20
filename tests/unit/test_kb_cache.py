#!/usr/bin/env python3
"""测试 KB 缓存服务（Sprint 6.1：DB 数据源）。

覆盖 web/services/kb_cache.py 的核心行为：
  - DynamicKBManager 数据源（替代旧 config.yaml 路径）
  - TTL 缓存命中（status 60s / search 30s）
  - 缓存失效（invalidate_status / invalidate_search / invalidate_all）
  - Dummy 模式降级（未配置时返回 enabled=False）
  - enabled 字段注入（修复前端误报「知识库未启用」）
  - LRU 淘汰（search 缓存上限）

设计：用 mock 隔离 DynamicKBManager，避免测试依赖外部 DB / vault。
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def reset_cache():
    """每个测试前后重置 kb_cache 模块状态，避免测试间污染。"""
    import web.services.kb_cache as kc

    kc._status_cache = (0, None)
    kc._search_cache.clear()

    yield

    kc._status_cache = (0, None)
    kc._search_cache.clear()


def _make_mock_manager(configured=True, client=None):
    """构造 mock DynamicKBManager。

    Args:
        configured: is_configured() 返回值
        client: get_client() 返回的 mock client（None 时自动创建）
    """
    mgr = MagicMock()
    mgr.is_configured.return_value = configured
    if client is None:
        client = MagicMock()
        client.status.return_value = {"total": 0, "categories": {}}
        client.search.return_value = []
    mgr.get_client.return_value = client
    mgr.get_config.return_value = (
        {"provider_type": "mcp_filesystem", "vault_path": "/tmp/fake_vault"}
        if configured else None
    )
    return mgr


# ═══════════════════════════════════════════════════════════════
# 数据源：DynamicKBManager
# ═══════════════════════════════════════════════════════════════


class TestDataSource:
    """测试 kb_cache 从 DynamicKBManager 取数据（DB 数据源）。"""

    def test_get_status_uses_dynamic_manager(self):
        """get_status 走 DynamicKBManager.get_client().status()。"""
        import web.services.kb_cache as kc

        client = MagicMock()
        client.status.return_value = {"total": 42, "categories": {"a": 1}}

        mgr = _make_mock_manager(configured=True, client=client)
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr):
            result = kc.get_status()

        client.status.assert_called_once()
        assert result["total"] == 42
        # ★ enabled 字段必须被注入（修复前端误报「知识库未启用」）
        assert result["enabled"] is True

    def test_get_kb_manager_returns_client(self):
        """get_kb_manager（向后兼容）返回底层 client。"""
        import web.services.kb_cache as kc

        mgr = _make_mock_manager(configured=True)
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr):
            result = kc.get_kb_manager()

        assert result is mgr.get_client.return_value

    def test_get_kb_manager_none_when_dummy(self):
        """未配置（Dummy）时 get_kb_manager 返回 None。"""
        import web.services.kb_cache as kc

        mgr = _make_mock_manager(configured=False)
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr):
            assert kc.get_kb_manager() is None


# ═══════════════════════════════════════════════════════════════
# Dummy 模式降级
# ═══════════════════════════════════════════════════════════════


class TestDummyMode:
    """未配置（Dummy）时的降级行为。"""

    def test_status_returns_disabled_when_dummy(self):
        """Dummy 模式 → status 返回 enabled=False。"""
        import web.services.kb_cache as kc

        mgr = _make_mock_manager(configured=False)
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr):
            result = kc.get_status()

        assert result["enabled"] is False
        assert result["total"] == 0
        assert "message" in result

    def test_search_returns_empty_when_dummy(self):
        """Dummy 模式 → search 返回空列表。"""
        import web.services.kb_cache as kc

        mgr = _make_mock_manager(configured=False)
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr):
            assert kc.search("anything") == []


# ═══════════════════════════════════════════════════════════════
# enabled 字段注入
# ═══════════════════════════════════════════════════════════════


class TestEnabledField:
    """MCPClient.status() 不含 enabled 字段，kb_cache 必须注入。"""

    def test_status_injects_enabled_true(self):
        """client.status() 无 enabled → kb_cache 注入 enabled=True。"""
        import web.services.kb_cache as kc

        client = MagicMock()
        client.status.return_value = {"total": 5, "categories": {"x": 5}}  # 无 enabled

        mgr = _make_mock_manager(configured=True, client=client)
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr):
            result = kc.get_status()

        assert "enabled" in result
        assert result["enabled"] is True


# ═══════════════════════════════════════════════════════════════
# TTL 缓存
# ═══════════════════════════════════════════════════════════════


class TestStatusCache:
    """测试 get_status 的 TTL 缓存。"""

    def test_cache_hit_avoids_repeated_calls(self):
        """缓存命中时不重复调用 client.status()。"""
        import web.services.kb_cache as kc

        client = MagicMock()
        client.status.return_value = {"total": 42}

        mgr = _make_mock_manager(configured=True, client=client)
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr):
            kc.get_status()  # 冷
            kc.get_status()  # 热
            kc.get_status()  # 热

            assert client.status.call_count == 1

    def test_cache_expires_after_ttl(self):
        """超过 TTL 后缓存过期，重新查询。"""
        import web.services.kb_cache as kc

        client = MagicMock()
        client.status.return_value = {"total": 42}

        mgr = _make_mock_manager(configured=True, client=client)
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr):
            with patch("web.services.kb_cache.time.time",
                       side_effect=[100, 100, 100 + kc.STATUS_TTL + 1, 100 + kc.STATUS_TTL + 1]):
                kc.get_status()  # t=100 冷
                kc.get_status()  # t=100 热
                kc.get_status()  # t=161 过期，重查

            assert client.status.call_count == 2


class TestSearchCache:
    """测试 search 的按 query 缓存。"""

    def test_different_queries_cached_separately(self):
        """不同 query 各自缓存。"""
        import web.services.kb_cache as kc

        client = MagicMock()
        client.search.return_value = [{"title": "结果"}]

        mgr = _make_mock_manager(configured=True, client=client)
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr):
            kc.search("关键词A")
            kc.search("关键词B")
            kc.search("关键词A")  # 命中缓存
            kc.search("关键词B")  # 命中缓存

            assert client.search.call_count == 2

    def test_same_query_cache_hit(self):
        """相同 query 第二次命中缓存。"""
        import web.services.kb_cache as kc

        client = MagicMock()
        client.search.return_value = [{"title": "x"}]

        mgr = _make_mock_manager(configured=True, client=client)
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr):
            kc.search("同义词")
            kc.search("同义词")
            kc.search("同义词")

            assert client.search.call_count == 1


# ═══════════════════════════════════════════════════════════════
# 缓存失效
# ═══════════════════════════════════════════════════════════════


class TestCacheInvalidation:
    """测试写入/热切换后的缓存失效。"""

    def test_invalidate_status_clears_cache(self):
        """invalidate_status 后下次 get_status 重新查询。"""
        import web.services.kb_cache as kc

        client = MagicMock()
        client.status.return_value = {"total": 42}

        mgr = _make_mock_manager(configured=True, client=client)
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr):
            kc.get_status()
            kc.invalidate_status()
            kc.get_status()

            assert client.status.call_count == 2

    def test_invalidate_search_clears_all_queries(self):
        """invalidate_search 清除所有 query 的缓存。"""
        import web.services.kb_cache as kc

        client = MagicMock()
        client.search.return_value = []

        mgr = _make_mock_manager(configured=True, client=client)
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr):
            kc.search("A")
            kc.search("B")
            assert client.search.call_count == 2

            kc.invalidate_search()
            kc.search("A")
            kc.search("B")

            assert client.search.call_count == 4

    def test_invalidate_all_clears_both(self):
        """invalidate_all 同时清 status 和 search。"""
        import web.services.kb_cache as kc

        client = MagicMock()
        client.status.return_value = {"total": 1}
        client.search.return_value = []

        mgr = _make_mock_manager(configured=True, client=client)
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr):
            kc.get_status()
            kc.search("x")
            kc.invalidate_all()
            kc.get_status()
            kc.search("x")

            assert client.status.call_count == 2
            assert client.search.call_count == 2


# ═══════════════════════════════════════════════════════════════
# LRU 淘汰（防止内存无限增长）
# ═══════════════════════════════════════════════════════════════


class TestSearchCacheLRU:
    """search 缓存 LRU 上限测试。"""

    @pytest.fixture(autouse=True)
    def _reset(self):
        import web.services.kb_cache as kc
        kc.invalidate_all()
        kc._search_cache.clear()
        yield
        kc.invalidate_all()
        kc._search_cache.clear()

    def test_cache_bounded_by_max(self):
        """写入超过 SEARCH_CACHE_MAX 条目后，总数不超过上限。"""
        import web.services.kb_cache as kc

        client = MagicMock()
        client.search.side_effect = lambda q, limit: [{"q": q}]

        mgr = _make_mock_manager(configured=True, client=client)
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr):
            for i in range(kc.SEARCH_CACHE_MAX + 10):
                kc.search(f"query-{i}")

            assert len(kc._search_cache) <= kc.SEARCH_CACHE_MAX

    def test_lru_evicts_oldest(self):
        """LRU 淘汰最旧条目。"""
        import web.services.kb_cache as kc

        client = MagicMock()
        client.search.side_effect = lambda q, limit: [{"q": q}]

        mgr = _make_mock_manager(configured=True, client=client)
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr):
            kc.search("first-query")
            for i in range(kc.SEARCH_CACHE_MAX):
                kc.search(f"q-{i}")

            assert "first-query:20" not in kc._search_cache

    def test_lru_keeps_recently_accessed(self):
        """命中过的条目被 move_to_end，不会被优先淘汰。"""
        import web.services.kb_cache as kc

        client = MagicMock()
        client.search.side_effect = lambda q, limit: [{"q": q}]

        mgr = _make_mock_manager(configured=True, client=client)
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr):
            kc.search("hot-query")
            kc.search("hot-query")  # 命中
            for i in range(kc.SEARCH_CACHE_MAX - 1):
                kc.search(f"q-{i}")

            assert "hot-query:20" in kc._search_cache
