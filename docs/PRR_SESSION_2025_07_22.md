# PRR 修复 + 前端认证集成 — 变更记录

> 日期：2025-07-22
> 范围：Production Readiness Review (PRR) 全量问题修复 + 前端认证集成

## 一、P0 严重问题修复

### P0-1: bcrypt 依赖断裂（3个认证测试失败）

**问题**：`pyproject.toml` 的 `web` 依赖组声明了 `bcrypt>=4.0`，但 Docker slim 镜像缺少 `libffi-dev`，导致 bcrypt 从源码编译失败，`tests/test_auth_jwt.py` 中 3 个测试报 `ModuleNotFoundError: No module named 'bcrypt'`。

**修复**：
- 在 `Dockerfile` builder 阶段添加 `libffi-dev`（bcrypt 编译所需的 C 库头文件）
- 在本地环境执行 `uv pip install bcrypt` 确认 19 个认证测试全部通过

**文件**：`Dockerfile`

### P0-2: Pipeline 后台线程无全局超时保护

**问题**：`PipelineTask._execute()` 在 daemon 线程中运行 Pipeline，但没有任何全局超时。当 LLM 出现半开连接（TCP 连接已建立但无数据返回）时，线程会无限阻塞，导致 ThreadPoolExecutor(max_workers=2) 的任务槽被永久占用，新任务无法调度。

**修复**：
- 新增常量 `PIPELINE_GLOBAL_TIMEOUT = 1800`（30 分钟，覆盖 8 步 × 120s LLM timeout + 余量）
- 重写 `_execute()` 方法：在内部创建一个 daemon 线程执行 `Pipeline.run()`，外层 `join(timeout=PIPELINE_GLOBAL_TIMEOUT)` 等待
- 超时后设置 `_cancel_flag`，标记任务状态为 `error`，持久化到 DB，发布 EventBus 事件
- 正常完成时检查 `result_holder` 字典处理 cancelled/error/success 三种状态

**文件**：`web/services/pipeline_task.py`

### P0-3: CI 覆盖率门槛与文档不一致

**问题**：`docs/PRR_REMEDIATION.md` 记录覆盖率为 75%，但 `.github/workflows/test.yml` 中 `--cov-fail-under=60`，实际基线为 66%。门槛过低，无法有效防止覆盖率退化。

**修复**：
- 将 `--cov-fail-under` 从 60 改为 65（与当前 66% 基线留 1% 缓冲）
- 更新注释说明目标 75%，逐步提升

**文件**：`.github/workflows/test.yml`

---

## 二、P1 建议修复

### P1-1: PostgreSQL 迁移支持

**问题**：生产环境使用 SQLite + WAL 模式，高并发写入时存在锁竞争。`db/session.py` 已有 PostgreSQL 连接池配置（pool_pre_ping / pool_recycle），但 `_get_database_url()` 硬编码返回 SQLite URL，无法通过环境变量切换。

**修复**：
- `db/session.py`：`_get_database_url()` 优先读取 `DATABASE_URL` 环境变量，支持 `postgresql://` / `mysql://` 等网络数据库连接串；`get_engine()` 按 URL 协议分别处理 SQLite / 非 SQLite 路径
- `pyproject.toml`：新增 `postgresql` 可选依赖组（`psycopg2-binary>=2.9`），`all` 依赖组同步更新
- `Dockerfile`：builder 阶段添加 `libpq-dev`（psycopg2 编译依赖），runtime 阶段添加 `libpq5`（运行时依赖），pip install extras 包含 `postgresql`
- `docker-compose.postgres.yml`：新建 PostgreSQL compose override 文件，包含 PostgreSQL 16 Alpine 服务（带健康检查 + 资源限制 + 数据卷持久化），app 服务通过 `DATABASE_URL` 环境变量切换连接

**文件**：`db/session.py`、`pyproject.toml`、`Dockerfile`、`docker-compose.postgres.yml`（新建）

### P1-2: 登录端点独立限流 + 失败锁定

**问题**：登录端点仅受全局 60/min 限流保护，缺少独立的暴力破解防护。攻击者可在限流窗口内尝试 60 次密码组合。

