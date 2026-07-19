#!/usr/bin/env python3
"""
配置 API 路由

Endpoints:
  GET /api/config  — 查看配置（API Key 脱敏）
"""

from fastapi import APIRouter

from core.config_loader import load_config, validate_config

router = APIRouter(tags=["config"])


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
