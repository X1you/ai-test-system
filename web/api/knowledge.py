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
from web.middleware.auth import require_user

router = APIRouter(prefix="/api/kb", tags=["knowledge"])

KB_SCRIPT = Path(__file__).resolve().parents[2] / "core" / "kb" / "kb_manager_mcp.py"


@router.get("/status")
async def kb_status(user: dict = Depends(require_user)):
    """知识库统计（带 60s 缓存，单例复用避免每次 fork 子进程）。"""
    config = load_config()
    kb_config = config.get("knowledge_base", {})

    if not kb_config.get("enabled", False):
        return {"enabled": False, "total": 0, "categories": {}}

    # 走缓存服务（单例 + TTL 缓存，单例不可用时内部回退 subprocess）
    from web.services.kb_cache import get_status
    return get_status()


@router.get("/search")
async def kb_search(q: str = Query(..., description="搜索关键词"), user: dict = Depends(require_user)):
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
async def kb_import(file: UploadFile = File(...), user: dict = Depends(require_user)):
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
    user: dict = Depends(require_user),
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