**修复**：
- 新建 `web/middleware/login_lockout.py`：内存滑动窗口计数器，按 IP + 用户名组合跟踪失败次数，连续失败 5 次锁定 15 分钟，登录成功或锁定过期自动清除
- `web/api/auth.py`：
  - 新增 `Request` 参数提取客户端 IP
  - 登录前检查是否被锁定（返回 429 + Retry-After header）
  - 认证失败调用 `record_failure()`，成功调用 `record_success()`
  - 挂载 slowapi `@limiter.limit("5/minute")` 独立限流装饰器

**文件**：`web/middleware/login_lockout.py`（新建）、`web/api/auth.py`

### P1-3: 数据库自动备份配置

**问题**：无数据库备份方案，数据丢失不可恢复。

**修复**：
- 新建 `docs/BACKUP.md`：完整备份方案文档，覆盖 SQLite 和 PostgreSQL 两种部署模式
- 新建 `scripts/backup_sqlite.sh`：SQLite 在线备份脚本（使用 `.backup` 命令保证一致性，自动压缩 + 过期清理）
- 新建 `scripts/backup_postgres.sh`：PostgreSQL 逻辑备份脚本（pg_dump custom 格式 + gzip 压缩 + 过期清理）
- 文档包含 Docker sidecar 容器配置、恢复流程、备份验证方法、保留策略建议

**文件**：`docs/BACKUP.md`（新建）、`scripts/backup_sqlite.sh`（新建）、`scripts/backup_postgres.sh`（新建）

### P1-4: 日志收集系统配置

**问题**：应用已使用 structlog 输出 JSON 格式日志，但缺少日志收集 / 聚合 / 查询方案。

**修复**：
- 新建 `docs/LOG_COLLECTION.md`：完整日志收集配置文档
- 方案一（推荐）：Loki + Promtail + Grafana，包含 docker-compose 配置、promtail 配置（Docker 日志自动发现 + JSON 解析）、LogQL 查询示例
- 方案二：ELK Stack，包含 Elasticsearch + Logstash + Kibana 配置、Logstash pipeline 配置
- 包含日志告警规则（Loki Ruler）、保留策略建议

**文件**：`docs/LOG_COLLECTION.md`（新建）

### P1-5: LLM readiness 探针增加真实连通性检查

**问题**：`/health/ready` 的 LLM 检查仅验证配置是否存在（`api_key` + `model` 非空），不验证 API Key 有效性和网络可达性。LLM 服务不可用时 readiness 仍返回 ok，K8s 继续导流量但所有 Pipeline 任务会失败。

**修复**：
- `web/app.py` 的 `_check_dependencies()` 中 LLM 检查改为发送轻量 ping 请求（`max_tokens=1`，timeout=5s），验证 API Key 有效性和网络可达性
- 增加 30 秒结果缓存，避免每次 readiness 探测都调用 LLM API（K8s 默认 10s 探测间隔）
- 错误信息截断至 200 字符，避免过长错误消息

**文件**：`web/app.py`

### P1-6: CSP 移除 unsafe-inline

**问题**：CSP `script-src` 包含 `'unsafe-inline'`，允许内联脚本执行，削弱了 XSS 防护。Vite 构建产物使用外部 `<script src>` 引用，实际不需要 `unsafe-inline`。

**修复**：
- 移除 `script-src` 和 `style-src` 中的 `'unsafe-inline'`
- 保留 `https://unpkg.com`（Vue 框架 CDN）和 `https://fonts.googleapis.com`（Google Fonts）
- 添加注释说明 Vite 构建产物使用外部资源引用，无需 unsafe-inline

**文件**：`web/app.py`

### P1-7: K8s 部署清单

**问题**：仅有 Docker Compose 部署方案，缺少 Kubernetes 生产部署清单。

**修复**：
- 新建 `deploy/k8s/deployment.yml`：完整 K8s 部署清单，包含：
  - Namespace + ConfigMap + Secret（含安全创建指引）
  - PVC 数据持久化（20Gi）
  - Deployment（2 副本，滚动更新策略 maxSurge=1/maxUnavailable=0，安全上下文 runAsNonRoot，资源 requests/limits）
  - Service（ClusterIP）
  - Ingress（nginx-ingress，TLS，文件上传 50m，SSE 300s 超时，Ingress 层限流 60/min）
  - HPA（CPU 70% + Memory 80%，min=2 max=6，扩容稳定 60s / 缩容稳定 300s）
  - PDB（minAvailable=1，保证滚动更新时至少 1 个 Pod 可用）
  - NetworkPolicy（仅允许 ingress-nginx 和 monitoring 命名空间访问，egress 仅允许 DNS + HTTPS）

