#!/usr/bin/env python3
"""
FastAPI 应用入口 — WebUI

启动方式:
    python -m web.app
    uvicorn web.app:app --reload --port 8080
"""

import os
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 先加载 .env，确保后续模块导入时 os.environ 已有 API_KEY / JWT_SECRET 等配置。
# 必须在 web.api.auth / web.middleware.auth 等模块导入之前执行，
# 否则模块级 os.environ.get() 会读到空值（时序 bug）。
from core.config_loader import _load_dotenv

_load_dotenv(PROJECT_ROOT / ".env")

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from core.config_loader import load_config
from core.errors import AppError, app_error_handler
from web.api import auth as auth_api
from web.api import config as config_api
from web.api import knowledge, pipeline, webhooks
from web.services.task_manager import get_task_manager

# SSE 路由（Phase 3，可能尚未创建）
try:
    from web.api import sse as sse_api
except ImportError:
    sse_api = None

# 集成服务路由（Phase 2）
try:
    from integrations.service import router as integrations_router
except ImportError:
    integrations_router = None

# ─── FastAPI 应用 ───

app = FastAPI(
    title="AI 测试用例生成系统",
    description="从需求到测试报告的全流程自动化",
    version="2.0.0-alpha",
)

# 静态文件
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 模板
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


# ─── 静态资源版本指纹（cache busting）───
# 用文件 mtime 生成版本号，文件一改 URL 自动变，浏览器不会用旧缓存
def _static_version(path: str) -> str:
    """Jinja2 过滤器：给静态资源路径追加 ?v=mtime 后缀"""
    full = static_dir / path
    try:
        return f"/static/{path}?v={int(full.stat().st_mtime)}"
    except OSError:
        return f"/static/{path}"


templates.env.filters["static_v"] = _static_version

# 注册路由
app.include_router(pipeline.router)

# 注册 AppError 异常处理器
app.add_exception_handler(AppError, app_error_handler)
app.include_router(knowledge.router)
app.include_router(config_api.router)
app.include_router(webhooks.router)
app.include_router(auth_api.router)
if sse_api is not None:
    app.include_router(sse_api.router)
if integrations_router is not None:
    app.include_router(integrations_router)


# ─── 安全与性能中间件 ───

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """添加安全响应头 + 静态资源缓存 + CSP + HSTS"""

    # 内容安全策略（CSP）：限制资源加载来源
    CSP_POLICY = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # 静态资源缓存：CSS/JS 缓存 24 小时，图片/字体缓存 7 天
        path = request.url.path
        if path.startswith("/static/"):
            if path.endswith((".css", ".js")):
                response.headers["Cache-Control"] = "public, max-age=3600, immutable"
            elif any(path.endswith(ext) for ext in (".png", ".jpg", ".svg", ".ico", ".woff2")):
                response.headers["Cache-Control"] = "public, max-age=604800, immutable"

        # 安全头
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = self.CSP_POLICY
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        return response


app.add_middleware(SecurityHeadersMiddleware)

from web.middleware.csrf import CSRFMiddleware

app.add_middleware(CSRFMiddleware)

# ─── Gzip 压缩中间件 ───
try:
    from starlette.middleware.gzip import GZipMiddleware
    app.add_middleware(GZipMiddleware, minimum_size=500)
except ImportError:
    pass

# ─── 速率限制（slowapi 集成）───
try:
    from web.middleware.rate_limit import setup_rate_limiting

    setup_rate_limiting(app)
except ImportError:
    pass  # slowapi 未安装时跳过

# ─── 结构化日志中间件（Phase 6）───
try:
    from web.middleware.logging import LoggingMiddleware, configure_logging

    configure_logging()
    app.add_middleware(LoggingMiddleware)
except ImportError:
    pass  # structlog 未安装时跳过

# ─── JWT 密钥校验（启动时显式调用）───
try:
    from web.middleware.auth import validate_secret_on_startup

    validate_secret_on_startup()
except ImportError:
    pass

# ─── KB 缓存预热（后台异步，不阻塞启动）───
# 首次 status/search 请求要构建单例 + 全量遍历 Vault（~5s），
# 启动时后台预热，用户访问时永远是缓存命中（<1ms）。
try:
    import threading

    def _warmup_kb_cache():
        try:
            from web.services.kb_cache import get_status
            get_status()  # 触发单例构建 + status 缓存填充
        except Exception:
            pass  # 预热失败不影响启动，首次请求时会重试

    threading.Thread(target=_warmup_kb_cache, daemon=True, name="kb-cache-warmup").start()
