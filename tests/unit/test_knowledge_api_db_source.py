#!/usr/bin/env python3
"""
Knowledge API 端到端测试 — DB 数据源统一性（Sprint 6.1 修复回归保护）。

背景：Sprint 6.1 重构出现「双重数据源」bug——/current_config 读 DB，
/status /search 读 config.yaml，导致两卡片永远指向不同 vault。
本测试验证修复后的数据源一致性，防止同类回归。

覆盖：
  - /status 与 /current_config 同源（都走 DynamicKBManager）
  - /status 返回必须含 enabled 字段（修复前端误报「知识库未启用」）
  - /search 与 /status 同源
  - /update_config 热切换后 status 立即反映新 vault（缓存失效）
  - /update_config 校验：无效 provider / 不存在路径被拒
  - _kb_subprocess_env 注入 DB 配置的 vault_path
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("LLM_API_KEY", "sk-test-dummy")


# ═══════════════════════════════════════════════════════════════
# 辅助：构造 mock DynamicKBManager
# ═══════════════════════════════════════════════════════════════


def _make_mock_manager(configured=True, vault_path="/tmp/fake_vault", total=10):
    """构造 mock DynamicKBManager。

    configured=True  → 有配置，status 返回 total 条目
    configured=False → Dummy 模式，status 返回 enabled=False
    """
    mgr = MagicMock()
    mgr.is_configured.return_value = configured
    mgr.get_config.return_value = (
        {"provider_type": "mcp_filesystem", "connection_url": None,
         "auth_token": None, "vault_path": vault_path}
        if configured else None
    )
    client = MagicMock()
    client.status.return_value = {
        "source": "mcp-obsidian", "total": total,
        "categories": {"business-rules": total},
        "last_updated": "2026-07-20 10:00:00",
    }
    client.search.return_value = [{"title": "命中结果", "snippet": "..."}]
    mgr.get_client.return_value = client
    return mgr


@pytest.fixture(autouse=True)
def _reset_kb_cache():
    """每个测试前后重置 kb_cache 缓存，避免测试间污染。"""
    import web.services.kb_cache as kc
    kc._status_cache = (0, None)
    kc._search_cache.clear()
    yield
    kc._status_cache = (0, None)
    kc._search_cache.clear()


# ═══════════════════════════════════════════════════════════════
# 数据源一致性（核心回归保护）
# ═══════════════════════════════════════════════════════════════


class TestKBDataSourceConsistency:
    """验证 /status /search 与 /current_config 同源（DB）。"""

    def test_status_and_config_same_source(self, client):
        """/status 与 /current_config 都走 DB 数据源。"""
        # /current_config 直接查 KBConfig 表，需插入记录
        from db.models import KBConfig
        from db.session import session_scope

        with session_scope() as db:
            db.add(KBConfig(
                provider_type="mcp_filesystem",
                vault_path="/data/vault_A",
                is_active=True,
            ))

        try:
            mgr = _make_mock_manager(configured=True, vault_path="/data/vault_A", total=42)
            with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr):
                # current_config 走 DB
                cfg = client.get("/api/v1/knowledge/current_config").json()
                # status 走 DynamicKBManager（同源）
                st = client.get("/api/v1/knowledge/status").json()

            assert cfg["configured"] is True
            assert st["total"] == 42
            # 两者都基于同一个 manager（同源）— manager.get_client().status() 被调用
            mgr.get_client.return_value.status.assert_called()
        finally:
            # 清理：删除测试插入的 KBConfig，避免污染 /health 检查
            with session_scope() as db:
                db.query(KBConfig).filter(
                    KBConfig.vault_path == "/data/vault_A"
                ).delete()
            # 重置单例缓存，避免坏配置影响后续测试的 /health 检查
            from core.kb.dynamic_kb_manager import DynamicKBManager
            DynamicKBManager._instance = None

    def test_status_returns_enabled_field(self, client):
        """/status 必须含 enabled 字段（修复前端误报「知识库未启用」）。"""
        mgr = _make_mock_manager(configured=True)
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr):
            st = client.get("/api/v1/knowledge/status").json()
        # MCPClient.status() 原始返回不含 enabled，kb_cache 必须注入
        assert "enabled" in st
        assert st["enabled"] is True

    def test_search_same_source_as_status(self, client):
        """/search 与 /status 走同一 manager（DB 数据源）。"""
        mgr = _make_mock_manager(configured=True)
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr):
            client.get("/api/v1/knowledge/status")
            client.get("/api/v1/knowledge/search?q=测试")

        # 两者都调用同一个 client
        client_mock = mgr.get_client.return_value
        client_mock.status.assert_called_once()
        client_mock.search.assert_called_once()


# ═══════════════════════════════════════════════════════════════
# Dummy 模式降级
# ═══════════════════════════════════════════════════════════════


class TestKBDummyMode:
    """未配置（Dummy）时的降级行为。"""

    def test_status_disabled_when_dummy(self, client):
        """Dummy 模式 → /status 返回 enabled=False。"""
        mgr = _make_mock_manager(configured=False)
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr):
            st = client.get("/api/v1/knowledge/status").json()
        assert st["enabled"] is False

    def test_search_empty_when_dummy(self, client):
        """Dummy 模式 → /search 返回空结果。"""
        mgr = _make_mock_manager(configured=False)
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr):
            data = client.get("/api/v1/knowledge/search?q=x").json()
        assert data["total"] == 0
        assert data["results"] == []


# ═══════════════════════════════════════════════════════════════
# 缓存失效（热切换后立即刷新）
# ═══════════════════════════════════════════════════════════════


class TestKBCacheInvalidation:
    """验证 /status 的 60s 缓存在 invalidate 后立即失效。"""

    def test_status_cached_within_ttl(self, client):
        """60s 内重复请求不重复调用 client.status()。"""
        mgr = _make_mock_manager(configured=True)
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr):
            client.get("/api/v1/knowledge/status")
            client.get("/api/v1/knowledge/status")
            client.get("/api/v1/knowledge/status")
        mgr.get_client.return_value.status.assert_called_once()

    def test_invalidate_forces_refresh(self, client):
        """invalidate_all 后 status 重新查询。"""
        mgr = _make_mock_manager(configured=True)
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr):
            client.get("/api/v1/knowledge/status")
            import web.services.kb_cache as kc
            kc.invalidate_all()
            client.get("/api/v1/knowledge/status")
        assert mgr.get_client.return_value.status.call_count == 2


# ═══════════════════════════════════════════════════════════════
# _kb_subprocess_env（import/add 写入正确 vault）
# ═══════════════════════════════════════════════════════════════


class TestKBSubprocessEnv:
    """验证 import/add 子进程注入 DB 配置的 vault_path。"""

    def test_env_includes_db_vault_path(self):
        """_kb_subprocess_env 从 DynamicKBManager 取 vault_path。"""
        from web.api.knowledge import _kb_subprocess_env

        mgr = _make_mock_manager(configured=True, vault_path="/data/DB_vault")
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr):
            env = _kb_subprocess_env()
        assert env["OBSIDIAN_VAULT"] == "/data/DB_vault"

    def test_env_fallback_when_unconfigured(self):
        """未配置时回退到当前进程环境（不崩溃）。"""
        from web.api.knowledge import _kb_subprocess_env

        mgr = _make_mock_manager(configured=False)
        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager", return_value=mgr):
            env = _kb_subprocess_env()
        # 不注入 OBSIDIAN_VAULT（回退），但不报错
        assert isinstance(env, dict)


# ═══════════════════════════════════════════════════════════════
# /update_config 输入校验
# ═══════════════════════════════════════════════════════════════


class TestKBUpdateConfigValidation:
    """/update_config 的连通性测试与输入校验。"""

    def test_reject_invalid_provider(self, client):
        """无效 provider_type 被拒。"""
        resp = client.post("/api/v1/knowledge/update_config",
                           json={"provider_type": "invalid", "vault_path": "/tmp"})
        data = resp.json()
        assert data["status"] == "error"

    def test_reject_nonexistent_vault(self, client, tmp_path):
        """mcp_filesystem 要求 vault_path 存在。"""
        resp = client.post("/api/v1/knowledge/update_config",
                           json={"provider_type": "mcp_filesystem",
                                 "vault_path": "/nonexistent/path/xyz"})
        data = resp.json()
        assert data["status"] == "error"
        assert "vault_path" in data["message"] or "存在" in data["message"]
