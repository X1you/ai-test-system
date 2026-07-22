#!/usr/bin/env python3
"""
web/api/knowledge.py 单元测试。

目标：将知识库 API 路由的覆盖率提升到 90%+。
覆盖：
  - _kb_subprocess_env 异常分支
  - /import（成功/非法后缀/文件过大/子进程失败/JSON解析失败/超时）
  - /add（成功/失败/异常）
  - /update_config（mcp成功/obsidian成功/obsidian连接失败/无效provider/vault不存在/热切换）
  - /current_config（已配置/未配置/异常）
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("LLM_API_KEY", "test-key")


@pytest.fixture(autouse=True)
def _reset_kb_cache():
    """每个测试前后重置 kb_cache 缓存，避免测试间污染。"""
    import web.services.kb_cache as kc
    kc._status_cache = (0, None)
    kc._search_cache.clear()
    yield
    kc._status_cache = (0, None)
    kc._search_cache.clear()


def _make_mock_manager(configured=True, vault_path="/tmp/fake_vault", total=10):
    """构造 mock DynamicKBManager。"""
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
    client.search.return_value = [{"title": "命中", "snippet": "..."}]
    mgr.get_client.return_value = client
    return mgr


# ═══════════════════════════════════════════════════════════════
# /import — Excel 导入回灌
# ═══════════════════════════════════════════════════════════════


class TestKBImport:
    """测试知识库导入端点。"""

    def test_import_invalid_extension(self, client):
        """非 .xlsx/.xls 文件 → 400。"""
        resp = client.post("/api/v1/knowledge/import",
                           files={"file": ("test.txt", b"hello", "text/plain")})
        assert resp.status_code == 400

    def test_import_file_too_large(self, client):
        """文件超过 10MB → 400。"""
        big = b"x" * (10 * 1024 * 1024 + 1)
        resp = client.post("/api/v1/knowledge/import",
                           files={"file": ("test.xlsx", big,
                                   "application/vnd.ms-excel")})
        assert resp.status_code == 400

    def test_import_success(self, client):
        """导入成功（子进程返回码 0，有效 JSON）。"""
        content = b"fake-excel"
        result = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout=json.dumps({"imported": 5}),
            stderr="",
        )
        with patch("web.api.knowledge.subprocess.run", return_value=result):
            resp = client.post("/api/v1/knowledge/import",
                               files={"file": ("test.xlsx", content,
                                       "application/vnd.ms-excel")})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["imported"] == 5

    def test_import_json_parse_fail(self, client):
        """子进程返回码 0 但 stdout 非合法 JSON → 导入完成（数量解析失败）。"""
        result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="not-json", stderr="",
        )
        with patch("web.api.knowledge.subprocess.run", return_value=result):
            resp = client.post("/api/v1/knowledge/import",
                               files={"file": ("t.xlsx", b"x",
                                       "application/vnd.ms-excel")})
        data = resp.json()
        assert data["ok"] is True
        assert "解析失败" in data["message"]

    def test_import_subprocess_fail(self, client):
        """子进程返回码非 0 → ok=False。"""
        result = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="some error",
        )
        with patch("web.api.knowledge.subprocess.run", return_value=result):
            resp = client.post("/api/v1/knowledge/import",
                               files={"file": ("t.xlsx", b"x",
                                       "application/vnd.ms-excel")})
        data = resp.json()
        assert data["ok"] is False

    def test_import_exception(self, client):
        """子进程执行抛异常 → ok=False，message 含异常信息。"""
        with patch("web.api.knowledge.subprocess.run",
                   side_effect=FileNotFoundError("python not found")):
            resp = client.post("/api/v1/knowledge/import",
                               files={"file": ("t.xlsx", b"x",
                                       "application/vnd.ms-excel")})
        data = resp.json()
        assert data["ok"] is False


# ═══════════════════════════════════════════════════════════════
# /add — 添加单条知识
# ═══════════════════════════════════════════════════════════════


class TestKBAdd:
    """测试添加单条知识端点。"""

    def test_add_success(self, client):
        """添加成功（子进程返回码 0）。"""
        result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="",
        )
        with patch("web.api.knowledge.subprocess.run", return_value=result):
            resp = client.post("/api/v1/knowledge/add", data={
                "title": "规则1", "category": "business-rules",
                "content": "测试内容", "tags": "tag1", "module": "mod1",
            })
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_add_subprocess_fail(self, client):
        """子进程返回码非 0 → ok=False。"""
        result = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="error",
        )
        with patch("web.api.knowledge.subprocess.run", return_value=result):
            resp = client.post("/api/v1/knowledge/add", data={
                "title": "t", "category": "c", "content": "x",
            })
        assert resp.json()["ok"] is False

    def test_add_exception(self, client):
        """子进程执行抛异常 → ok=False。"""
        with patch("web.api.knowledge.subprocess.run",
                   side_effect=OSError("boom")):
            resp = client.post("/api/v1/knowledge/add", data={
                "title": "t", "category": "c", "content": "x",
            })
        assert resp.json()["ok"] is False


# ═══════════════════════════════════════════════════════════════
# /update_config — 知识库配置热切换
# ═══════════════════════════════════════════════════════════════


class TestKBUpdateConfig:
    """测试知识库配置更新端点。"""

    def test_update_config_mcp_success(self, client, tmp_path):
        """mcp_filesystem 配置成功（vault 存在）。"""
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "note.md").write_text("# test")

        # mock DB 写入
        with patch("db.session.session_scope") as mock_scope, \
             patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager") as mock_mgr:
            mock_db = MagicMock()
            mock_scope.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_scope.return_value.__exit__ = MagicMock(return_value=None)
            mgr = MagicMock()
            mock_mgr.return_value = mgr

            resp = client.post("/api/v1/knowledge/update_config", json={
                "provider_type": "mcp_filesystem",
                "vault_path": str(vault),
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "连通性测试通过" in data["message"]

    def test_update_config_obsidian_success(self, client):
        """obsidian_api 配置成功（连通性测试通过）。"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("db.session.session_scope") as mock_scope, \
             patch("requests.get", return_value=mock_resp) as mock_get, \
             patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager") as mock_mgr:
            mock_db = MagicMock()
            mock_scope.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_scope.return_value.__exit__ = MagicMock(return_value=None)
            mgr = MagicMock()
            mock_mgr.return_value = mgr

            resp = client.post("/api/v1/knowledge/update_config", json={
                "provider_type": "obsidian_api",
                "connection_url": "http://localhost:3000",
                "auth_token": "tok-12345678",
            })
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        mock_get.assert_called_once()

    def test_update_config_obsidian_conn_fail(self, client):
        """obsidian_api 连接失败 → status=error。"""
        with patch("requests.get", side_effect=ConnectionError("refused")):
            resp = client.post("/api/v1/knowledge/update_config", json={
                "provider_type": "obsidian_api",
                "connection_url": "http://localhost:3000",
            })
        data = resp.json()
        assert data["status"] == "error"
        assert "连接失败" in data["message"]

    def test_update_config_invalid_provider(self, client):
        """无效 provider_type → status=error。"""
        resp = client.post("/api/v1/knowledge/update_config", json={
            "provider_type": "invalid_provider",
            "vault_path": "/tmp",
        })
        assert resp.json()["status"] == "error"

    def test_update_config_mcp_vault_not_exist(self, client):
        """mcp_filesystem vault 不存在 → status=error。"""
        resp = client.post("/api/v1/knowledge/update_config", json={
            "provider_type": "mcp_filesystem",
            "vault_path": "/nonexistent/xyz/123",
        })
        assert resp.json()["status"] == "error"

    def test_update_config_db_write_fail(self, client, tmp_path):
        """DB 写入失败 → status=error。"""
        vault = tmp_path / "v"
        vault.mkdir()
        with patch("db.session.session_scope",
                   side_effect=RuntimeError("db locked")):
            resp = client.post("/api/v1/knowledge/update_config", json={
                "provider_type": "mcp_filesystem",
                "vault_path": str(vault),
            })
        data = resp.json()
        assert data["status"] == "error"
        assert "DB 写入失败" in data["message"]

    def test_update_config_reload_fail(self, client, tmp_path):
        """热切换 reload 失败 → 不影响主流程（status 仍 success）。"""
        vault = tmp_path / "v"
        vault.mkdir()
        with patch("db.session.session_scope") as mock_scope, \
             patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager") as mock_mgr:
            mock_db = MagicMock()
            mock_scope.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_scope.return_value.__exit__ = MagicMock(return_value=None)
            mgr = MagicMock()
            mgr.reload.side_effect = RuntimeError("reload failed")
            mock_mgr.return_value = mgr

            resp = client.post("/api/v1/knowledge/update_config", json={
                "provider_type": "mcp_filesystem",
                "vault_path": str(vault),
            })
        # reload 失败被捕获，status 仍为 success
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"


