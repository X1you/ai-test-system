#!/usr/bin/env python3
"""测试 core/kb/dynamic_kb_manager.py — DynamicKBManager + DummyKBClient。

覆盖目标：
  - DummyKBClient: status / search / list_files / read_file / create_file
  - DynamicKBManager.__init__ → _load_from_db（DB 异常降级 / 无记录 / 有记录）
  - _build_client（obsidian_api / mcp_filesystem / 未知 provider / 构建异常）
  - _build_obsidian_client / _build_mcp_client
  - get_instance（单例）/ get_client / get_config / reload / is_configured
  - get_dynamic_kb_manager 便捷入口

设计：mock db.session.session_scope 和 db.models.KBConfig，
     避免真实 DB 交互；mock MCPClient 避免真实文件系统。
"""

import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch, ANY

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ═══════════════════════════════════════════════════════════════
# DummyKBClient
# ═══════════════════════════════════════════════════════════════


class TestDummyKBClient:
    """测试 DummyKBClient 冷启动占位客户端。"""

    def test_status_returns_disabled(self):
        # 测试 status 返回 dummy 标记
        from core.kb.dynamic_kb_manager import DummyKBClient

        client = DummyKBClient()
        result = client.status()
        assert result["source"] == "dummy"
        assert result["total"] == 0

    def test_search_returns_empty(self):
        # 测试 search 返回空列表
        from core.kb.dynamic_kb_manager import DummyKBClient

        assert DummyKBClient().search("anything") == []

    def test_list_files_returns_empty(self):
        # 测试 list_files 返回空列表
        from core.kb.dynamic_kb_manager import DummyKBClient

        assert DummyKBClient().list_files("cat") == []

    def test_read_file_returns_none(self):
        # 测试 read_file 返回 None
        from core.kb.dynamic_kb_manager import DummyKBClient

        assert DummyKBClient().read_file("path") is None

    def test_create_file_returns_false(self):
        # 测试 create_file 返回 False
        from core.kb.dynamic_kb_manager import DummyKBClient

        assert DummyKBClient().create_file(MagicMock()) is False


# ═══════════════════════════════════════════════════════════════
# DynamicKBManager — _load_from_db / _build_client
# ═══════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def reset_singleton():
    """每个测试前后重置 DynamicKBManager 单例，避免测试间污染。"""
    from core.kb import dynamic_kb_manager as mod

    mod.DynamicKBManager._instance = None
    yield
    mod.DynamicKBManager._instance = None


def _mock_kb_config(provider="mcp_filesystem", vault="/tmp/v", url="", token=""):
    """构造 mock KBConfig ORM 对象。"""
    cfg = MagicMock()
    cfg.provider_type = provider
    cfg.connection_url = url
    cfg.auth_token = token
    cfg.vault_path = vault
    cfg.updated_at = MagicMock()
    return cfg


@pytest.fixture
def mock_db_session():
    """mock db.session.session_scope，返回可控的 session。"""
    session = MagicMock()
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=session)
    ctx.__exit__ = MagicMock(return_value=False)

    with patch("db.session.session_scope", return_value=ctx):
        yield session


