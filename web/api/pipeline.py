#!/usr/bin/env python3
"""
Pipeline API 路由。

Endpoints:
  POST /api/pipeline/start              — 上传需求 + 启动
  GET  /api/pipeline/{id}/progress      — 获取进度（JSON / HTMX 片段）
  GET  /api/pipeline/{id}/status        — 详细状态
  GET  /api/pipeline/list               — 任务列表（分页 + 搜索）
  POST /api/pipeline/{id}/cancel        — 取消
  POST /api/pipeline/{id}/resume        — 断点继续
  GET  /api/pipeline/{id}/artifacts     — 产物列表
  GET  /api/pipeline/{id}/artifacts/{name} — 下载产物
  GET  /api/pipeline/{id}/preview/{name}   — 预览产物
"""

import re
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from core.config_loader import load_config
from core.utils import safe_join_path
from web.services.task_manager import get_task_manager

# ─── 常量 ───

# 模板实例化（复用，避免重复创建）
_templates = Jinja2Templates(directory="web/templates")

# 上传目录（使用绝对路径）
UPLOAD_DIR = Path(__file__).resolve().parents[1] / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 允许的需求文档后缀
ALLOWED_EXTENSIONS = {".md", ".txt"}

# 上传文件大小上限（字节）— 需求文档与执行结果共用
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Excel 预览最大行数
EXCEL_PREVIEW_MAX_ROWS = 50
# Excel 单元格预览最大字符数
EXCEL_CELL_MAX_CHARS = 100

# 终态 → HTMX 事件名映射（完成后触发前端停止轮询）
_TERMINAL_EVENTS: dict[str, str] = {
    "done": "pipeline-complete",
    "paused": "pipeline-paused",
    "error": "pipeline-error",
    "cancelled": "pipeline-cancelled",
}

# 产物文件 → 友好展示名映射
_ARTIFACT_NAMES: dict[str, str] = {
    "requirements_analysis.md": "需求分析",
    "clarification_needed.md": "待确认清单",
    "knowledge-context.md": "知识库上下文",
    "testpoints.md": "测试点清单",
    "testcases.xlsx": "测试用例",
    "testcases.xmind": "XMind 用例",
    "test_case_review_report.md": "评审报告",
    "test_report.md": "测试报告",
}

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


# ─── 辅助函数 ───


def _require_task(pipeline_id: str):
    """获取任务，不存在时抛 404。

    消除各 endpoint 中重复的 get_task + HTTPException(404) 样板。
    """
    tm = get_task_manager()
    task = tm.get_task(pipeline_id)
    if not task:
        raise HTTPException(404, "Pipeline 不存在")
    return task


def _detect_file_type(name: str) -> str:
    """根据文件后缀推断展示类型。"""
    if name.endswith(".md"):
        return "markdown"
    if name.endswith(".xlsx"):
        return "excel"
    return "xmind"


# ─── 路由 ───


@router.post("/start")
async def start_pipeline(
    file: UploadFile = File(...),
    mode: str = Form("semi"),
    dimensions: str = Form("basic"),
    formats: str = Form("excel"),
):
    """上传需求文档 + 启动 Pipeline。"""
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

    # 保存上传文件（安全文件名：仅保留 \w \- _ . 和空格）
    upload_id = uuid.uuid4().hex[:8]
    safe_name = re.sub(r"[^\w\-_. ]", "_", file.filename or "upload.md")
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
    """获取进度。

    如果请求头 HX-Request: true（HTMX 请求），返回 HTML 片段；
    否则返回 JSON。
    """
    task = _require_task(pipeline_id)
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
        # 终态时在响应头标记触发事件（前端据此停止轮询）
        status = progress["status"]
        event_name = _TERMINAL_EVENTS.get(status, "pipeline-complete")
        html.headers["HX-Trigger"] = event_name
        return html

    return progress


@router.get("/{pipeline_id}/status")
async def get_status(pipeline_id: str):
    """详细状态。"""
    task = _require_task(pipeline_id)
    return task.get_progress()


