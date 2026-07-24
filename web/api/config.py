#!/usr/bin/env python3
"""
配置 API 路由 — 支持多 LLM Provider 管理

Endpoints:
  GET    /config                    — 查看完整配置（含 providers 列表，API Key 脱敏）
  PUT    /config                    — 部分更新（pipeline / output / llm.providers）
  POST   /config/test_provider      — 测试单个 provider 连接（不入库）
  POST   /config/set_default        — 切换默认 provider
  GET    /config/providers          — 列出所有 provider（仅元数据，无 Key）

注：知识库配置已迁移到 DB，通过 /knowledge/update_config 管理。
"""

from pathlib import Path
from typing import Optional

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.config_loader import PROJECT_ROOT, load_config, validate_config
from core.llm_client import SUPPORTED_PROTOCOLS, create_llm_client

router = APIRouter(tags=["config"])

# ─── 允许前端更新的白名单 section ───
_UPDATABLE_SECTIONS = {"pipeline", "output", "llm"}

# ─── LLM Provider 允许更新的字段 ───
# 注：api_key 特殊处理（空=不改）；protocol 一旦设定不可改 name（防冲突）
_LLM_PROVIDER_UPDATABLE = {
    "name", "protocol", "base_url", "endpoint", "api_key",
    "model", "temperature", "max_tokens", "timeout", "retry",
    "enabled", "priority", "tags", "headers", "body_template",
    "response_path", "method",
}


def _mask_api_key(api_key: str) -> str:
    """脱敏 API Key：保留前 8 后 4，中间用 ... 替代"""
    if not api_key:
        return "未配置"
    if len(api_key) > 12:
        return api_key[:8] + "..." + api_key[-4:]
    return "***"


def _provider_to_dict(p: dict, include_key: bool = False) -> dict:
    """把 provider 配置 dict 序列化为前端友好格式（脱敏 API Key）"""
    out = {
        "name": p.get("name", p.get("provider", "")),
        "provider": p.get("provider") or p.get("name", ""),
        "protocol": p.get("protocol", "openai_compatible"),
        "base_url": p.get("base_url", ""),
        "endpoint": p.get("endpoint", ""),
        "model": p.get("model", ""),
        "temperature": p.get("temperature", 0.3),
        "max_tokens": p.get("max_tokens", 8192),
        "timeout": p.get("timeout", 120),
        "retry": p.get("retry", 2),
        "enabled": p.get("enabled", True),
        "priority": p.get("priority", 0),
        "tags": p.get("tags", []),
        # custom_http 专属字段
        "method": p.get("method", "POST"),
        "headers": p.get("headers", {}),
        "body_template": p.get("body_template", ""),
        "response_path": p.get("response_path", "text"),
    }
    if include_key:
        out["api_key"] = p.get("api_key", "")
    else:
        out["api_key"] = _mask_api_key(p.get("api_key", ""))
    return out


def _get_providers_from_config(llm: dict) -> list[dict]:
    """从 llm 段提取 providers 列表"""
    providers = llm.get("providers", [])
    if not isinstance(providers, list):
        return []
    return [p for p in providers if isinstance(p, dict)]


def _get_provider_by_name(llm: dict, name: str) -> Optional[dict]:
    for p in _get_providers_from_config(llm):
        if p.get("name") == name or p.get("provider") == name:
            return p
    return None


def _patch_yaml_file(cfg_path: Path, updates: dict) -> None:
    """行级替换 YAML 文件中的键值，保留注释和原始格式。"""
    lines = cfg_path.read_text(encoding="utf-8").splitlines(keepends=True)
    result: list[str] = []
    pending: dict[str, dict] = {s: dict(v) for s, v in updates.items() if isinstance(v, dict)}
    current_section: str | None = None

    def _fmt(v) -> str:
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return str(v)
        if v is None:
            return ""
        s = str(v)
        # YAML 字符串里有特殊字符就加引号
        if any(c in s for c in ":#{}[]&*?|>!%@`\n") or s.strip() != s:
            return '"' + s.replace('"', '\\"') + '"'
        return s

    def _flush(section: str | None):
        if section and section in pending and pending[section]:
            for k, v in pending[section].items():
                result.append(f"  {k}: {_fmt(v)}\n")
            pending[section] = {}

    for line in lines:
        stripped = line.rstrip("\n\r")
        if stripped and not stripped[0].isspace() and stripped.endswith(":") and not stripped.startswith("#"):
            _flush(current_section)
            current_section = stripped[:-1].strip()
            result.append(line)
            continue
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
    for section, vals in pending.items():
        if vals:
            result.append(f"\n{section}:\n")
            for k, v in vals.items():
                result.append(f"  {k}: {_fmt(v)}\n")

    cfg_path.write_text("".join(result), encoding="utf-8")