class TestLoadFromDB:
    """测试 DynamicKBManager._load_from_db 及 __init__。"""

    def test_init_db_exception_falls_back_to_dummy(self):
        # 测试 DB 异常时降级 DummyKBClient
        from core.kb.dynamic_kb_manager import DynamicKBManager, DummyKBClient

        with patch("db.session.session_scope", side_effect=Exception("no DB")):
            mgr = DynamicKBManager()
        assert isinstance(mgr.get_client(), DummyKBClient)
        assert mgr.get_config() is None

    def test_init_no_active_config_falls_back_to_dummy(self, mock_db_session):
        # 测试 DB 中无 active 记录时降级 DummyKBClient
        from core.kb.dynamic_kb_manager import DynamicKBManager, DummyKBClient

        mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        mgr = DynamicKBManager()
        assert isinstance(mgr.get_client(), DummyKBClient)
        assert mgr.get_config() is None

    def test_init_with_mcp_filesystem_config(self, mock_db_session):
        # 测试从 DB 加载 mcp_filesystem 配置并构建 MCPClient
        from core.kb.dynamic_kb_manager import DynamicKBManager

        mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = _mock_kb_config(
            provider="mcp_filesystem", vault="/tmp/test_vault"
        )
        mock_client = MagicMock()
        with patch("core.kb.mcp_client.MCPClient", return_value=mock_client):
            mgr = DynamicKBManager()
        assert mgr.get_client() is mock_client
        assert mgr.get_config()["provider_type"] == "mcp_filesystem"

    def test_init_with_obsidian_api_config(self, mock_db_session):
        # 测试从 DB 加载 obsidian_api 配置并构建 MCPClient（use_obsidian_api=True）
        from core.kb.dynamic_kb_manager import DynamicKBManager

        mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = _mock_kb_config(
            provider="obsidian_api", vault="/tmp/v", url="http://localhost:1", token="key"
        )
        mock_client = MagicMock()
        with patch("core.kb.mcp_client.MCPClient", return_value=mock_client) as mc:
            mgr = DynamicKBManager()
        # 验证 use_obsidian_api=True
        call_kwargs = mc.call_args[1]
        assert call_kwargs["use_obsidian_api"] is True
        assert mgr.get_client() is mock_client

    def test_init_unknown_provider_falls_back_to_dummy(self, mock_db_session):
        # 测试未知 provider_type 降级 DummyKBClient
        from core.kb.dynamic_kb_manager import DynamicKBManager, DummyKBClient

        mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = _mock_kb_config(
            provider="unknown_provider", vault="/tmp/v"
        )
        mgr = DynamicKBManager()
        assert isinstance(mgr.get_client(), DummyKBClient)

    def test_init_build_client_exception_falls_back_to_dummy(self, mock_db_session):
        # 测试 client 构建抛异常时降级 DummyKBClient
        from core.kb.dynamic_kb_manager import DynamicKBManager, DummyKBClient

        mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = _mock_kb_config(
            provider="mcp_filesystem", vault=""
        )
        # vault_path 为空 → _build_mcp_client raise ValueError
        mgr = DynamicKBManager()
        assert isinstance(mgr.get_client(), DummyKBClient)
        assert mgr.get_config() is None


# ═══════════════════════════════════════════════════════════════
# DynamicKBManager — _build_mcp_client / _build_obsidian_client
# ═══════════════════════════════════════════════════════════════


class TestBuildHelpers:
    """测试 _build_mcp_client 和 _build_obsidian_client 静态方法。"""

    def test_build_mcp_client_success(self):
        # 测试 _build_mcp_client 成功构建
        from core.kb.dynamic_kb_manager import DynamicKBManager

        config = {"vault_path": "/tmp/x"}
        mock_client = MagicMock()
        with patch("core.kb.mcp_client.MCPClient", return_value=mock_client) as mc:
            result = DynamicKBManager._build_mcp_client(config)
        assert result is mock_client
        call_kwargs = mc.call_args[1]
        assert call_kwargs["use_obsidian_api"] is False

    def test_build_mcp_client_no_vault_raises(self):
        # 测试 _build_mcp_client 无 vault_path 时抛 ValueError
        from core.kb.dynamic_kb_manager import DynamicKBManager

        with pytest.raises(ValueError, match="vault_path"):
            DynamicKBManager._build_mcp_client({"vault_path": ""})

    def test_build_obsidian_client_success(self):
        # 测试 _build_obsidian_client 成功构建
        from core.kb.dynamic_kb_manager import DynamicKBManager

        config = {"vault_path": "/tmp/v", "connection_url": "http://x", "auth_token": "k"}
        mock_client = MagicMock()
        with patch("core.kb.mcp_client.MCPClient", return_value=mock_client) as mc:
            result = DynamicKBManager._build_obsidian_client(config)
        assert result is mock_client
        call_kwargs = mc.call_args[1]
        assert call_kwargs["use_obsidian_api"] is True
        assert call_kwargs["obsidian_api_base"] == "http://x"


