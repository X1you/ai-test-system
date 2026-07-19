#!/usr/bin/env python3
"""
知识库 API 路由

Endpoints:
  GET  /api/kb/status   — 知识库统计
  GET  /api/kb/search   — 搜索
  POST /api/kb/import   — 导入 Excel 用例回灌知识库
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from core.config_loader import load_config

router = APIRouter(prefix="/api/kb", tags=["knowledge"])

KB_SCRIPT = Path(__file__).resolve().parents[2] / "core" / "kb" / "kb_manager_mcp.py"


@router.get("/status")
async def kb_status():
    """知识库统计（带 60s 缓存，单例复用避免每次 fork 子进程）。"""
    config = load_config()
    kb_config = config.get("knowledge_base", {})

    if not kb_config.get("enabled", False):
        return {"enabled": False, "total": 0, "categories": {}}

    # 走缓存服务（单例 + TTL 缓存，单例不可用时内部回退 subprocess）
    from web.services.kb_cache import get_status
    return get_status()


@router.get("/search")
async def kb_search(q: str = Query(..., description="搜索关键词")):
    """搜索知识库（按 query 缓存 30s）。"""
    config = load_config()
    kb_config = config.get("knowledge_base", {})

    if not kb_config.get("enabled", False):
        return {"query": q, "total": 0, "results": [], "error": "知识库未启用"}

    # 走缓存服务
    from web.services.kb_cache import search as kb_search_cached
    data = kb_search_cached(q, limit=20)

    # 简化输出（与原逻辑一致）
    results = []
    for item in data[:20]:
        results.append({
            "title": item.get("title", ""),
            "category": item.get("category", ""),
            "module": item.get("module", ""),
            "preview": item.get("content", "")[:200],
            "filepath": item.get("filepath", ""),
        })
    return {"query": q, "total": len(results), "results": results}


@router.post("/import")
async def kb_import(file: UploadFile = File(...)):
    """导入 Excel 用例回灌知识库"""
    # 校验文件类型
    if not file.filename or not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(400, "仅支持 .xlsx / .xls 格式")

    config = load_config()
    kb_config = config.get("knowledge_base", {})

    if not kb_config.get("enabled", False):
        raise HTTPException(400, "知识库未启用")

    if not KB_SCRIPT.exists():
        raise HTTPException(500, "知识库脚本不存在")

    # 保存上传文件到临时目录
    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [sys.executable, str(KB_SCRIPT), "ingest", tmp_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            # 写入成功 → 失效缓存，让下次 status/search 看到新数据
            from web.services.kb_cache import invalidate_all
            invalidate_all()
            return {
                "ok": True,
                "imported": data.get("imported", 0),
                "message": data.get("message", "导入成功"),
            }
        return {
            "ok": False,
            "imported": 0,
            "message": result.stderr[:500] or "导入失败",
        }
    except json.JSONDecodeError:
        return {"ok": False, "imported": 0, "message": result.stdout[:500] or "响应解析失败"}
    except Exception as e:
        return {"ok": False, "imported": 0, "message": str(e)}
    finally:
        # 清理临时文件
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass


@router.post("/add")
async def kb_add(
    title: str = Form(...),
    content: str = Form(...),
    category: str = Form(...),
    module: str = Form(""),
    tags: str = Form(""),
    severity: str = Form(""),
):
    """添加单条知识条目"""
    config = load_config()
    kb_config = config.get("knowledge_base", {})

    if not kb_config.get("enabled", False):
        raise HTTPException(400, "知识库未启用")

    if not KB_SCRIPT.exists():
        raise HTTPException(500, "知识库脚本不存在")

    valid_categories = [
        "business-rules", "historical-cases", "pitfalls",
        "templates", "data-dictionary", "business-specs", "team-standards",
    ]
    if category not in valid_categories:
        raise HTTPException(400, f"无效分类: {category}")

    cmd = [
        sys.executable, str(KB_SCRIPT), "add",
        "--title", title,
        "--content", content,
        "--category", category,
    ]
    if module:
        cmd += ["--module", module]
    if tags:
        cmd += ["--tags", tags]
    if severity and category == "pitfalls":
        cmd += ["--severity", severity]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            # 写入成功 → 失效缓存
            from web.services.kb_cache import invalidate_all
            invalidate_all()
            return {"ok": True, "message": "添加成功"}
        return {"ok": False, "message": result.stderr[:500] or "添加失败"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


# ═══════════════════════════════════════════════════════════════
# Sprint 6.0: 动态配置管理
# ═══════════════════════════════════════════════════════════════


@router.post("/update_config")
async def update_kb_config(
    provider_type: str = Form(..., description="obsidian_api / mcp_filesystem"),
    connection_url: str = Form("", description="Obsidian API base_url 或 MCP 连接 URL"),
    auth_token: str = Form("", description="Bearer token 或 API key"),
    vault_path: str = Form("", description="本地 Vault 路径（mcp_filesystem 必填）"),
):
    """更新知识库配置（热切换）

    流程：
      1. 轻量连通性测试（requests.get/Path.exists）
      2. 校验通过 → DB 写入（旧配置置 inactive）
      3. 立即调用 kb_manager.reload() 热切换
    """
    import logging

    logger = logging.getLogger("ai-test-system")

    # ─── 1. 校验 provider_type ───
    valid_providers = {"obsidian_api", "mcp_filesystem"}
    if provider_type not in valid_providers:
        raise HTTPException(
            400,
            f"provider_type 必须是 {valid_providers} 之一，实际: {provider_type}",
        )

    # ─── 2. mcp_filesystem 必填 vault_path ───
    if provider_type == "mcp_filesystem":
        if not vault_path or not Path(vault_path).exists():
            raise HTTPException(
                400,
                f"mcp_filesystem provider 要求 vault_path 存在: {vault_path}",
            )

    # ─── 3. 轻量连通性测试 ───
    connectivity_msg = ""
    try:
        if provider_type == "obsidian_api" and connection_url:
            import requests

            headers = {}
            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"
            # 用短 timeout 探测，SSL verify=False 容错自签证书
            resp = requests.get(
                connection_url.rstrip("/"),
                headers=headers,
                timeout=5,
                verify=False,
            )
            # Obsidian Local REST API 可能返回 200 或 401（无 token 时）
            # 只要连上就算通过
            connectivity_msg = f"连通性测试通过（HTTP {resp.status_code}）"
        elif provider_type == "mcp_filesystem":
            # vault_path 已在上面验证
            md_count = sum(1 for _ in Path(vault_path).rglob("*.md"))
            connectivity_msg = f"连通性测试通过（Vault 含 {md_count} 个 .md 文件）"
    except Exception as e:
        raise HTTPException(
            400, f"连通性测试失败: {e}（请检查 URL/路径/Token 是否正确）"
        )

    # ─── 4. 写入 DB（旧配置置 inactive）───
    try:
        from datetime import datetime

        from db.models import KBConfig
        from db.session import session_scope

        with session_scope() as session:
            # 旧配置全部置 inactive
            session.query(KBConfig).filter(
                KBConfig.is_active == True  # noqa: E712
            ).update({KBConfig.is_active: False})

            # 插入新配置
            new_cfg = KBConfig(
                provider_type=provider_type,
                connection_url=connection_url or None,
                auth_token=auth_token or None,
                vault_path=vault_path or None,
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(new_cfg)
            session.commit()
            cfg_id = new_cfg.id

        logger.info(
            "KB 配置已更新: id=%s provider=%s url=%s vault=%s",
            cfg_id, provider_type, connection_url, vault_path,
        )
    except Exception as e:
        raise HTTPException(500, f"DB 写入失败: {e}")

    # ─── 5. 立即热切换 ───
    try:
        from core.kb.dynamic_kb_manager import get_dynamic_kb_manager

        ok = get_dynamic_kb_manager().reload()
        if not ok:
            logger.warning("KB 配置已写入但 reload 返回 False（可能 provider 不支持）")
    except Exception as e:
        logger.error("KB reload 失败（配置已写入 DB）: %s", e)

    return {
        "ok": True,
        "message": f"配置已保存并热切换。{connectivity_msg}",
        "config_id": cfg_id,
        "provider_type": provider_type,
    }


@router.get("/current_config")
async def get_current_kb_config():
    """获取当前生效的知识库配置（脱敏 token）"""
    try:
        from db.models import KBConfig
        from db.session import session_scope

        with session_scope() as session:
            cfg = (
                session.query(KBConfig)
                .filter(KBConfig.is_active == True)  # noqa: E712
                .order_by(KBConfig.updated_at.desc())
                .first()
            )
            if cfg is None:
                return {
                    "configured": False,
                    "message": "未配置（Dummy 模式）",
                }
            return {
                "configured": True,
                "config_id": cfg.id,
                "provider_type": cfg.provider_type,
                "connection_url": cfg.connection_url,
                "vault_path": cfg.vault_path,
                "auth_token_masked": (
                    (cfg.auth_token[:4] + "****" + cfg.auth_token[-4:])
                    if cfg.auth_token and len(cfg.auth_token) > 8
                    else "****"
                ),
                "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
            }
    except Exception as e:
        return {"configured": False, "error": str(e)}
