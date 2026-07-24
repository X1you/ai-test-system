"""e2e 测试公共 fixture。

- backup_config：备份/恢复 config.yaml，PUT /config 测试会修改它
- seed_providers：写入一组已知 provider 到 config.yaml，供生命周期测试
- mock_llm_client：mock LLM 连接测试，避免真实 HTTP 调用
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("LLM_API_KEY", "sk-test-e2e-dummy")

_CFG = PROJECT_ROOT / "config.yaml"


@pytest.fixture
def backup_config():
    """备份 config.yaml，测试后恢复（PUT /config 会写盘）。

    恢复文件后必须清除 config_loader 缓存，否则后续测试（如
    test_batch_operations_pure）会读到 e2e seed 写入的陈旧缓存配置。
    """
    bak = _CFG.read_bytes() if _CFG.exists() else None
    yield
    if bak is not None:
        _CFG.write_bytes(bak)
    else:
        _CFG.unlink(missing_ok=True)
    _invalidate_config_cache()


def _invalidate_config_cache():
    """清除 config_loader 的内存缓存，避免跨测试状态污染。"""
    try:
        from core import config_loader as _cl
        if hasattr(_cl, "_config_cache"):
            _cl._config_cache = None
        if hasattr(_cl, "_CACHE"):
            _cl._CACHE.clear()
    except Exception:
        pass


@pytest.fixture
def seed_providers(backup_config):
    """写入 3 个已知 provider 到 config.yaml，返回配置 dict。"""
    import yaml

    cfg = {
        "llm": {
            "providers": [
                {
                    "name": "glm", "provider": "bigmodel", "protocol": "openai_compatible",
                    "base_url": "https://open.bigmodel.cn/api/paas/v4",
                    "api_key": "sk-glm-test-1234567890wxyz", "model": "glm-4.7-flash",
                    "temperature": 0.3, "max_tokens": 8192, "timeout": 120, "retry": 2,
                    "enabled": True, "priority": 0, "tags": ["production"],
                },
                {
                    "name": "deepseek", "provider": "deepseek", "protocol": "openai_compatible",
                    "base_url": "https://api.deepseek.com/v1",
                    "api_key": "sk-deepseek-test-1234567890abcd", "model": "deepseek-chat",
                    "temperature": 0.3, "max_tokens": 8192, "timeout": 120, "retry": 2,
                    "enabled": True, "priority": 1, "tags": ["备用"],
                },
                {
                    "name": "claude", "provider": "anthropic", "protocol": "anthropic",
                    "base_url": "https://api.anthropic.com",
                    "api_key": "sk-ant-claude-test-1234567890efgh", "model": "claude-3-5-sonnet",
                    "temperature": 0.3, "max_tokens": 8192, "timeout": 120, "retry": 2,
                    "enabled": False, "priority": 2, "tags": ["production"],
                },
            ],
            "default": "glm",
        },
        "pipeline": {
            "default_mode": "semi",
            "default_dimensions": "basic",
            "default_formats": "excel",
            "self_check": False,
        },
    }
    _CFG.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    # 清除 config_loader 缓存，确保下一次 load_config 读到新文件
    try:
        from core import config_loader as _cl
        if hasattr(_cl, "_config_cache"):
            _cl._config_cache = None
        if hasattr(_cl, "_CACHE"):
            _cl._CACHE.clear()
    except Exception:
        pass
    yield cfg


@pytest.fixture
def ensure_admin_user():
    """确保 admin 用户存在（用已知密码），返回 (username, password)。"""
    from db.session import init_db, session_scope
    from db.models import User
    from web.services.user_service import hash_password

    init_db()
    username, password = "admin", "admin123-e2e"
    with session_scope() as session:
        existing = session.query(User).filter(User.username == username).first()
        if existing:
            existing.password_hash = hash_password(password)
            existing.role = "admin"
        else:
            session.add(User(
                username=username,
                password_hash=hash_password(password),
                role="admin",
                api_key="sk-admin-e2e-test-key",
            ))
    return username, password


@pytest.fixture
def mock_llm_connection():
    """mock LLM 客户端的 test_connection，避免真实 HTTP 调用。"""
    def _factory(ok: bool = True, latency: int = 250):
        mock_client = MagicMock()
        mock_client.test_connection.return_value = {
            "ok": ok,
            "status": "ok" if ok else "error: connection refused",
            "latency_ms": latency,
            "provider": "mock",
            "model": "mock-model",
            "protocol": "openai_compatible",
        }
        mock_client.provider = "mock"
        mock_client.model = "mock-model"
        mock_client.protocol = "openai_compatible"
        return patch("web.api.config.create_llm_client", return_value=mock_client)
    return _factory