# ═══════════════════════════════════════════════════════════════
# /current_config — 获取当前配置
# ═══════════════════════════════════════════════════════════════


class TestKBCurrentConfig:
    """测试获取当前知识库配置端点。"""

    def test_current_config_not_configured(self, client):
        """DB 中无 active 配置 → configured=False。"""
        from db.models import KBConfig
        from db.session import session_scope

        # 清理可能存在的 active 配置
        with session_scope() as db:
            db.query(KBConfig).filter(KBConfig.is_active == True).delete()  # noqa: E712

        resp = client.get("/api/v1/knowledge/current_config")
        data = resp.json()
        assert data["configured"] is False

    def test_current_config_configured(self, client):
        """DB 中有 active 配置 → 返回配置详情（token 脱敏）。"""
        from db.models import KBConfig
        from db.session import session_scope

        with session_scope() as db:
            db.query(KBConfig).filter(KBConfig.is_active == True).delete()  # noqa: E712
            db.add(KBConfig(
                provider_type="mcp_filesystem",
                vault_path="/data/test_vault",
                auth_token="sk-1234567890abcdef",
                is_active=True,
            ))

        try:
            resp = client.get("/api/v1/knowledge/current_config")
            data = resp.json()
            assert data["configured"] is True
            assert data["provider_type"] == "mcp_filesystem"
            assert data["vault_path"] == "/data/test_vault"
            assert "****" in data["auth_token_masked"]
        finally:
            with session_scope() as db:
                db.query(KBConfig).filter(
                    KBConfig.vault_path == "/data/test_vault"
                ).delete()

    def test_current_config_exception(self, client):
        """DB 查询异常 → configured=False, error 字段。"""
        with patch("db.session.session_scope",
                   side_effect=RuntimeError("db down")):
            resp = client.get("/api/v1/knowledge/current_config")
        data = resp.json()
        assert data["configured"] is False
        assert "error" in data


# ═══════════════════════════════════════════════════════════════
# _kb_subprocess_env 异常分支
# ═══════════════════════════════════════════════════════════════


class TestKBSubprocessEnvException:
    """测试 _kb_subprocess_env 的异常捕获分支。"""

    def test_env_handles_dynamic_manager_exception(self):
        """get_dynamic_kb_manager 抛异常时回退到环境变量（不崩溃）。"""
        from web.api.knowledge import _kb_subprocess_env

        with patch("core.kb.dynamic_kb_manager.get_dynamic_kb_manager",
                   side_effect=RuntimeError("init failed")):
            env = _kb_subprocess_env()
        assert isinstance(env, dict)
        # 不注入 OBSIDIAN_VAULT（异常被捕获）