**文件**：`deploy/k8s/deployment.yml`（新建）

---

## 三、前端认证集成

### 背景

PRR 评审中发现后端已有完整的 JWT 认证体系（`web/api/auth.py` 登录端点、`web/middleware/auth.py` JWT 验证中间件、`web/services/user_service.py` bcrypt 密码哈希），但前端 Vue 应用完全未集成认证——无登录页、无 token 持久化、请求拦截器不注入 Authorization header、路由无守卫保护。

### 实现

**1. 认证状态管理 — `webui/src/composables/useAuth.js`（新建）**
- 使用 Vue 3 `reactive` + `computed` 管理全局认证状态
- Token 和用户信息持久化到 `localStorage`（`aitest_token` / `aitest_user`）
- 导出 `isAuthenticated` / `currentUser` / `authToken` 计算属性
- 导出 `setAuth()` / `clearAuth()` / `logout()` 方法

**2. 请求拦截器 — `webui/src/composables/useApi.js`（修改）**
- `request()` 函数自动从 `authToken` 读取 token 并注入 `Authorization: Bearer {token}` header
- 登录接口自身跳过 token 注入（`path.includes('/auth/login')`）
- 401 响应自动清除本地 token 并跳转登录页（`window.location.href = '/login'`）

**3. 登录页 — `webui/src/views/Login.vue`（新建）**
- 表单包含用户名 / 密码输入，提交调用 `POST /api/v1/auth/login`
- 登录成功后调用 `setAuth()` 持久化 token，跳转到 redirect 参数或首页
- 错误处理：401 显示"用户名或密码错误"，429 显示限流提示，网络错误显示连接提示
- 样式使用项目 CSS 变量（tokens.css），适配亮色/暗色模式

**4. 路由守卫 — `webui/src/router/index.js`（修改）**
- 新增 `/login` 路由，标记 `meta.public = true`
- `router.beforeEach()` 守卫：未认证用户访问受保护路由 → 重定向到 `/login?redirect=原始路径`；已认证用户访问 `/login` → 重定向到首页

**5. 侧边栏用户信息 — `webui/src/components/AppSidebar.vue`（修改）**
- 底部新增用户信息区：头像（用户名首字母）+ 用户名 + 登出按钮
- 点击登出弹出确认框，确认后调用 `logout()` 清除状态并跳转登录页
- 移动端隐藏用户信息区（底部 tab bar 空间有限）

---

## 四、变更文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `Dockerfile` | 修改 | 添加 libffi-dev / libpq-dev / libpq5，pip extras 加 postgresql |
| `.github/workflows/test.yml` | 修改 | 覆盖率门槛 60% → 65% |
| `web/services/pipeline_task.py` | 修改 | Pipeline 全局超时保护（1800s） |
| `db/session.py` | 修改 | 支持 DATABASE_URL 环境变量切换 PostgreSQL |
| `pyproject.toml` | 修改 | 新增 postgresql 依赖组 |
| `docker-compose.postgres.yml` | 新建 | PostgreSQL compose override |
| `web/middleware/login_lockout.py` | 新建 | 登录失败锁定模块 |
| `web/api/auth.py` | 修改 | 独立限流 + 失败锁定 |
| `docs/BACKUP.md` | 新建 | 数据库备份方案文档 |
| `scripts/backup_sqlite.sh` | 新建 | SQLite 备份脚本 |
| `scripts/backup_postgres.sh` | 新建 | PostgreSQL 备份脚本 |
| `docs/LOG_COLLECTION.md` | 新建 | 日志收集配置文档 |
| `web/app.py` | 修改 | LLM readiness 真实连通性检查 + CSP 移除 unsafe-inline |
| `deploy/k8s/deployment.yml` | 新建 | K8s 部署清单 |
| `webui/src/composables/useAuth.js` | 新建 | 前端认证状态管理 |
| `webui/src/composables/useApi.js` | 修改 | Token 自动注入 + 401 处理 |
| `webui/src/views/Login.vue` | 新建 | 登录页 |
| `webui/src/router/index.js` | 修改 | 路由守卫 + login 路由 |
| `webui/src/components/AppSidebar.vue` | 修改 | 用户信息 + 登出按钮 |