except Exception:
    pass


# ─── 应用关闭时清理 TaskManager 线程池（防止资源泄漏）───
@app.on_event("shutdown")
async def _shutdown_task_manager():
    try:
        get_task_manager().shutdown()
    except Exception:
        pass

# ─── 全局异常处理（Phase 6）───


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理 — 所有未捕获的异常返回标准 JSON

    安全：生产环境不泄露内部异常详情（可能包含路径、密钥片段等），
    仅记录到日志，返回通用错误消息。
    AppError 由专用处理器处理（已注册），此处 isinstance 检查为安全兜底。
    """
    # AppError 由专用处理器处理，不应到达此处
    if isinstance(exc, AppError):
        return app_error_handler(request, exc)

    import logging

    logger = logging.getLogger("ai-test-system")
    logger.error(
        "Unhandled exception on %s %s: %s",
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )

    env = os.environ.get("AI_TEST_ENV", "")
    detail = str(exc) if env == "development" else "An internal error occurred"

    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "detail": detail,
            "path": request.url.path,
        },
    )


# ─── 页面路由（服务端渲染）───

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """首页 — 上传需求 + 启动 Pipeline"""
    tm = get_task_manager()
    running_count = tm.get_running_count()
    return templates.TemplateResponse(request, "index.html", {
        "title": "AI 测试用例生成系统",
        "running_count": running_count,
    })


@app.get("/pipeline/{pipeline_id}", response_class=HTMLResponse)
async def pipeline_page(request: Request, pipeline_id: str):
    """Pipeline 进度页"""
    return templates.TemplateResponse(request, "pipeline.html", {"pipeline_id": pipeline_id})


@app.get("/results/{pipeline_id}", response_class=HTMLResponse)
async def results_page(request: Request, pipeline_id: str):
    """结果预览页"""
    return templates.TemplateResponse(request, "results.html", {"pipeline_id": pipeline_id})


@app.get("/knowledge", response_class=HTMLResponse)
async def knowledge_page(request: Request):
    """知识库管理页"""
    return templates.TemplateResponse(request, "knowledge.html", {})


@app.get("/pipelines", response_class=HTMLResponse)
async def pipelines_page(request: Request):
    """Pipeline 列表页"""
    tm = get_task_manager()
    running_count = tm.get_running_count()
    return templates.TemplateResponse(request, "pipelines.html", {
        "title": "Pipeline 列表",
        "running_count": running_count,
    })


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """登录页"""
    return templates.TemplateResponse(request, "login.html", {})


@app.get("/health")
async def health():
    """健康检查 — 返回各组件连通性状态

    检查项：
      - api: FastAPI 应用本身（始终 ok）
      - database: SQLite 连通性
      - llm: LLM 配置是否就绪（不实际调用）
      - knowledge_base: 知识库路径是否存在
    """
    checks = {"api": "ok"}

    # 检查数据库
    try:
        from sqlalchemy import text

        from db.session import get_engine

        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    # 检查 LLM 配置（不实际调用）
    try:
        config = load_config()
        llm_cfg = config.get("llm", {})
        if llm_cfg.get("api_key") and llm_cfg.get("model"):
            checks["llm"] = "ok"
        else:
            checks["llm"] = "not_configured"
    except Exception:
        checks["llm"] = "error"

    # 检查知识库
    try:
        config = load_config()
        kb_cfg = config.get("knowledge_base", {})
        if kb_cfg.get("enabled"):
            vault = Path(kb_cfg.get("vault_path", ""))
            checks["knowledge_base"] = "ok" if vault.exists() else "vault_not_found"
        else:
            checks["knowledge_base"] = "disabled"
    except Exception:
        checks["knowledge_base"] = "error"

    # 综合状态
    all_ok = all(v == "ok" or v == "disabled" or v == "not_configured" for v in checks.values())

    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={
            "status": "ok" if all_ok else "degraded",
            "version": "2.0.0",
            "checks": checks,
        },
    )


# ─── 入口 ───

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
