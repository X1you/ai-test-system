#!/usr/bin/env python3
"""
知识库 API 路由（Sprint 6.1：纯 JSON API，移除 prefix 与 Form）

Endpoints（前缀由 app.py 统一挂载为 /api/v1/knowledge）:
  GET  /status             — 知识库统计
  GET  /search             — 搜索
  POST /import             — 导入 Excel 用例回灌
  POST /add                — 添加单条知识
  POST /update_config      — 更新知识库配置（热切换）
  GET  /current_config     — 获取当前生效配置
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

from core.config_loader import load_config

# ★ Sprint 6.1：移除 prefix（由 app.py 统一挂载 /api/v1/knowledge）
router = APIRouter(tags=["knowledge"])

KB_SCRIPT = Path(__file__).resolve().parents[2] / "core" / "kb" / "kb_manager_mcp.py"


@router.get("/status")
async def kb_status():
    """知识库统计（带 60s 缓存，单例复用避免每次 fork 子进程）。"""
    config = load_config()
    kb_config = config.get("knowledge_base", {})

    if not kb_config.get("enabled", False):
        return {"enabled": False, "total": 0, "categories": {}, "message": "知识库未启用"}

    vault_path = kb_config.get("vault_path", "")
    if not vault_path or not Path(vault_path).exists():
        return {"enabled": True, "total": 0, "categories": {}, "message": "Vault 路径不存在"}

    if not KB_SCRIPT.exists():
        return {"enabled": True, "total": 0, "categories": {}, "message": "KB 脚本缺失"}

    # 复用缓存（避免每次 fork）
    try:
        from web.services.kb_cache import get_status
        return get_status()
    except ImportError:
        pass

    # 兜底：直接 fork
    try:
        result = subprocess.run(
            [sys.executable, str(KB_SCRIPT), "status", "--json"],
            capture_output=True, text=True, timeout=30,
            env={**__import__("os").environ, "OBSIDIAN_VAULT": vault_path},
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception as e:
        return {"enabled": True, "error": str(e)[:200]}

    return {"enabled": True, "total": 0, "categories": {}}


@router.get("/search")
async def kb_search(q: str = Query(..., description="搜索关键词")):
    """搜索知识库"""
    config = load_config()
    kb_config = config.get("knowledge_base", {})
    if not kb_config.get("enabled", False):
        return {"query": q, "results": [], "total": 0, "message": "知识库未启用"}

    vault_path = kb_config.get("vault_path", "")

    try:
        result = subprocess.run(
            [sys.executable, str(KB_SCRIPT), "search", q, "--json", "--limit", "20"],
            capture_output=True, text=True, timeout=30,
            env={**__import__("os").environ, "OBSIDIAN_VAULT": vault_path},
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            data["query"] = q
            return data
    except Exception as e:
        return {"query": q, "results": [], "total": 0, "error": str(e)[:200]}

    return {"query": q, "results": [], "total": 0}


@router.post("/import")
async def kb_import(file: UploadFile = File(...)):
    """从 Excel 文件导入测试用例回灌知识库"""
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "仅支持 .xlsx/.xls 文件")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "文件超过 10MB 上限")

    # 写入临时文件供脚本读取
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [sys.executable, str(KB_SCRIPT), "import", tmp_path, "--category", "historical-cases"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                return {"ok": True, "imported": data.get("imported", 0), "message": "导入成功"}
            except json.JSONDecodeError:
                return {"ok": True, "imported": 0, "message": "导入完成（数量解析失败）"}
        return {"ok": False, "message": result.stderr[:500] or "导入失败"}
    except Exception as e:
        return {"ok": False, "message": str(e)[:200]}
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@router.post("/add")
async def kb_add(
    title: str = Form(...),
    category: str = Form(...),
    content: str = Form(...),
    tags: str = Form(""),
    module: str = Form(""),
):
    """添加单条知识条目"""
    cmd = [
        sys.executable, str(KB_SCRIPT), "add",
        "--title", title,
        "--category", category,
        "--content", content,
        "--tags", tags,
        "--module", module,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            try:
                from web.services.kb_cache import invalidate_all
                invalidate_all()
            except ImportError:
                pass
            return {"ok": True, "message": "添加成功"}
        return {"ok": False, "message": result.stderr[:500] or "添加失败"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


# ═══════════════════════════════════════════════════════════════
# Sprint 6.1: 动态知识库配置（纯 JSON API，使用 Pydantic BaseModel）
# ═══════════════════════════════════════════════════════════════


class KBConfigRequest(BaseModel):
    """知识库配置请求（JSON Body）"""
    provider_type: str = "mcp_filesystem"
    connection_url: str = ""
    auth_token: str | None = None
    vault_path: str = ""


@router.post("/update_config")
async def update_kb_config(req: KBConfigRequest):
    """更新知识库配置（热切换）

    流程：
      1. provider_type 校验
      2. 连通性测试（requests.get 或 Path.exists）
      3. DB 写入（旧配置置 inactive）
      4. 立即热切换（get_dynamic_kb_manager().reload()）
    """
    import logging
    import requests

    logger = logging.getLogger("ai-test-system")

    # 1. 校验
    valid_providers = {"obsidian_api", "mcp_filesystem"}
    if req.provider_type not in valid_providers:
        return {
            "status": "error",
            "message": f"provider_type 必须是 {valid_providers} 之一",
        }

    # 2. 连通性测试
    try:
        if req.provider_type == "obsidian_api" and req.connection_url:
            headers = {"Authorization": f"Bearer {req.auth_token}"} if req.auth_token else {}
            resp = requests.get(
                req.connection_url.rstrip("/") + "/health",
                headers=headers, timeout=5, verify=False,
            )
            # 只要能连上就算通过（401 也算）
            connectivity_msg = f"连通性测试通过（HTTP {resp.status_code}）"
        elif req.provider_type == "mcp_filesystem":
            if not req.vault_path or not Path(req.vault_path).exists():
                return {
                    "status": "error",
                    "message": f"mcp_filesystem 要求 vault_path 存在: {req.vault_path}",
                }
            md_count = sum(1 for _ in Path(req.vault_path).rglob("*.md"))
            connectivity_msg = f"连通性测试通过（Vault 含 {md_count} 个 .md 文件）"
        else:
            connectivity_msg = "跳过连通性测试"
    except Exception as e:
        return {"status": "error", "message": f"连接失败: {str(e)}"}

    # 3. 写入 DB
    try:
        from datetime import datetime
        from db.models import KBConfig
        from db.session import session_scope

        with session_scope() as db:
            db.query(KBConfig).filter(KBConfig.is_active == True).update(  # noqa: E712
                {KBConfig.is_active: False}
            )
            new_cfg = KBConfig(
                provider_type=req.provider_type,
                connection_url=req.connection_url or None,
                auth_token=req.auth_token or None,
                vault_path=req.vault_path or None,
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(new_cfg)
            db.commit()
            cfg_id = new_cfg.id

        logger.info("KB 配置更新: id=%s provider=%s", cfg_id, req.provider_type)
    except Exception as e:
        return {"status": "error", "message": f"DB 写入失败: {str(e)}"}

    # 4. 热切换
    try:
        from core.kb.dynamic_kb_manager import get_dynamic_kb_manager
        get_dynamic_kb_manager().reload()
    except Exception as e:
        logger.error("KB reload 失败: %s", e)

    return {
        "status": "success",
        "message": f"配置已生效并热重载。{connectivity_msg}",
        "config_id": cfg_id,
    }


@router.get("/current_config")
async def get_current_kb_config():
    """获取当前生效的知识库配置（脱敏 token）"""
    try:
        from db.models import KBConfig
        from db.session import session_scope

        with session_scope() as db:
            cfg = (
                db.query(KBConfig)
                .filter(KBConfig.is_active == True)  # noqa: E712
                .order_by(KBConfig.updated_at.desc())
                .first()
            )
            if cfg is None:
                return {"configured": False, "message": "未配置（Dummy 模式）"}
            return {
                "configured": True,
                "config_id": cfg.id,
                "provider_type": cfg.provider_type,
                "connection_url": cfg.connection_url,
                "vault_path": cfg.vault_path,
                "auth_token_masked": (
                    cfg.auth_token[:4] + "****" + cfg.auth_token[-4:]
                    if cfg.auth_token and len(cfg.auth_token) > 8
                    else "****"
                ),
                "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
            }
    except Exception as e:
        return {"configured": False, "error": str(e)}
