# PRR 整改报告 — 生产就绪审查修复记录

> **审查日期**：2026-07-21
> **审查版本**：v2.1.0
> **整改状态**：全部 P0 + P1 + 附加项已完成
> **审查人**：首席架构师 / SRE 专家

---

## 一、P0 紧急修复（阻断上线项）

### P0-1：Dockerfile 补全 production extras + 非 root 用户

**问题**：`Dockerfile` 安装依赖时漏掉了 `production` extras，导致 `structlog`、`slowapi`、`prometheus-fastapi-instrumentator`、`opentelemetry-*` 全部缺失。`web/app.py` 中所有可观测性组件的初始化代码包裹在 `try/except ImportError: pass` 中，静默跳过 → 生产环境无限流、无监控、无告警、无结构化日志，且团队完全无法感知。

**修复内容**：

1. `Dockerfile` 第 24 行的 pip install 命令从 `.[web,xmind,excel,db]` 改为 `.[web,xmind,excel,db,production]`，确保生产加固依赖全部打包进镜像。
2. 新增非 root 用户 `appuser`，通过 `useradd -r -s /bin/false appuser && chown -R appuser:appuser /app` 创建并赋权，`USER appuser` 切换运行身份，消除容器内 root 权限风险。
3. `HEALTHCHECK` 从 `/health` 改为 `/health/live`（liveness 探针不检查依赖，避免误判），新增 `--start-period=30s` 给冷启动宽限期。

**修改文件**：`Dockerfile`

---

### P0-2：消除默认管理员凭证硬编码

**问题**：`web/services/user_service.py` 中 `create_admin_if_not_exists(username="admin", password="admin123")` 硬编码默认密码，且无首次登录强制改密机制。攻击者扫描到端口后可直接用默认凭证登录，消耗 LLM 额度或篡改系统配置。

**修复内容**：

1. 函数签名改为 `create_admin_if_not_exists(username: str | None = None, password: str | None = None)`，不再接受硬编码默认值。
2. 凭证来源优先级：函数参数（测试场景）→ 环境变量 `ADMIN_USERNAME` / `ADMIN_PASSWORD` → 未配置时生成随机密码（`secrets.token_urlsafe(16)`）并打印到日志。
3. 绝不使用 `admin123` 等弱密码作为默认值。

**修改文件**：`web/services/user_service.py`

**配套修改**：`docker-compose.yml` 新增 `ADMIN_USERNAME` 和 `ADMIN_PASSWORD` 环境变量透传；`.env.example` 添加管理员账户配置说明。

---

### P0-3：`_pipeline_state.json` 原子写入

**问题**：`core/pipeline.py` 的 `save_state` 方法直接 `path.write_text()` 覆写文件。进程在写入过程中被 OOM Kill 或宿主机重启时，文件会被截断为半截 JSON，导致重启后 `load_state` 抛 `JSONDecodeError`，Pipeline 状态完全丢失，断点续跑失败。

**修复内容**：

改为原子写入模式：先写入 `.json.tmp` 临时文件，再通过 `os.replace(tmp_path, path)` 原子替换目标文件。`os.replace` 在 POSIX 系统上是原子 `rename` 系统调用，保证要么旧文件完整、要么新文件完整。

**修改文件**：`core/pipeline.py`

---

### P0-4：Docker Compose 资源限制 + 日志轮转 + 生产环境变量

**问题**：`docker-compose.yml` 无资源限制（`deploy.resources.limits` 缺失）、无日志轮转配置（日志无限增长撑满磁盘）、未设置 `AI_TEST_ENV=production` 和 `JWT_SECRET` 等生产必需环境变量。

**修复内容**：

1. 新增 `deploy.resources.limits`（memory: 2G, cpus: 2.0）和 `reservations`（memory: 512M），防止单容器吃光宿主机资源。
2. 新增 `logging` 配置：`json-file` 驱动 + `max-size: 50m` + `max-file: 5`，日志最多占用 250MB 后自动轮转。
3. `healthcheck` 新增 `start_period: 30s`，冷启动期间不判定健康状态。
4. `environment` 新增 `AI_TEST_ENV=production`、`JWT_SECRET`、`ADMIN_USERNAME`、`ADMIN_PASSWORD`、`WEBHOOK_SECRET` 透传。

