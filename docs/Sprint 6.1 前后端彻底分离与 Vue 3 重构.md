# Sprint 6.1 前后端彻底分离与 Vue 3 重构

> 状态：✅ 已完成 | 日期：2026-07-20 | 测试：537 passed / 10 skipped / 0 failed

## 目标

将 HTMX + Jinja2 服务端渲染架构迁移为 **FastAPI 纯 JSON API + Vue 3 SPA** 前后端彻底分离架构。

## 架构变更

```
Before (Sprint 6.0):
  FastAPI + Jinja2Templates + HTMX 片段 → 服务端渲染 HTML

After (Sprint 6.1):
  FastAPI 纯 JSON API (/api/v1/*)
  + Vue 3 SPA (webui/, Vite 构建 → web/static/dist/)
  + SPA Fallback (非 API 路径返回 index.html)
```

## 实施步骤

### 第一步：后端 JSON 化

| 文件 | 改动 |
|------|------|
| `web/app.py` | 移除 `Jinja2Templates` 实例和 `static_v` 过滤器；6 个页面路由（`/`, `/pipelines`, `/knowledge` 等）改为返回 JSON；新增 SPA fallback |
| `web/api/pipeline.py` | `GET /{pipeline_id}/progress` 移除 HTMX HTML 分支，统一返回 JSON；清理 `_templates`、`Request`、`_TERMINAL_EVENTS` 等死代码 |
| `web/api/views.py` | **删除**（HTMX 智能片段路由不再需要） |

### 第二步：知识库 API 重写

`web/api/knowledge.py` 重写为纯 JSON API：

- 使用 `session_scope()`（非文档中不存在的 `get_db`）
- 使用 `get_dynamic_kb_manager()`（非文档中不存在的 `kb_manager_instance`）
- 搜索响应增加 `query` 字段回显
- 端点：`status`、`search`、`import`、`add`、`update_config`、`current_config`

### 第三步：路由统一挂载

- 5 个 API 文件移除内部 `APIRouter(prefix=...)` 声明
- `web/app.py` 统一挂载 `/api/v1/*` 前缀，避免双重前缀
- SPA Fallback：仅当 `web/static/dist/index.html` 存在时，非 API 路径返回 Vue 构建产物

### 第四步：Vue 3 前端工程

新建 `webui/` 目录：

```
webui/
├── package.json          # Vue 3.5 + Vue Router 4.5 + Vite 6.2
├── vite.config.js        # /api 代理 → 127.0.0.1:8090, 构建输出 → ../web/static/dist
├── index.html
├── public/favicon.svg
└── src/
    ├── main.js           # createApp + createWebHistory 路由
    ├── App.vue           # 应用外壳 + 导航
    └── views/
        ├── Home.vue           # 上传需求文档 + 启动 pipeline
        ├── KnowledgeConfig.vue # 知识库动态配置（热切换）
        └── PipelineList.vue   # 任务列表 + 搜索 + 操作
```

- `npm install` → 35 packages
- `npm run build` → 产物输出到 `web/static/dist/`

### 第五步：清理与测试修复

- `web/templates/` → 归档到 `legacy/templates_sprint60/`（非物理删除，保留回滚能力）
- 12 个测试文件修复：
  - `/api/xxx` → `/api/v1/xxx` 前缀迁移
  - `text/html` 断言 → `application/json` 或兼容 SPA `text/html`
  - Auth 残留（`user_service`、`/api/auth/*`、`create_admin`）→ `pytest.skip("Auth module removed in Sprint 6.0")`
  - `test_build_steps_view` 步骤数 7→8，索引 1-based→0-based
  - SSE 路由验证改用 OpenAPI schema
  - 404 响应 `detail` → `error` 字段兼容

## 原始文档勘误

原始指令文档含 4 处会导致系统立即崩硬的错误，已在实施中修正：

| # | 原始文档 | 实际修正 |
|---|---------|---------|
| 1 | `from core.kb.kb_manager import kb_manager_instance` | `from core.kb.dynamic_kb_manager import get_dynamic_kb_manager` |
| 2 | `from db.session import get_db` | 使用项目现有 `session_scope()` 上下文管理器 |
| 3 | `rm -rf web/templates` | 归档到 `legacy/templates_sprint60/`，保留回滚能力 |
| 4 | `app.include_router(pipeline.router, prefix="/api/v1/pipeline")` + router 内部 `/api/pipeline` | 移除 router 内部 prefix，由 app 统一挂载 |

## 验证结果

```
pytest tests/ -q → 537 passed, 10 skipped, 0 failed

/health                    → {"status":"ok", checks: api/database/llm/kb 全 ok}
/api/v1/knowledge/status   → 516 条知识库条目
/api/v1/pipeline/list      → 正常返回任务列表
/knowledge                 → 200 text/html (Vue SPA)
/docs                      → 200 (Swagger UI)
```

## 开发/生产模式

| 模式 | 前端 | 后端 | 说明 |
|------|------|------|------|
| 开发 | `cd webui && npm run dev` → `127.0.0.1:5173` | `uvicorn web.app:app --port 8090` | Vite HMR + `/api` 代理 |
| 生产 | `cd webui && npm run build` → `web/static/dist/` | 同上 | SPA fallback 直接服务构建产物 |
