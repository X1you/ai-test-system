#!/usr/bin/env python3
"""
Pipeline API 路由

Endpoints:
  POST /api/pipeline/start          — 上传需求 + 启动
  GET  /api/pipeline/{id}/progress  — 获取进度（JSON / HTMX 片段）
  POST /api/pipeline/{id}/resume    — 断点继续
  GET  /api/pipeline/list           — 任务列表
"""

import os
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from core.config_loader import load_config
from core.utils import safe_join_path
from web.services.task_manager import get_task_manager

# 模板实例化（复用，避免重复创建）
_templates = Jinja2Templates(directory="web/templates")

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

# 上传目录（使用绝对路径）
UPLOAD_DIR = Path(__file__).resolve().parents[1] / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 允许的文件后缀
ALLOWED_EXTENSIONS = {".md", ".txt"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/start")
async def start_pipeline(
    file: UploadFile = File(...),
    mode: str = Form("semi"),
    dimensions: str = Form("basic"),
    formats: str = Form("excel"),
):
    """上传需求文档 + 启动 Pipeline"""
    # 校验文件后缀
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"仅支持 {', '.join(ALLOWED_EXTENSIONS)} 文件")

    # 读取并校验大小
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, "文件过大（>10MB）")

    # 检查并发限制
    tm = get_task_manager()
    if tm.is_full():
        raise HTTPException(429, "并发任务已达上限，请等待现有任务完成")

    # 保存上传文件（安全文件名）
    import re
    import uuid

    upload_id = uuid.uuid4().hex[:8]
    safe_name = re.sub(r'[^\w\-_. ]', '_', file.filename or "upload.md")
    upload_path = UPLOAD_DIR / f"{upload_id}_{safe_name}"
    upload_path.write_bytes(content)

    # 加载配置并创建任务
    config = load_config()
    task = tm.create_task(
        config=config,
        requirements_path=str(upload_path),
        mode=mode,
        dimensions=dimensions,
        formats=formats,
    )

    return JSONResponse(
        status_code=201,
        content={
            "pipeline_id": task.pipeline_id,
            "redirect": f"/pipeline/{task.pipeline_id}",
            "status": "running",
        },
    )


@router.get("/{pipeline_id}/progress")
async def get_progress(pipeline_id: str, request: Request):
    """获取进度

    如果请求头 HX-Request: true（HTMX 请求），返回 HTML 片段。
    否则返回 JSON。
    """
    tm = get_task_manager()
    task = tm.get_task(pipeline_id)
    if not task:
        raise HTTPException(404, "Pipeline 不存在")

    progress = task.get_progress()

    # 检查是否为 HTMX 请求
    is_htmx = request.headers.get("HX-Request") == "true"

    if is_htmx:
        # 返回 HTML 片段
        html = _templates.TemplateResponse(
            request,
            "pipeline_progress.html",
            {"progress": progress},
        )
        # 如果已完成/暂停/错误，在头部标记停止轮询
        status = progress["status"]
        if status in ("done", "paused", "error", "cancelled"):
            event_name = {
                "done": "pipeline-complete",
                "paused": "pipeline-paused",
                "error": "pipeline-error",
                "cancelled": "pipeline-cancelled",
            }.get(status, "pipeline-complete")
            html.headers["HX-Trigger"] = event_name
        return html

    return progress


@router.get("/{pipeline_id}/status")
async def get_status(pipeline_id: str):
    """详细状态"""
    tm = get_task_manager()
    task = tm.get_task(pipeline_id)
    if not task:
        raise HTTPException(404, "Pipeline 不存在")
    return task.get_progress()