**修改文件**：`docker-compose.yml`

---

### P0-5：Webhook 端点添加 HMAC 签名验证

**问题**：`web/api/webhooks.py` 豁免 JWT 认证，且基类 `BaseAdapter.verify_signature` 默认实现直接返回 `True`（无签名验证）。任何人都可以伪造 webhook 请求。

**修复内容**：

1. 新增全局 HMAC-SHA256 签名验证层 `_verify_global_signature`，使用 `WEBHOOK_SECRET` 环境变量作为预共享密钥。
2. 所有 webhook 请求必须携带 `X-Webhook-Signature` 头，值为 `HMAC-SHA256(WEBHOOK_SECRET, body)` 的 hex digest。
3. 使用 `hmac.compare_digest` 进行常量时间比较，防止时序攻击。
4. 未配置 `WEBHOOK_SECRET` 时拒绝所有 webhook 请求（安全默认，不静默放行）。
5. 保留原有适配器级签名验证作为第二层防线。

**修改文件**：`web/api/webhooks.py`

---

## 二、P1 重要修复（上线后第一周内完成的技术债）

### P1-1：SQLite 写并发改善

**问题**：`busy_timeout=5000ms` 在两个 Pipeline 并发执行时容易超时报 `database is locked`，导致步骤状态静默丢失。

**修复内容**：将 `PRAGMA busy_timeout` 从 5000ms 提升到 15000ms，给写冲突更多排队等待时间。同时 `db/session.py` 已预留 PostgreSQL 的 `pool_pre_ping` + `pool_recycle` 配置，未来迁移到 PostgreSQL 时可彻底解决写并发瓶颈。

**修改文件**：`db/session.py`

---

### P1-2：Docker Secrets 密钥管理（.env.example 更新）

**问题**：`.env` 文件明文存储真实 API Key 和 JWT 密钥，存在泄露风险。`.env.example` 缺少 `ADMIN_PASSWORD`、`WEBHOOK_SECRET` 等新增环境变量的说明。

**修复内容**：

1. `.env.example` 全面重写，新增 `ADMIN_USERNAME` / `ADMIN_PASSWORD`、`WEBHOOK_SECRET` 配置项及安全说明。
2. 添加 Docker Secrets 使用指南：通过 `docker secret create` 创建密钥，应用侧从 `/run/secrets/<name>` 文件读取，避免明文环境变量。
3. 添加密钥生成方式说明（`python -c "import secrets; print(secrets.token_urlsafe(48))"`）。

**修改文件**：`.env.example`

---

### P1-3：数据库自动备份 cron 配置

**问题**：`scripts/db_backup.py` 存在但无定时任务配置，`data/backups/` 下仅有一个手动备份文件。生产环境无自动备份机制，DB 损坏后无法恢复。

**修复内容**：

新增 `deploy/backup_cron.example` 文件，提供 crontab 配置模板：
- 每 6 小时执行一次 SQLite 在线备份，保留最近 7 份。
- 每周日凌晨执行一次完整备份，保留 4 份周备份。
- 适配 Docker 部署（`docker compose exec`）和裸机部署两种场景。
- 日志输出到 `/var/log/ai-test-backup.log`。

**修改文件**：`deploy/backup_cron.example`（新建）

---

### P1-4：提升测试覆盖率门槛

**问题**：CI 流水线 `--cov-fail-under=50` 门槛过低，生产级系统应至少 80% 行覆盖 + 70% 分支覆盖。当前基线 69%，50% 的门槛无法防止覆盖率退化。

**修复内容**：将 `.github/workflows/test.yml` 中的 `--cov-fail-under` 从 50 提升到 75，注释同步更新。

**修改文件**：`.github/workflows/test.yml`

---

### P1-5：添加 CORS 中间件

