#!/usr/bin/env python3
"""
配置 API 路由

Endpoints:
  GET  /api/config  — 查看配置（API Key 脱敏）
  PUT  /api/config  — 更新安全配置字段（pipeline / output / llm）

注：知识库配置已迁移到 DB（DynamicKBManager），通过 /knowledge/update_config 管理，
不再走本端点。GET 返回的 knowledge_base 字段改从 DB 读取（只读，兼容旧消费者）。
"""

from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.config_loader import PROJECT_ROOT, load_config, validate_config

router = APIRouter(tags=["config"])

# ─── 允许前端更新的白名单字段 ───
_UPDATABLE_SECTIONS = {"pipeline", "output", "llm"}

# ─── LLM 段允许更新的字段（api_key 特殊处理：空=不改） ───
_LLM_UPDATABLE_FIELDS = {"provider", "model", "base_url", "temperature", "api_key"}


class ConfigUpdate(BaseModel):
    """前端可更新的配置字段。"""
    pipeline: dict | None = None
    output: dict | None = None
    llm: dict | None = None


def _patch_yaml_file(cfg_path: Path, updates: dict) -> None:
    """行级替换 YAML 文件中的键值，保留注释和原始格式。"""
    lines = cfg_path.read_text(encoding="utf-8").splitlines(keepends=True)
    result: list[str] = []
    pending: dict[str, dict] = {s: dict(v) for s, v in updates.items()}
    current_section: str | None = None

    def _fmt(v) -> str:
        if isinstance(v, bool):
            return "true" if v else "false"
        return str(v)

    def _flush(section: str | None):
        if section and section in pending and pending[section]:
            for k, v in pending[section].items():
                result.append(f"  {k}: {_fmt(v)}\n")
            pending[section] = {}

    for line in lines:
        stripped = line.rstrip("\n\r")
        # 顶级 section 行（无缩进 `word:`）
        if stripped and not stripped[0].isspace() and stripped.endswith(":") and not stripped.startswith("#"):
            _flush(current_section)
            current_section = stripped[:-1].strip()
            result.append(line)
            continue
        # 段内 key: value 行
        if current_section in pending and stripped and stripped[0].isspace():
            content = stripped.lstrip()
            if ":" in content and not content.startswith("#"):
                key = content.split(":", 1)[0].strip()
                if key in pending[current_section]:
                    indent = stripped[: len(stripped) - len(content)]
                    result.append(f"{indent}{key}: {_fmt(pending[current_section].pop(key))}\n")
                    continue
        result.append(line)

    _flush(current_section)
    # 文件末尾追加全新段
    for section, vals in pending.items():
        if vals:
            result.append(f"\n{section}:\n")
            for k, v in vals.items():
                result.append(f"  {k}: {_fmt(v)}\n")

    cfg_path.write_text("".join(result), encoding="utf-8")


@router.get("")
async def get_config():
    """查看当前配置（API Key 脱敏）"""
    config = load_config()

    llm = config.get("llm", {})
    api_key = llm.get("api_key", "")
    if len(api_key) > 12:
        masked = api_key[:8] + "..." + api_key[-4:]
    elif api_key:
        masked = "***"
    else:
        masked = "未配置"

    # 知识库配置改从 DB 读取（与知识库页面/健康检查同源）
    try:
        from core.kb.dynamic_kb_manager import get_dynamic_kb_manager

        _mgr = get_dynamic_kb_manager()
        _kb_cfg = _mgr.get_config() or {}
        kb = {
            "enabled": _mgr.is_configured(),
            "vault_path": _kb_cfg.get("vault_path", "N/A"),
        }
    except Exception:
        kb = {"enabled": False, "vault_path": "N/A"}
    pipe = config.get("pipeline", {})

    errors = validate_config(config)

    return {
        "llm": {
            "provider": llm.get("provider", "N/A"),
            "model": llm.get("model", "N/A"),
            "base_url": llm.get("base_url", "N/A"),
            "api_key": masked,
            "temperature": llm.get("temperature", 0.3),
        },
        "knowledge_base": {
            "enabled": kb.get("enabled", False),
            "vault_path": kb.get("vault_path", "N/A"),
        },
        "pipeline": {
            "default_mode": pipe.get("default_mode", "semi"),
            "default_dimensions": pipe.get("default_dimensions", "basic"),
            "default_formats": pipe.get("default_formats", "excel"),
            "self_check": pipe.get("self_check", False),
        },
        "validation": {
            "valid": len(errors) == 0,
            "errors": errors,
        },
    }


@router.put("")
async def update_config(body: ConfigUpdate):
    """更新安全配置字段（pipeline / knowledge_base / output / llm）。

    只允许白名单 section。LLM 的 api_key 只在传入非空非掩码值时更新。
    更新后写回 config.yaml 并重新校验。
    """
    cfg_path = PROJECT_ROOT / "config.yaml"

    # 读取现有 YAML
    user_config: dict = {}
    if cfg_path.exists():
        try:
            with open(cfg_path, encoding="utf-8") as f:
                user_config = yaml.safe_load(f) or {}
        except Exception:
            user_config = {}

    # 合并白名单字段
    updates = body.model_dump(exclude_none=True)
    changed = []
    for section, values in updates.items():
        if section not in _UPDATABLE_SECTIONS:
            raise HTTPException(400, f"不允许修改配置段: {section}")
        if not isinstance(values, dict):
            raise HTTPException(400, f"配置段 {section} 必须是对象")

        # LLM 段：只允许白名单字段，api_key 特殊处理
        if section == "llm":
            filtered = {}
            for k, v in values.items():
                if k not in _LLM_UPDATABLE_FIELDS:
                    continue
                # api_key 为空或掩码格式 → 不修改（保留原值）
                if k == "api_key":
                    if not v or "..." in str(v) or v == "***":
                        continue
                filtered[k] = v
            values = filtered
            updates[section] = filtered

        if section not in user_config:
            user_config[section] = {}
        user_config[section].update(values)
        if values:
            changed.append(section)

    if not changed:
        raise HTTPException(400, "未提供任何可更新的配置字段")

    # 写回 YAML（行级替换，保留注释和格式）
    try:
        _patch_yaml_file(cfg_path, updates)
    except Exception as e:
        raise HTTPException(500, f"写入配置文件失败: {e}")

    # 重新加载并校验
    config = load_config()
    errors = validate_config(config)

    return {
        "ok": True,
        "message": f"已更新: {', '.join(changed)}",
        "changed": changed,
        "validation": {
            "valid": len(errors) == 0,
            "errors": errors,
        },
    }
