#!/usr/bin/env python3
"""
SPA 智能视图路由（Sprint 6.0）

利用 HTMX 的 HX-Request Header 实现：
  - HTMX 请求 → 仅返回片段（无外壳）
  - 浏览器直接访问 → 返回完整页面（带 base.html 外壳）

路由设计：
  GET /view/pipelines    — 任务列表（SPA 片段/完整页）
  GET /view/knowledge    — 知识库管理（SPA 片段/完整页）
  GET /view/results/{id} — 结果预览（SPA 片段/完整页）
  GET /view/pipeline/{id} — Pipeline 详情（SPA 片段/完整页）
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from pathlib import Path

from web.services.task_manager import get_task_manager

router = APIRouter(prefix="/view", tags=["views"])


def _get_templates():
    """延迟导入 app.py 的 templates 实例，避免循环导入。

    app.py 在模块加载时 include_router(views.router)，此时 views 已导入完毕，
    但 app.py 中的 `templates = Jinja2Templates(...)` 还未执行。
    所以不能在 views.py 模块顶部直接 `from web.app import templates`。
    """
    from web.app import templates
    return templates


def _is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _render(request: Request, template_name: str, ctx: dict, htmx_fragment: str | None = None):
    """智能渲染：HTMX 请求返回片段，否则返回完整页面。"""
    templates = _get_templates()
    full_ctx = {"request": request, **ctx}
    if _is_htmx(request) and htmx_fragment:
        fragment_path = (
            Path(__file__).resolve().parents[1] / "templates" / htmx_fragment
        )
        if fragment_path.exists():
            return templates.TemplateResponse(request, htmx_fragment, ctx)
    return templates.TemplateResponse(request, template_name, full_ctx)


# ─── 任务列表 ───

@router.get("/pipelines", response_class=HTMLResponse)
async def view_pipelines(request: Request):
    """任务列表视图（SPA 片段 / 完整页）"""
    tm = get_task_manager()
    running_count = tm.get_running_count()
    ctx = {
        "title": "Pipeline 列表",
        "running_count": running_count,
    }
    return _render(request, "pipelines.html", ctx, htmx_fragment="_pipelines_list.html")


# ─── 知识库管理 ───

@router.get("/knowledge", response_class=HTMLResponse)
async def view_knowledge(request: Request):
    """知识库管理视图（含动态配置表单）"""
    ctx = {"title": "知识库管理"}
    return _render(request, "knowledge.html", ctx, htmx_fragment="_knowledge_main.html")


# ─── Pipeline 详情 ───

@router.get("/pipeline/{pipeline_id}", response_class=HTMLResponse)
async def view_pipeline_detail(request: Request, pipeline_id: str):
    """Pipeline 进度详情"""
    ctx = {"pipeline_id": pipeline_id, "title": f"Pipeline {pipeline_id[:8]}"}
    return _render(request, "pipeline.html", ctx, htmx_fragment="_pipeline_detail.html")


# ─── 结果预览 ───

@router.get("/results/{pipeline_id}", response_class=HTMLResponse)
async def view_results(request: Request, pipeline_id: str):
    """结果预览"""
    ctx = {"pipeline_id": pipeline_id, "title": "结果预览"}
    return _render(request, "results.html", ctx, htmx_fragment="_results_main.html")
