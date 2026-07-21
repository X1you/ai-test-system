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
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from core.config_loader import load_config
from core.errors import AppError, app_error_handler
from web.api import config as config_api
from web.api import knowledge, pipeline, webhooks
from web.api.auth import router as auth_router
from web.middleware.auth import verify_token
from web.services.task_manager import get_task_manager

# SSE 路由（Phase 3，可能尚未创建）
try:
    from web.api import sse as sse_api
except ImportError:
    sse_api = None

# 单一版本常量（与 CHANGELOG.md 保持同步）
APP_VERSION = "2.1.0"

# 集成服务路由（Phase 2）
try:
    from integrations.service import router as integrations_router
except ImportError:
    integrations_router = None

# ─── FastAPI 应用 ───

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理（替代已废弃的 @app.on_event）。

    startup 阶段（yield 之前）：
      1. JWT 密钥安全校验
      2. 管理员账户初始化
      3. 僵尸任务检测 + interrupted 恢复
      4. KB 缓存后台预热
    shutdown 阶段（yield 之后）：
      清理 TaskManager 线程池，防止 ThreadPoolExecutor 资源泄漏
    """
    _run_startup_tasks()
    yield
    _run_shutdown_tasks()


app = FastAPI(
    title="AI 测试用例生成系统",
    description="从需求到测试报告的全流程自动化",
    version=APP_VERSION,
    lifespan=lifespan,
)

# 静态文件
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 注册路由（Sprint 6.1：统一 /api/v1 前缀，避免重叠）
# JWT 认证：除 auth/login（自身用于获取 token）和 webhooks（外部系统回调）外，
# 所有 API 路由强制 require verify_token 依赖。
from fastapi import Depends  # noqa: E402

_auth_dep = [Depends(verify_token)]

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(
    pipeline.router, prefix="/api/v1/pipeline", tags=["pipeline"], dependencies=_auth_dep
)
app.include_router(
    knowledge.router, prefix="/api/v1/knowledge", tags=["knowledge"], dependencies=_auth_dep
)
app.include_router(
    config_api.router, prefix="/api/v1/config", tags=["config"], dependencies=_auth_dep
)
# webhooks 豁免认证：外部系统（CI/CD 等）回调无法携带 JWT
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["webhooks"])

# 注册 AppError 异常处理器
app.add_exception_handler(AppError, app_error_handler)
if sse_api is not None:
    app.include_router(
        sse_api.router, prefix="/api/v1/pipeline", tags=["sse"], dependencies=_auth_dep
    )
if integrations_router is not None:
    app.include_router(integrations_router)  # integrations 自带 prefix，保留


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

# ─── CORS 中间件（前后端分离部署时必需）───
from starlette.middleware.cors import CORSMiddleware  # noqa: E402

_cors_origins = load_config().get("security", {}).get("cors_origins", [])
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    )

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

# ─── Prometheus 可观测性（/metrics 端点）───
# instrumentator 自动暴露 GET /metrics（Prometheus exposition 格式），
# 记录 HTTP 请求维度指标（延迟/状态码/路径）。
# /metrics 端点豁免 JWT 认证（Prometheus 抓取不带 token，靠网络隔离保护）。
try:
    from prometheus_fastapi_instrumentator import Instrumentator

    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=["/metrics", "/health"],  # 不采集自身和健康检查
    ).instrument(app).expose(
        app,
        endpoint="/metrics",
        include_in_schema=False,  # 不出现在 /docs OpenAPI 中
        tags=["monitoring"],
    )
except ImportError:
    pass  # prometheus-fastapi-instrumentator 未安装时跳过

# ─── OpenTelemetry 分布式追踪（可选）───
# 需设置 OTEL_EXPORTER_OTLP_ENDPOINT 环境变量才启用。
# 未配置时完全静默，零开销。
try:
    from web.middleware.tracing import setup_tracing

    setup_tracing(app)
except ImportError:
    pass  # opentelemetry 未安装时跳过

# ─── 结构化日志中间件（Phase 6）───
try:
    from web.middleware.logging import LoggingMiddleware, configure_logging

    configure_logging()
    app.add_middleware(LoggingMiddleware)
except ImportError:
    pass  # structlog 未安装时跳过

# ─── 应用生命周期：startup / shutdown（lifespan 上下文管理器调用）───


def _run_startup_tasks():
    """应用启动任务（由 lifespan 调用）。

    1. JWT 密钥安全校验（生产环境弱密钥拒绝启动）
    2. 确保管理员账户存在（首次启动自动创建）
    3. 僵尸任务检测 + interrupted 恢复
    4. KB 缓存后台预热（不阻塞启动）
    """
    import logging

    logger = logging.getLogger("web")

    # 1. JWT 密钥校验（弱密钥/生产环境缺失会 SystemExit）
    from web.middleware.auth import validate_secret_on_startup

    validate_secret_on_startup()

    # 2. 确保管理员账户存在（幂等，仅首次创建）
    try:
        from web.services.user_service import create_admin_if_not_exists

        if create_admin_if_not_exists():
            logger.info("已创建默认管理员账户 admin/admin123（请尽快修改密码）")
    except Exception as e:
        logger.warning(f"管理员账户初始化失败（不影响启动）: {e}")

    # 3. 僵尸检测 + 任务恢复
    try:
        from db.models import Pipeline
        from db.repository import get_repository
        from db.session import session_scope

        with session_scope() as session:
            # running/pending/paused → interrupted
            stale = (
                session.query(Pipeline)
                .filter(Pipeline.status.in_(["running", "pending", "paused"]))
                .all()
            )
            for p in stale:
                p.status = "interrupted"
                p.error = "服务重启，任务中断"
            if stale:
                logger.info(f"启动清理：{len(stale)} 个僵尸任务标记为 interrupted")

        # interrupted 中可续跑的重建到内存
        try:
            tm = get_task_manager()
            from pathlib import Path as _Path

            with session_scope() as session:
                recoverable = (
                    session.query(Pipeline)
                    .filter(Pipeline.status == "interrupted")
                    .all()
                )
            recovered = 0
            for p in recoverable:
                req_ok = bool(
                    p.requirements_path and _Path(p.requirements_path).exists()
                )
                if not req_ok:
                    continue
                steps = get_repository().get_completed_step_ids(p.id)
                if not steps:
                    continue
                if p.id not in tm._tasks:
                    tm.rebuild_task_from_db(p.id)
                    recovered += 1
            if recovered:
                logger.info(
                    f"持久化恢复：{recovered} 个 interrupted 任务已重建到内存（paused）"
                )
        except Exception as e:
            logger.warning(f"任务恢复失败（不影响启动）: {e}")
    except Exception as e:
        logger.error(f"启动清理失败: {e}", exc_info=True)

    # 4. KB 缓存后台预热（不阻塞启动）
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

        threading.Thread(
            target=_warmup_kb_cache, daemon=True, name="kb-cache-warmup"
        ).start()
    except Exception as e:
        import logging
        logging.getLogger("web").debug("kb_cache_warmup_failed: %s", e)


def _run_shutdown_tasks():
    """应用关闭任务（由 lifespan 调用）。

    清理 TaskManager 的 ThreadPoolExecutor，防止线程池资源泄漏。
    """
    try:
        get_task_manager().shutdown()
    except Exception as e:
        import logging
        logging.getLogger("web").warning("task_manager_shutdown_failed: %s", e)

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


# ─── 页面路由（Sprint 6.1: 全部改为 JSON，SPA 由前端 Vue 接管）───

@app.get("/")
async def index():
    """根路径 — 前端已构建时返回 SPA，否则返回系统元信息"""
    _dist_index = Path(__file__).parent / "static" / "dist" / "index.html"
    if _dist_index.exists():
        from fastapi.responses import FileResponse
        return FileResponse(str(_dist_index))
    tm = get_task_manager()
    return {
        "name": "AI 测试用例生成系统",
        "version": APP_VERSION,
        "running_count": tm.get_running_count(),
        "spa_hint": "前端 Vue 工程见 webui/，启动方式见 README",
    }


def _check_dependencies() -> dict:
    """依赖连通性检查（供 readiness 复用）。

    返回各依赖组件的状态字典。所有检查异常安全，不抛出。
    """
    # api 组件：能响应本端点即 ok（始终 ok，保留向后兼容）
    checks: dict = {"api": "ok"}

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

    # 检查知识库（DB 数据源，与 /knowledge/status 同源）
    try:
        from core.kb.dynamic_kb_manager import get_dynamic_kb_manager

        mgr = get_dynamic_kb_manager()
        if mgr.is_configured():
            cfg = mgr.get_config()
            vault = Path(cfg.get("vault_path", "")) if cfg and cfg.get("vault_path") else None
            if vault and vault.exists():
                checks["knowledge_base"] = "ok"
            elif vault:
                checks["knowledge_base"] = "vault_not_found"
            else:
                # obsidian_api 等 provider 不依赖本地 vault 路径
                checks["knowledge_base"] = "ok"
        else:
            checks["knowledge_base"] = "not_configured"
    except Exception:
        checks["knowledge_base"] = "error"

    return checks


def _all_dependencies_ok(checks: dict) -> bool:
    """依赖检查是否全部通过（not_configured/disabled 也算通过）。"""
    return all(v == "ok" or v == "disabled" or v == "not_configured" for v in checks.values())


@app.get("/health/live")
async def liveness():
    """Liveness 探针 — 进程是否存活。

    只要进程能响应即为存活，不检查任何外部依赖。
    K8s/Docker 配置：liveness 失败 → 重启进程。
    """
    return JSONResponse(
        status_code=200,
        content={"status": "alive"},
    )


@app.get("/health/ready")
async def readiness():
    """Readiness 探针 — 是否准备好接收流量。

    检查 DB / LLM / KB 依赖连通性。任一关键依赖不可用返回 503。
    K8s/Docker 配置：readiness 失败 → 摘除流量（不重启进程）。
    """
    checks = _check_dependencies()
    all_ok = _all_dependencies_ok(checks)
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={
            "status": "ok" if all_ok else "degraded",
            "version": APP_VERSION,
            "checks": checks,
        },
    )


@app.get("/health")
async def health():
    """健康检查（向后兼容）— 等价于 /health/ready。

    新部署建议直接用 /health/live + /health/ready 分离探针。
    """
    checks = _check_dependencies()
    all_ok = _all_dependencies_ok(checks)
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={
            "status": "ok" if all_ok else "degraded",
            "version": APP_VERSION,
            "checks": checks,
        },
    )


# ─── SPA Fallback（生产环境：将非 API 请求交给 Vue index.html）───
# 仅当 web/static/dist/index.html 存在（前端已构建）时启用
_dist_dir = Path(__file__).parent / "static" / "dist"
_index_file = _dist_dir / "index.html"

if _index_file.exists():
    from fastapi.responses import FileResponse

    # 挂载 Vite 构建产物中的 /assets 目录（JS/CSS/图片等）
    _assets_dir = _dist_dir / "assets"
    if _assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="spa-assets")

    @app.get("/{catchall:path}")
    async def serve_spa(catchall: str):
        """SPA 回退：非 API 请求统一返回 index.html（Vue Router 接管）

        catchall 已存在的精确路由（如 /health、/api/v1/...）会优先匹配，
        此路由只兜底处理未命中的路径。
        """
        # 避免把 API 404 误判为 SPA 路由
        if catchall.startswith("api/"):
            return JSONResponse(
                status_code=404,
                content={"error": "API Endpoint Not Found", "path": catchall},
            )
        # 静态资源直接 404（不该走 SPA）
        if catchall.startswith("static/"):
            return JSONResponse(
                status_code=404,
                content={"error": "Static Resource Not Found", "path": catchall},
            )
        return FileResponse(str(_index_file))
else:
    # 前端未构建时，根路径之外的未知路径返回 JSON 提示（开发期友好）
    @app.get("/{catchall:path}")
    async def spa_not_built(catchall: str):
        if catchall.startswith("api/") or catchall.startswith("static/"):
            return JSONResponse(
                status_code=404,
                content={"error": "Not Found", "path": catchall},
            )
        return JSONResponse(
            status_code=200,
            content={
                "message": "Frontend not built yet. Run `npm run build` in webui/.",
                "path": catchall,
                "api_docs": "/docs",
                "health": "/health",
            },
        )


# ─── 入口 ───

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