@router.get("/list")
async def list_pipelines(
    page: int = 1,
    page_size: int = 20,
    keyword: str = "",
    status: str = "",
):
    """任务列表（支持分页 + 搜索过滤）。

    - keyword: 模糊匹配 pipeline_id 或 requirements 文件名
    - status: 精确状态过滤（running/pending/done/error/paused/cancelled）
    """
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 20

    tm = get_task_manager()
    all_tasks = tm.list_tasks()

    # —— 统计仪表盘始终反映全量任务（不受过滤/分页影响）——
    s_running = s_done = 0
    for t in all_tasks:
        st0 = t.get("status", "")
        if st0 in ("running", "pending"):
            s_running += 1
        elif st0 == "done":
            s_done += 1
    all_stats = {
        "total": len(all_tasks),
        "running": s_running,
        "done": s_done,
        "other": len(all_tasks) - s_running - s_done,
    }

    # —— 搜索过滤 ——
    kw = (keyword or "").strip().lower()
    st = (status or "").strip().lower()
    if kw:
        all_tasks = [
            t
            for t in all_tasks
            if kw in t.get("pipeline_id", "").lower()
            or kw in t.get("requirements", "").lower()
        ]
    if st:
        all_tasks = [t for t in all_tasks if t.get("status", "").lower() == st]

    # —— 分页 ——
    total = len(all_tasks)
    start = (page - 1) * page_size
    items = all_tasks[start : start + page_size]
    pages = (total + page_size - 1) // page_size if page_size > 0 else 0

    return {
        "items": items,
        "pipelines": items,  # 向后兼容
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
        "keyword": keyword or "",
        "status": status or "",
        "all_stats": all_stats,
    }


@router.post("/{pipeline_id}/cancel")
async def cancel_pipeline(pipeline_id: str):
    """取消 Pipeline。"""
    task = _require_task(pipeline_id)

    if task.status not in ("running", "pending"):
        raise HTTPException(400, f"当前状态不允许取消: {task.status}")

    task.cancel()
    return {"pipeline_id": pipeline_id, "status": "cancelled"}


@router.post("/{pipeline_id}/resume")
async def resume_pipeline(pipeline_id: str, file: UploadFile = None):
    """断点继续（可上传已执行结果的 Excel 覆盖 output 目录中的 testcases.xlsx）。"""
    task = _require_task(pipeline_id)

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
    """产物列表。"""
    task = _require_task(pipeline_id)
    output_dir = Path(task.output_dir)

    artifacts = []
    for fname, display_name in _ARTIFACT_NAMES.items():
        fpath = output_dir / fname
        if fpath.exists():
            artifacts.append(
                {
                    "name": fname,
                    "display_name": display_name,
                    "size": fpath.stat().st_size,
                    "type": _detect_file_type(fname),
                }
            )

    return {"pipeline_id": pipeline_id, "artifacts": artifacts}


@router.get("/{pipeline_id}/artifacts/{name}")
async def download_artifact(pipeline_id: str, name: str):
    """下载产物。"""
    task = _require_task(pipeline_id)

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
    """预览产物（Markdown 渲染 / Excel 表格）。"""
    task = _require_task(pipeline_id)

    # 安全校验：防止路径穿越
    try:
        file_path = safe_join_path(task.output_dir, name)
    except ValueError:
        raise HTTPException(400, "非法文件名")

    if not file_path.exists():
        raise HTTPException(404, "文件不存在")

    if name.endswith(".md"):
        return _preview_markdown(file_path)

    if name.endswith(".xlsx"):
        return _preview_excel(file_path)

    raise HTTPException(400, "不支持预览此格式")


# ─── 预览内部实现 ───


def _preview_markdown(file_path: Path) -> dict:
    """渲染 Markdown 为 HTML（优先用 markdown 库，缺失时转义兜底）。"""
    content = file_path.read_text(encoding="utf-8")
    try:
        import markdown as md

        html = md.markdown(content, extensions=["tables", "fenced_code"])
    except ImportError:
        # fallback: HTML-escape + <pre>（防止 XSS）
        import html as html_module

        escaped = html_module.escape(content)
        html = f"<pre>{escaped}</pre>"
    return {"type": "markdown", "html": html}


def _preview_excel(file_path: Path) -> dict:
    """读取 Excel 前 N 行为二维数组返回。"""
    try:
        from openpyxl import load_workbook

        wb = load_workbook(str(file_path), data_only=True)
        ws = wb.active
        if ws is None:
            wb.close()
            raise HTTPException(500, "Excel 无活动工作表")
        rows = []
        for i, row in enumerate(
            ws.iter_rows(min_row=1, values_only=True)
        ):
            if i >= EXCEL_PREVIEW_MAX_ROWS:
                break
            rows.append([str(c or "")[:EXCEL_CELL_MAX_CHARS] for c in row])
        wb.close()
        return {"type": "excel", "rows": rows}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Excel 读取失败: {e}")