**问题**：代码中完全没有添加 `CORSMiddleware`。Vue 前端与后端不同源部署时，所有请求会被浏览器 CORS 策略阻断。

**修复内容**：在 `web/app.py` 中 CSRF 中间件之后添加 CORS 中间件，从 `config.yaml` 的 `security.cors_origins` 读取白名单。空列表时不启用 CORS（默认安全），配置了具体域名时才允许跨域。允许的方法限定为 GET/POST/PUT/DELETE，允许的头部限定为 Authorization/Content-Type/X-CSRF-Token。

**修改文件**：`web/app.py`

---

### P1-6：SSE 连接泄漏防护

**问题**：`web/api/sse.py` 的 `event_generator` 依赖 `request.is_disconnected()` 检测客户端断开，但无法检测 TCP 半开连接（客户端网络异常断开但 TCP 层面未通知）。SSE 连接会泄漏，长期运行后耗尽资源。

**修复内容**：

1. 新增 `SSE_MAX_LIFETIME = 1800.0`（30 分钟）常量。
2. `event_generator` 记录连接开始时间，每次循环检查是否超过最大存活时间，超时后发送 `timeout` 事件并关闭流。
3. 客户端收到 timeout 事件后可自动重连，实现连接刷新。

**修改文件**：`web/api/sse.py`

---

### P1-7：`datetime.utcnow()` 迁移到 `datetime.now(UTC)`

**问题**：`datetime.utcnow()` 在 Python 3.12+ 已弃用，返回的是 naive datetime（无时区信息），可能导致时区比较错误。虽然当前 `pyproject.toml` 要求 `>=3.11`，但应预防升级。

**修复内容**：全局替换所有 `datetime.utcnow()` 为 `datetime.now(UTC)`（from `datetime import UTC, datetime`）。SQLAlchemy 模型中的 `default=datetime.utcnow` 改为 `default=lambda: datetime.now(UTC)`（lambda 延迟求值）。

**修改文件**：
- `db/models.py`（5 处）
- `db/repository.py`（2 处）
- `web/services/user_service.py`（1 处）
- `web/api/knowledge.py`（2 处）
- `core/multi_tenant.py`（1 处）

---

## 三、附加改进项

### 附加-1：LLM 断路器状态指标暴露

**问题**：`core/llm_gateway.py` 的断路器状态（`_circuits` 字典）未暴露为 Prometheus 指标，运维无法感知断路器是否触发。

**修复内容**：

1. `core/metrics.py` 新增 `LLM_CIRCUIT_BREAKER_STATE` Gauge 指标（label: provider），值为 0=closed / 1=open / 2=half_open。
2. 新增 `record_circuit_breaker_state(provider, state)` 函数，异常安全。
3. `core/llm_gateway.py` 在断路器状态变更时调用 `record_circuit_breaker_state`：熔断时记 `"open"`，半开探测时记 `"half_open"`，恢复时记 `"closed"`。

**修改文件**：`core/metrics.py`、`core/llm_gateway.py`

---

### 附加-2：EventBus 队列满时记录 WARN 日志

**问题**：`web/services/event_bus.py` 在队列满时静默丢弃旧事件，运维无法感知事件丢失。

**修复内容**：在 `publish` 和 `publish_sync` 方法的队列满丢弃逻辑中，新增 `logging.warning` 调用，记录 `event_queue_full` / `event_queue_full_sync` 事件及 topic 名称，便于排查 SSE 事件丢失问题。

**修改文件**：`web/services/event_bus.py`

---

### 附加-3：`TaskManager.MAX_WORKERS` 配置生效

**问题**：`web/services/task_manager.py` 中 `MAX_WORKERS = 2` 是类级硬编码常量，而 `config.yaml` 的 `pipeline.max_concurrent` 配置项实际上没有被读取，配置失效。

**修复内容**：将 `MAX_WORKERS` 从类级常量改为实例属性，在 `__init__` 中从 `config.yaml` 的 `pipeline.max_concurrent` 读取（默认 2），使配置真正生效。

**修改文件**：`web/services/task_manager.py`