# ─── Pydantic 模型 ───

class ProviderConfig(BaseModel):
    """单个 LLM Provider 配置（API 请求/响应）"""
    name: str = Field(..., min_length=1, max_length=64, description="用户起的别名，唯一")
    protocol: str = Field(default="openai_compatible", description="协议类型")
    base_url: str = ""
    endpoint: str = ""
    api_key: str = ""
    model: str = ""
    temperature: float = 0.3
    max_tokens: int = 8192
    timeout: int = 120
    retry: int = 2
    enabled: bool = True
    priority: int = 0
    tags: list[str] = []
    method: str = "POST"
    headers: dict = Field(default_factory=dict)
    body_template: str = ""
    response_path: str = "text"


class TestProviderRequest(BaseModel):
    """测试单个 provider（不依赖 config 存储）"""
    provider: ProviderConfig
    timeout: float = 10.0


class SetDefaultRequest(BaseModel):
    name: str


class ReorderRequest(BaseModel):
    """V1：拖拽排序（故障转移顺序）。names 为按新顺序排列的 provider name 列表。

    完整列表必须与现有 providers 数量一致（前端发送全量顺序）。
    缺少的 name 视为不在新列表中（保留原位置）；多余的 name 忽略。
    """
    names: list[str] = Field(..., min_length=1)


class BatchToggleRequest(BaseModel):
    """V2：批量启用/禁用。
    names: 要操作的 provider name 列表
    enabled: True 启用 / False 禁用
    """
    names: list[str] = Field(..., min_length=1)
    enabled: bool


class BatchDeleteRequest(BaseModel):
    """V2：批量删除 provider。
    names: 要删除的 provider name 列表
    """
    names: list[str] = Field(..., min_length=1)


class ConfigUpdate(BaseModel):
    """部分更新顶层结构"""
    pipeline: dict | None = None
    output: dict | None = None
    llm: dict | None = None  # 含 providers 列表


# ─── 路由 ───