@router.get("/list")
async def list_pipelines(page: int = 1, page_size: int = 20):
    """任务列表（支持分页）"""
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 20
    tm = get_task_manager()
    all_tasks = tm.list_tasks()
    total = len(all_tasks)
    start = (page - 1) * page_size
    end = start + page_size
    items = all_tasks[start:end]
    pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    return {
        "items": items,
        "pipelines": items,  # 向后兼容：旧前端/测试依赖此字段
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


@router.post("/{pipeline_id}/cancel")
async def cancel_pipeline(pipeline_id: str):
    """取消 Pipeline"""
    tm = get_task_manager()
    task = tm.get_task(pipeline_id)
    if not task:
        raise HTTPException(404, "Pipeline 不存在")

    if task.status not in ("running", "pending"):
        raise HTTPException(400, f"当前状态不允许取消: {task.status}")

    task.cancel()
    return {"pipeline_id": pipeline_id, "status": "cancelled"}


@router.post("/{pipeline_id}/resume")
async def resume_pipeline(pipeline_id: str, file: UploadFile = None):
    """断点继续（上传已执行结果的 Excel → 继续生成报告）

    如果 file 有提供，覆盖 output 目录中的 testcases.xlsx。
    """
    tm = get_task_manager()
    task = tm.get_task(pipeline_id)
    if not task:
        raise HTTPException(404, "Pipeline 不存在")

    if task.status not in ("paused", "done"):
        raise HTTPException(400, f"当前状态不允许继续: {task.status}")

    # 如果有新上传的 Excel，覆盖旧文件
    if file and file.filename and file.filename.endswith(".xlsx"):
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(400, "文件过大（>10MB）")
        target_path = Path(task.output_dir) / "testcases.xlsx"
        target_path.write_bytes(content)
        task._on_log("OK", f"已接收执行结果文件: {file.filename}")

    # 后台继续执行（从 Step 6 开始）
    task.resume_background()

    return {
        "pipeline_id": pipeline_id,
        "status": "running",
        "redirect": f"/pipeline/{pipeline_id}",
    }


@router.get("/{pipeline_id}/artifacts")
async def list_artifacts(pipeline_id: str):
    """产物列表"""
    tm = get_task_manager()
    task = tm.get_task(pipeline_id)
    if not task:
        raise HTTPException(404, "Pipeline 不存在")

    output_dir = Path(task.output_dir)
    artifacts = []

    # 产物文件 → 友好名称映射
    artifact_names = {
        "requirements_analysis.md": "需求分析",
        "clarification_needed.md": "待确认清单",
        "knowledge-context.md": "知识库上下文",
        "testpoints.md": "测试点清单",
        "testcases.xlsx": "测试用例",
        "testcases.xmind": "XMind 用例",
        "test_case_review_report.md": "评审报告",
        "test_report.md": "测试报告",
    }

    for fname, display_name in artifact_names.items():
        fpath = output_dir / fname
        if fpath.exists():
            size = fpath.stat().st_size
            ftype = (
                "markdown"
                if fname.endswith(".md")
                else ("excel" if fname.endswith(".xlsx") else "xmind")
            )
            artifacts.append(
                {
                    "name": fname,
                    "display_name": display_name,
                    "size": size,
                    "type": ftype,
                }
            )

    return {"pipeline_id": pipeline_id, "artifacts": artifacts}


@router.get("/{pipeline_id}/artifacts/{name}")
async def download_artifact(pipeline_id: str, name: str):
    """下载产物"""
    tm = get_task_manager()
    task = tm.get_task(pipeline_id)
    if not task:
        raise HTTPException(404, "Pipeline 不存在")

    # 安全校验：防止路径穿越
    try:
        file_path = safe_join_path(task.output_dir, name)
    except ValueError:
        raise HTTPException(400, "非法文件名")

    if not file_path.exists():
        raise HTTPException(404, "文件不存在")

    return FileResponse(
        str(file_path),
        filename=Path(name).name,
        media_type="application/octet-stream",
    )


@router.get("/{pipeline_id}/preview/{name}")
async def preview_artifact(pipeline_id: str, name: str):
    """预览产物（Markdown 渲染 / Excel 表格）"""
    tm = get_task_manager()
    task = tm.get_task(pipeline_id)
    if not task:
        raise HTTPException(404, "Pipeline 不存在")

    # 安全校验：防止路径穿越
    try:
        file_path = safe_join_path(task.output_dir, name)
    except ValueError:
        raise HTTPException(400, "非法文件名")

    if not file_path.exists():
        raise HTTPException(404, "文件不存在")

    if name.endswith(".md"):
        content = file_path.read_text(encoding="utf-8")
        # 简单 Markdown → HTML（后续可加 markdown 库）
        try:
            import markdown as md

            html = md.markdown(content, extensions=["tables", "fenced_code"])
        except ImportError:
            # fallback: HTML-escape + <pre> (防止 XSS)
            import html as html_module

            escaped = html_module.escape(content)
            html = f"<pre>{escaped}</pre>"
        return {"type": "markdown", "html": html}

    elif name.endswith(".xlsx"):
        # Excel 预览：前 50 行
        try:
            from openpyxl import load_workbook

            wb = load_workbook(str(file_path), data_only=True)
            ws = wb.active
            if ws is None:
                wb.close()
                raise HTTPException(500, "Excel 无活动工作表")
            rows = []
            for i, row in enumerate(ws.iter_rows(min_row=1, values_only=True)):
                if i >= 50:
                    break
                rows.append([str(c or "")[:100] for c in row])
            wb.close()
            return {"type": "excel", "rows": rows}
        except Exception as e:
            raise HTTPException(500, f"Excel 读取失败: {e}")

    else:
        raise HTTPException(400, "不支持预览此格式")