# ═══════════════════════════════════════════════════════════════
# DynamicKBManager — 单例 / reload / is_configured
# ═══════════════════════════════════════════════════════════════


class TestSingletonAndReload:
    """测试单例获取和 reload 方法。"""

    def test_get_instance_singleton(self):
        # 测试 get_instance 返回同一实例（单例）
        from core.kb.dynamic_kb_manager import DynamicKBManager

        with patch("db.session.session_scope", side_effect=Exception("no DB")):
            inst1 = DynamicKBManager.get_instance()
            inst2 = DynamicKBManager.get_instance()
        assert inst1 is inst2

    def test_reload_returns_true_when_config_loaded(self, mock_db_session):
        # 测试 reload 成功加载配置返回 True
        from core.kb.dynamic_kb_manager import DynamicKBManager

        with patch("db.session.session_scope", side_effect=Exception("init fail")):
            mgr = DynamicKBManager()

        # reload 时 DB 有配置
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = _mock_kb_config(
            provider="mcp_filesystem", vault="/tmp/rv"
        )
        with patch("core.kb.mcp_client.MCPClient", return_value=MagicMock()):
            result = mgr.reload()
        assert result is True

    def test_reload_returns_false_when_dummy(self, mock_db_session):
        # 测试 reload 降级 Dummy 时返回 False
        from core.kb.dynamic_kb_manager import DynamicKBManager

        with patch("db.session.session_scope", side_effect=Exception("init fail")):
            mgr = DynamicKBManager()

        mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        result = mgr.reload()
        assert result is False

    def test_is_configured_true_after_load(self, mock_db_session):
        # 测试成功加载配置后 is_configured 返回 True
        from core.kb.dynamic_kb_manager import DynamicKBManager

        mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = _mock_kb_config(
            provider="mcp_filesystem", vault="/tmp/v"
        )
        with patch("core.kb.mcp_client.MCPClient", return_value=MagicMock()):
            mgr = DynamicKBManager()
        assert mgr.is_configured() is True

    def test_is_configured_false_when_dummy(self):
        # 测试 Dummy 模式下 is_configured 返回 False
        from core.kb.dynamic_kb_manager import DynamicKBManager

        with patch("db.session.session_scope", side_effect=Exception("no DB")):
            mgr = DynamicKBManager()
        assert mgr.is_configured() is False

    def test_get_config_returns_loaded_config(self, mock_db_session):
        # 测试 get_config 返回已加载的配置 dict
        from core.kb.dynamic_kb_manager import DynamicKBManager

        mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = _mock_kb_config(
            provider="mcp_filesystem", vault="/tmp/gc"
        )
        with patch("core.kb.mcp_client.MCPClient", return_value=MagicMock()):
            mgr = DynamicKBManager()
        cfg = mgr.get_config()
        assert cfg is not None
        assert cfg["vault_path"] == "/tmp/gc"


# ═══════════════════════════════════════════════════════════════
# 便捷入口
# ═══════════════════════════════════════════════════════════════


class TestGetDynamicKBManager:
    """测试 get_dynamic_kb_manager 便捷函数。"""

    def test_get_dynamic_kb_manager_returns_singleton(self):
        # 测试 get_dynamic_kb_manager 返回单例
        from core.kb.dynamic_kb_manager import get_dynamic_kb_manager, DynamicKBManager

        with patch("db.session.session_scope", side_effect=Exception("no DB")):
            mgr = get_dynamic_kb_manager()
        assert isinstance(mgr, DynamicKBManager)
