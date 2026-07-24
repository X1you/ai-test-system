#!/usr/bin/env python3
"""
V2 批量操作端点的纯函数单元测试。

不依赖 FastAPI / 网络 — 直接调用 endpoint 内部逻辑。
覆盖：
  - batch_toggle: 启用/禁用 + 默认自动切换 + 未知名字忽略
  - batch_delete: 删除 + 默认保护 + 列表清空保护
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


def _seed_config(cfg: Path, providers: list[dict], default: str | None = None) -> None:
    """写一份测试用 config.yaml"""
    import yaml

    data = {
        "llm": {
            "default": default,
            "providers": providers,
        }
    }
    cfg.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ─── BatchToggleRequest 直接构造（不需要通过 FastAPI） ───

class FakeBatchToggleBody:
    def __init__(self, names, enabled):
        self.names = names
        self.enabled = enabled


class FakeBatchDeleteBody:
    def __init__(self, names):
        self.names = names


def test_batch_toggle_disable_default_then_auto_switch(tmp_path):
    """默认 provider 被禁用时，自动切换到下一个 enabled provider。"""
    from web.api.config import _patch_yaml_file, batch_toggle

    cfg = tmp_path / "config.yaml"
    _seed_config(
        cfg,
        [
            {"name": "a", "enabled": True, "priority": 0, "protocol": "openai_compatible"},
            {"name": "b", "enabled": True, "priority": 1, "protocol": "openai_compatible"},
            {"name": "c", "enabled": True, "priority": 2, "protocol": "openai_compatible"},
        ],
        default="a",
    )
    # 覆盖 PROJECT_ROOT（通过 patch）
    from web.api import config as cfg_mod

    orig_root = cfg_mod.PROJECT_ROOT
    cfg_mod.PROJECT_ROOT = tmp_path
    try:
        # 把 config 放根目录
        src = tmp_path / "config.yaml"
        # batch_toggle 写回时使用 PROJECT_ROOT / "config.yaml"
        result = _run(batch_toggle(FakeBatchToggleBody(["a"], False)))
    finally:
        cfg_mod.PROJECT_ROOT = orig_root

    assert result["ok"] is True
    assert result["enabled"] is False
    assert "a" in result["updated"]
    assert result["default"] == "b", f"expected default to auto-switch to b, got {result['default']}"


def test_batch_toggle_ignore_unknown_names(tmp_path):
    """未知名字应被忽略，不抛错。"""
    from web.api import config as cfg_mod
    from web.api.config import batch_toggle

    cfg = tmp_path / "config.yaml"
    _seed_config(
        cfg,
        [
            {"name": "a", "enabled": True, "priority": 0, "protocol": "openai_compatible"},
        ],
        default="a",
    )
    orig_root = cfg_mod.PROJECT_ROOT
    cfg_mod.PROJECT_ROOT = tmp_path
    try:
        result = _run(batch_toggle(FakeBatchToggleBody(["a", "ghost"], False)))
    finally:
        cfg_mod.PROJECT_ROOT = orig_root

    assert result["ok"] is True
    assert "a" in result["updated"]
    assert "ghost" in result["ignored"]


def test_batch_toggle_all_unknown_returns_404(tmp_path):
    """所有名字都不存在 → 404。"""
    from fastapi import HTTPException

    from web.api import config as cfg_mod
    from web.api.config import batch_toggle

    cfg = tmp_path / "config.yaml"
    _seed_config(
        cfg,
        [{"name": "a", "enabled": True, "priority": 0, "protocol": "openai_compatible"}],
        default="a",
    )
    orig_root = cfg_mod.PROJECT_ROOT
    cfg_mod.PROJECT_ROOT = tmp_path
    try:
        try:
            _run(batch_toggle(FakeBatchToggleBody(["x", "y"], True)))
            raised = False
        except HTTPException as e:
            raised = True
            assert e.status_code == 404
    finally:
        cfg_mod.PROJECT_ROOT = orig_root
    assert raised, "应当抛 404"


def test_batch_toggle_enable_disabled_providers(tmp_path):
    """批量启用禁用的 provider。"""
    from web.api import config as cfg_mod
    from web.api.config import batch_toggle

    cfg = tmp_path / "config.yaml"
    _seed_config(
        cfg,
        [
            {"name": "a", "enabled": True, "priority": 0, "protocol": "openai_compatible"},
            {"name": "b", "enabled": False, "priority": 1, "protocol": "openai_compatible"},
        ],
        default="a",
    )
    orig_root = cfg_mod.PROJECT_ROOT
    cfg_mod.PROJECT_ROOT = tmp_path
    try:
        result = _run(batch_toggle(FakeBatchToggleBody(["b"], True)))
    finally:
        cfg_mod.PROJECT_ROOT = orig_root

    assert result["ok"] is True
    assert result["enabled"] is True
    assert "b" in result["updated"]


def test_batch_delete_success(tmp_path):
    """批量删除非默认 provider。"""
    from web.api import config as cfg_mod
    from web.api.config import batch_delete

    cfg = tmp_path / "config.yaml"
    _seed_config(
        cfg,
        [
            {"name": "a", "enabled": True, "priority": 0, "protocol": "openai_compatible"},
            {"name": "b", "enabled": True, "priority": 1, "protocol": "openai_compatible"},
            {"name": "c", "enabled": True, "priority": 2, "protocol": "openai_compatible"},
        ],
        default="a",
    )
    orig_root = cfg_mod.PROJECT_ROOT
    cfg_mod.PROJECT_ROOT = tmp_path
    try:
        result = _run(batch_delete(FakeBatchDeleteBody(["b", "c"])))
    finally:
        cfg_mod.PROJECT_ROOT = orig_root

    assert result["ok"] is True
    assert "b" in result["deleted"]
    assert "c" in result["deleted"]
    assert result["remaining"] == 1


def test_batch_delete_rejects_default(tmp_path):
    """删除默认 provider 应被拒绝（400）。"""
    from fastapi import HTTPException

    from web.api import config as cfg_mod
    from web.api.config import batch_delete

    cfg = tmp_path / "config.yaml"
    _seed_config(
        cfg,
        [
            {"name": "a", "enabled": True, "priority": 0, "protocol": "openai_compatible"},
            {"name": "b", "enabled": True, "priority": 1, "protocol": "openai_compatible"},
        ],
        default="a",
    )
    orig_root = cfg_mod.PROJECT_ROOT
    cfg_mod.PROJECT_ROOT = tmp_path
    try:
        try:
            _run(batch_delete(FakeBatchDeleteBody(["a"])))
            raised = False
        except HTTPException as e:
            raised = True
            assert e.status_code == 400
            assert "默认" in e.detail
    finally:
        cfg_mod.PROJECT_ROOT = orig_root
    assert raised


def test_batch_delete_rejects_empty_remaining(tmp_path):
    """会清空列表应被拒绝（400）。"""
    from fastapi import HTTPException

    from web.api import config as cfg_mod
    from web.api.config import batch_delete

    cfg = tmp_path / "config.yaml"
    _seed_config(
        cfg,
        [{"name": "a", "enabled": True, "priority": 0, "protocol": "openai_compatible"}],
        default=None,  # 没有 default 限制，但只剩 1 个，删它就清空
    )
    orig_root = cfg_mod.PROJECT_ROOT
    cfg_mod.PROJECT_ROOT = tmp_path
    try:
        try:
            _run(batch_delete(FakeBatchDeleteBody(["a"])))
            raised = False
        except HTTPException as e:
            raised = True
            assert e.status_code == 400
            assert "至少保留 1 个" in e.detail
    finally:
        cfg_mod.PROJECT_ROOT = orig_root
    assert raised


def test_batch_delete_ignores_unknown(tmp_path):
    """未知名字应被忽略。"""
    from web.api import config as cfg_mod
    from web.api.config import batch_delete

    cfg = tmp_path / "config.yaml"
    _seed_config(
        cfg,
        [
            {"name": "a", "enabled": True, "priority": 0, "protocol": "openai_compatible"},
            {"name": "b", "enabled": True, "priority": 1, "protocol": "openai_compatible"},
        ],
        default="a",
    )
    orig_root = cfg_mod.PROJECT_ROOT
    cfg_mod.PROJECT_ROOT = tmp_path
    try:
        result = _run(batch_delete(FakeBatchDeleteBody(["b", "ghost"])))
    finally:
        cfg_mod.PROJECT_ROOT = orig_root

    assert result["ok"] is True
    assert "b" in result["deleted"]
    assert "ghost" in result["ignored"]


def test_batch_toggle_keeps_order(tmp_path):
    """批量启用/禁用后 providers 顺序不应改变。"""
    from web.api import config as cfg_mod
    from web.api.config import _read_user_config, batch_toggle

    cfg = tmp_path / "config.yaml"
    _seed_config(
        cfg,
        [
            {"name": "a", "enabled": True, "priority": 0, "protocol": "openai_compatible"},
            {"name": "b", "enabled": True, "priority": 1, "protocol": "openai_compatible"},
            {"name": "c", "enabled": True, "priority": 2, "protocol": "openai_compatible"},
        ],
        default="a",
    )
    orig_root = cfg_mod.PROJECT_ROOT
    cfg_mod.PROJECT_ROOT = tmp_path
    try:
        _run(batch_toggle(FakeBatchToggleBody(["a", "c"], False)))
        data = _read_user_config(tmp_path / "config.yaml")
    finally:
        cfg_mod.PROJECT_ROOT = orig_root

    names = [p["name"] for p in data["llm"]["providers"]]
    assert names == ["a", "b", "c"], f"顺序错乱: {names}"
    # a/c 应为 disabled
    enabled_map = {p["name"]: p["enabled"] for p in data["llm"]["providers"]}
    assert enabled_map["a"] is False
    assert enabled_map["b"] is True
    assert enabled_map["c"] is False