---

## 四、修改文件清单

| 文件 | 修复项 | 变更类型 |
|---|---|---|
| `Dockerfile` | P0-1, P0-4 | 修改：补全 production extras + 非 root 用户 + healthcheck 优化 |
| `docker-compose.yml` | P0-4 | 重写：资源限制 + 日志轮转 + 生产环境变量透传 |
| `web/services/user_service.py` | P0-2, P1-7 | 修改：管理员凭证环境变量化 + datetime 迁移 |
| `core/pipeline.py` | P0-3 | 修改：save_state 原子写入 |
| `web/api/webhooks.py` | P0-5 | 重写：全局 HMAC 签名验证层 |
| `db/session.py` | P1-1 | 修改：busy_timeout 5000→15000 |
| `.env.example` | P1-2 | 重写：新增 ADMIN_PASSWORD/WEBHOOK_SECRET + Docker Secrets 指南 |
| `deploy/backup_cron.example` | P1-3 | 新建：自动备份 crontab 模板 |
| `.github/workflows/test.yml` | P1-4 | 修改：覆盖率门槛 50→75 |
| `web/app.py` | P1-5 | 修改：添加 CORS 中间件 |
| `web/api/sse.py` | P1-6 | 修改：SSE 连接超时保护 |
| `db/models.py` | P1-7 | 修改：datetime.utcnow → datetime.now(UTC) |
| `db/repository.py` | P1-7 | 修改：datetime.utcnow → datetime.now(UTC) |
| `web/api/knowledge.py` | P1-7 | 修改：datetime.utcnow → datetime.now(UTC) |
| `core/multi_tenant.py` | P1-7 | 修改：datetime.utcnow → datetime.now(UTC) |
| `core/metrics.py` | 附加-1 | 修改：新增断路器 Gauge 指标 + record_circuit_breaker_state |
| `core/llm_gateway.py` | 附加-1 | 修改：断路器状态变更时记录指标 |
| `web/services/event_bus.py` | 附加-2 | 修改：队列满时记录 WARN 日志 |
| `web/services/task_manager.py` | 附加-3 | 修改：MAX_WORKERS 从配置读取 |
| `tests/test_auth_jwt.py` | P0-2 适配 | 修改：显式传入测试凭证，不再依赖已移除的硬编码密码 |
| `tests/test_boundary.py` | 附加-3 适配 | 修改：MAX_WORKERS 从类属性改为实例属性，测试同步适配 |
| `tests/test_task_manager.py` | 附加-3 适配 | 修改：MAX_WORKERS 断言从类级改为实例级 |

---

## 五、上线验证 Checklist

部署前逐项验证：

- [ ] `docker compose build` 成功，镜像大小 < 500MB
- [ ] `docker run --rm <image> python -c "import structlog, slowapi, prometheus_fastapi_instrumentator; print('OK')"` 无 ImportError
- [ ] 容器以 `appuser` 用户运行：`docker exec <container> whoami` 输出 `appuser`
- [ ] `curl http://localhost:8080/metrics` 返回 Prometheus 格式文本
- [ ] 未设置 `ADMIN_PASSWORD` 时，启动日志包含随机生成的管理员密码
- [ ] 设置 `ADMIN_PASSWORD` 后，使用该密码可登录系统
- [ ] 未携带 `X-Webhook-Signature` 头的 webhook 请求返回 401
- [ ] `docker compose logs` 日志为 JSON 格式（structlog），包含 `trace_id` 字段
- [ ] `docker stats` 显示容器内存限制为 2G
- [ ] `config.yaml` 中修改 `pipeline.max_concurrent` 后，TaskManager 并发上限随之变化
- [ ] `curl http://localhost:8080/metrics | grep circuit_breaker` 能看到断路器状态指标
- [ ] 配置 `security.cors_origins` 后，跨域请求返回正确的 CORS 头
- [ ] SSE 连接 30 分钟后自动关闭并发送 timeout 事件
- [ ] `python scripts/db_backup.py --dry-run` 能正常执行