@router.get("")
async def get_config():
    """查看当前配置（API Key 脱敏）"""
    config = load_config()
    llm = config.get("llm", {})
    providers = _get_providers_from_config(llm)
    default_name = llm.get("default")

    # 知识库配置（从 DB 读，与知识库页面同源）
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

    # 向后兼容字段：取默认 provider 的 LLMConfig（如旧前端期望的 llm.provider / llm.model / llm.base_url / llm.api_key）
    legacy_llm = {
        "provider": "N/A",
        "model": "N/A",
        "base_url": "N/A",
        "api_key": "未配置",
        "temperature": 0.3,
    }
    if providers:
        # 优先取 default，缺省取第一个
        primary = None
        if default_name:
            primary = _get_provider_by_name(llm, default_name)
        if primary is None:
            primary = providers[0]
        legacy_llm = {
            "provider": primary.get("provider") or primary.get("name", "N/A"),
            "model": primary.get("model", "N/A"),
            "base_url": primary.get("base_url", "N/A"),
            "api_key": _mask_api_key(primary.get("api_key", "")),
            "temperature": primary.get("temperature", 0.3),
        }

    return {
        "llm": legacy_llm,  # 向后兼容旧前端
        "llm_providers": [_provider_to_dict(p) for p in providers],  # 新前端
        "llm_default": default_name or (providers[0].get("name") if providers else None),
        "llm_protocols": sorted(SUPPORTED_PROTOCOLS),  # 前端协议下拉用
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
    """部分更新（pipeline / output / llm.providers）"""
    cfg_path = PROJECT_ROOT / "config.yaml"

    # 读取现有 YAML
    user_config: dict = {}
    if cfg_path.exists():
        try:
            with open(cfg_path, encoding="utf-8") as f:
                user_config = yaml.safe_load(f) or {}
        except Exception:
            user_config = {}

    updates = body.model_dump(exclude_none=True)
    changed = []

    for section, values in updates.items():
        if section not in _UPDATABLE_SECTIONS:
            raise HTTPException(400, f"不允许修改配置段: {section}")
        if not isinstance(values, dict):
            raise HTTPException(400, f"配置段 {section} 必须是对象")

        # LLM 段特殊处理：providers 列表整体替换
        if section == "llm":
            if "providers" in values:
                providers_in = values["providers"]
                if not isinstance(providers_in, list):
                    raise HTTPException(400, "llm.providers 必须是数组")
                # 校验 + 清理
                cleaned = []
                for p in providers_in:
                    if not isinstance(p, dict):
                        raise HTTPException(400, "provider 必须是对象")
                    p_clean = {k: v for k, v in p.items() if k in _LLM_PROVIDER_UPDATABLE}
                    # api_key 特殊处理：空或掩码 → 不修改（保留原值）
                    if not p_clean.get("api_key") or "..." in str(p_clean.get("api_key", "")) or p_clean.get("api_key") == "***":
                        p_clean.pop("api_key", None)
                    cleaned.append(p_clean)
                # name 唯一性校验
                names = [p.get("name") for p in cleaned]
                if len(names) != len(set(names)):
                    raise HTTPException(400, "provider name 必须唯一")
                # protocol 校验
                for p in cleaned:
                    if p.get("protocol", "openai_compatible") not in SUPPORTED_PROTOCOLS:
                        raise HTTPException(400, f"不支持的协议: {p.get('protocol')}")
                values["providers"] = cleaned
                # 清除旧 schema 字段
                for k in ("fallback", "provider", "api_key", "base_url", "model", "temperature", "max_tokens", "timeout", "retry"):
                    values.pop(k, None)
                # api_key 保留：被 pop 的（空/掩码）从原配置补回
                orig_llm = user_config.get("llm") or {}
                if isinstance(orig_llm.get("providers"), list):
                    orig_by_name = {
                        p.get("name"): p
                        for p in orig_llm["providers"]
                        if isinstance(p, dict)
                    }
                    for p_clean in cleaned:
                        if "api_key" not in p_clean:
                            orig = orig_by_name.get(p_clean.get("name"))
                            if orig and orig.get("api_key"):
                                p_clean["api_key"] = orig["api_key"]
                # 处理 default 字段
                if "default" in values:
                    default_name = values["default"]
                    if default_name and default_name not in names:
                        raise HTTPException(400, f"default provider '{default_name}' 不在 providers 列表中")
                    values.pop("_migrated", None)

        if section not in user_config:
            user_config[section] = {}
        # 对于 llm.providers 是数组，需要整体替换而不是 merge
        if section == "llm" and "providers" in values:
            user_config[section]["providers"] = values["providers"]
            for k, v in values.items():
                if k != "providers":
                    user_config[section][k] = v
        else:
            user_config[section].update(values)
        if values:
            changed.append(section)

    if not changed:
        raise HTTPException(400, "未提供任何可更新的配置字段")

    try:
        # llm.providers 是数组，_patch_yaml_file 不支持数组写盘；
        # 此时降级为全量重写（会丢注释，但保证结构正确）。
        needs_full_write = isinstance(
            (updates.get("llm") or {}).get("providers"), list
        )
        if needs_full_write:
            _write_full_yaml(cfg_path, user_config)
        else:
            _patch_yaml_file(cfg_path, updates)
    except Exception as e:
        raise HTTPException(500, f"写入配置文件失败: {e}")

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


@router.post("/test_provider")
async def test_provider(body: TestProviderRequest):
    """测试单个 provider 连接（不入库）。

    在 async handler 里用 asyncio.to_thread 包裹同步 SDK 调用，
    避免 httpx 同步客户端阻塞 event loop 触发 500。
    """
    import asyncio
    try:
        p_dict = body.provider.model_dump(exclude_none=True)
    except Exception as e:
        raise HTTPException(400, f"provider 数据格式错误: {e}")
    # 透传协议字段（缺省时用 openai_compatible）
    if not p_dict.get("protocol"):
        p_dict["protocol"] = "openai_compatible"
    try:
        client = create_llm_client(p_dict)
    except Exception as e:
        return {
            "ok": False,
            "status": f"misconfigured: {e}",
            "latency_ms": 0,
            "provider": p_dict.get("name", "unknown"),
            "model": p_dict.get("model", ""),
            "protocol": p_dict.get("protocol", "openai_compatible"),
        }
    # 同步 SDK 调用包到线程池，避免阻塞 event loop
    try:
        result = await asyncio.to_thread(client.test_connection, timeout=body.timeout)
    except Exception as e:
        return {
            "ok": False,
            "status": f"error: {str(e)[:200]}",
            "latency_ms": 0,
            "provider": client.provider,
            "model": client.model,
            "protocol": client.protocol,
        }
    return result


@router.post("/set_default")
async def set_default(body: SetDefaultRequest):
    """设置默认 provider（仅切换 default 标记，不动 providers 列表顺序）"""
    cfg_path = PROJECT_ROOT / "config.yaml"
    user_config: dict = {}
    if cfg_path.exists():
        try:
            with open(cfg_path, encoding="utf-8") as f:
                user_config = yaml.safe_load(f) or {}
        except Exception:
            user_config = {}

    llm = user_config.get("llm", {}) or {}
    providers = llm.get("providers", [])
    names = [p.get("name") for p in providers]
    if body.name not in names:
        raise HTTPException(404, f"provider '{body.name}' 不存在")

    llm["default"] = body.name
    user_config["llm"] = llm
    try:
        _patch_yaml_file(cfg_path, {"llm": {"default": body.name}})
    except Exception as e:
        raise HTTPException(500, f"写入配置文件失败: {e}")
    return {"ok": True, "default": body.name}


@router.post("/reorder_providers")
async def reorder_providers(body: ReorderRequest):
    """V1：拖拽排序（故障转移顺序）。

    入参：names 是按新顺序排列的 provider name 列表。
    行为：
      1. 按 names 列表顺序重排 providers 数组
      2. 同步回写每个 provider 的 priority 字段（index 即 priority，0 优先）
      3. 不变更 default、不变更 enabled、不变更其他字段
    校验：names 必须包含且仅包含当前所有 provider（数量一致 + 无重复 + 无未知）

    错误：
      - 400 名字数量不匹配 / 包含未知 / 重复
      - 500 写盘失败
    """
    cfg_path = PROJECT_ROOT / "config.yaml"
    user_config: dict = {}
    if cfg_path.exists():
        try:
            with open(cfg_path, encoding="utf-8") as f:
                user_config = yaml.safe_load(f) or {}
        except Exception:
            user_config = {}

    llm = user_config.get("llm", {}) or {}
    providers = llm.get("providers", [])
    if not isinstance(providers, list):
        raise HTTPException(400, "llm.providers 不是数组")

    existing_names = [p.get("name") for p in providers if isinstance(p, dict)]
    new_names = body.names

    # 校验：数量一致 + 无重复 + 无未知
    if len(new_names) != len(existing_names):
        raise HTTPException(
            400,
            f"name 数量不匹配：前端传 {len(new_names)}，实际有 {len(existing_names)}",
        )
    if len(set(new_names)) != len(new_names):
        raise HTTPException(400, "names 含重复")
    existing_set = set(existing_names)
    for n in new_names:
        if n not in existing_set:
            raise HTTPException(400, f"未知 provider name: {n}")

    # 重排：按 new_names 顺序重新组织 providers 列表
    by_name = {p.get("name"): p for p in providers if isinstance(p, dict)}
    reordered = []
    for idx, name in enumerate(new_names):
        p = dict(by_name[name])  # 浅拷贝，避免污染原引用
        p["priority"] = idx
        reordered.append(p)

    llm["providers"] = reordered
    user_config["llm"] = llm

    try:
        # 写盘：providers 是数组，_patch_yaml_file 不支持数组 merge，
        # 因此用 round-trip 写回（保留其他 section 注释/格式不变）。
        # 但为了简单可靠，这里直接重新 dump llm 段（comments 会丢），
        # 上游已有 _patch_yaml_file 处理简单 key 写入。providers 这种复杂列表
        # 必须用全量重写。
        _write_full_yaml(cfg_path, user_config)
    except Exception as e:
        raise HTTPException(500, f"写入配置文件失败: {e}")

    return {
        "ok": True,
        "count": len(reordered),
        "order": [p["name"] for p in reordered],
    }


def _read_user_config(cfg_path: Path) -> dict:
    """读取用户 config.yaml 为 dict（失败时返回空 dict）。"""
    if not cfg_path.exists():
        return {}
    try:
        with open(cfg_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


@router.post("/batch_toggle")
async def batch_toggle(body: BatchToggleRequest):
    """V2：批量启用/禁用 provider。

    行为：
      1. 校验 names 都存在（忽略未知名字并报告）
      2. 修改 providers 列表中对应 name 的 enabled 字段
      3. 同步更新 default（如果默认 provider 被禁用，自动切换为第一个仍 enabled 的）
      4. 写盘

    错误：
      - 400 names 为空
      - 404 所有 name 都不存在
      - 500 写盘失败
    """
    cfg_path = PROJECT_ROOT / "config.yaml"
    user_config = _read_user_config(cfg_path)
    llm = user_config.get("llm", {}) or {}
    providers = llm.get("providers", [])
    if not isinstance(providers, list) or not providers:
        raise HTTPException(400, "当前没有可操作的 provider")

    by_name: dict[str, dict] = {}
    for p in providers:
        if isinstance(p, dict):
            n = p.get("name")
            if n:
                by_name[n] = p

    if not by_name:
        raise HTTPException(400, "当前没有可操作的 provider")

    requested = [n for n in body.names if n in by_name]
    if not requested:
        raise HTTPException(404, "所有 name 都不存在")

    # 修改 enabled
    for n in requested:
        by_name[n]["enabled"] = body.enabled

    # 校验：default 不应被禁用；若被禁用，自动切到第一个仍 enabled 的
    default_name = llm.get("default")
    if default_name and by_name.get(default_name, {}).get("enabled") is False:
        # 找一个仍 enabled 的（按 priority 顺序）
        candidates = sorted(
            [p for p in by_name.values() if p.get("enabled") is True],
            key=lambda p: p.get("priority", 999),
        )
        if candidates:
            new_default = candidates[0].get("name")
            llm["default"] = new_default
            default_name = new_default
        # 若所有都禁用，保留 default 不动（让用户在 UI 上处理）

    # 写回（保持原顺序）
    llm["providers"] = providers
    user_config["llm"] = llm

    try:
        _write_full_yaml(cfg_path, user_config)
    except Exception as e:
        raise HTTPException(500, f"写入配置文件失败: {e}")

    return {
        "ok": True,
        "updated": requested,
        "ignored": [n for n in body.names if n not in by_name],
        "default": default_name,
        "enabled": body.enabled,
    }


@router.post("/batch_delete")
async def batch_delete(body: BatchDeleteRequest):
    """V2：批量删除 provider。

    行为：
      1. 校验 names 都存在（未知名字忽略）
      2. 拒绝删除默认 provider（用户必须先切换默认）
      3. 拒绝删除会清空 providers 列表（即不能删光所有 provider）
      4. 删除后同步更新 default：若 default 被删，切到剩下的第一个 enabled provider
      5. 写盘

    错误：
      - 400 names 为空 / 含默认 / 会清空列表
      - 404 所有 name 都不存在
      - 500 写盘失败
    """
    cfg_path = PROJECT_ROOT / "config.yaml"
    user_config = _read_user_config(cfg_path)
    llm = user_config.get("llm", {}) or {}
    providers = llm.get("providers", [])
    if not isinstance(providers, list) or not providers:
        raise HTTPException(400, "当前没有可操作的 provider")

    by_name: dict[str, dict] = {}
    for p in providers:
        if isinstance(p, dict):
            n = p.get("name")
            if n:
                by_name[n] = p

    if not by_name:
        raise HTTPException(400, "当前没有可操作的 provider")

    requested = [n for n in body.names if n in by_name]
    if not requested:
        raise HTTPException(404, "所有 name 都不存在")

    # 拒绝删除默认 provider
    default_name = llm.get("default")
    if default_name and default_name in requested:
        raise HTTPException(
            400,
            f"默认 Provider「{default_name}」不能直接删除，请先切换默认",
        )

    # 拒绝会清空列表
    remaining_count = len(by_name) - len(requested)
    if remaining_count < 1:
        raise HTTPException(
            400,
            f"至少保留 1 个 provider；当前 {len(by_name)} 个，要删 {len(requested)} 个",
        )

    # 执行删除（保持剩余 provider 的原顺序）
    deleted: list[str] = []
    new_providers = []
    for p in providers:
        n = p.get("name")
        if n in requested:
            deleted.append(n)
        else:
            new_providers.append(p)

    llm["providers"] = new_providers
    user_config["llm"] = llm

    try:
        _write_full_yaml(cfg_path, user_config)
    except Exception as e:
        raise HTTPException(500, f"写入配置文件失败: {e}")

    return {
        "ok": True,
        "deleted": deleted,
        "ignored": [n for n in body.names if n not in by_name],
        "remaining": len(new_providers),
    }


def _write_full_yaml(cfg_path: Path, config: dict) -> None:
    """全量重写 YAML 配置文件（用于 providers 列表等复杂结构的更新）。

    设计权衡：会丢失原始注释，但保证结构正确。生产环境的运维变更应通过
    专用 API（增删 provider）而不是手动改 yaml。
    """
    cfg_path.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


@router.get("/providers")
async def list_providers():
    """列出所有 provider 元数据（无 API Key）"""
    config = load_config()
    llm = config.get("llm", {})
    providers = _get_providers_from_config(llm)
    return {
        "providers": [_provider_to_dict(p) for p in providers],
        "default": llm.get("default") or (providers[0].get("name") if providers else None),
        "count": len(providers),
    }
