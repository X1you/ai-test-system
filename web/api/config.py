#!/usr/bin/env python3
"""
配置 API 路由

Endpoints:
  GET  /api/config  — 查看配置（API Key 脱敏）
  PUT  /api/config  — 更新安全配置字段（pipeline / knowledge_base / output）
"""

from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.config_loader import load_config, validate_config, PROJECT_ROOT

router = APIRouter(tags=["config"])

# ─── 允许前端更新的白名单字段 ───
_UPDATABLE_SECTIONS = {"pipeline", "knowledge_base", "output"}


class ConfigUpdate(BaseModel):
    """前端可更新的配置字段（不含 LLM 敏感信息）。"""
    pipeline: dict | None = None
    knowledge_base: dict | None = None
    output: dict | None = None


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

    kb = config.get("knowledge_base", {})
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
    """更新安全配置字段（pipeline / knowledge_base / output）。

    只允许白名单 section，LLM 敏感配置不可通过此接口修改。
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
        if section not in user_config:
            user_config[section] = {}
        user_config[section].update(values)
        changed.append(section)

    if not changed:
        raise HTTPException(400, "未提供任何可更新的配置字段")

    # 写回 YAML
    try:
        with open(cfg_path, "w", encoding="utf-8") as f:
            yaml.dump(user_config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
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
