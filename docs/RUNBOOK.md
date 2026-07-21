# AI 测试用例生成系统 — 生产运维 Runbook（应急处置手册）

> **面向对象**：值班人员（具备基本 Linux 技能，不一定了解项目细节）
> **适用版本**：v2.1.0 及以上
> **核心定位**：单机或小规模部署的内部工具，SQLite + uvicorn + Docker

---

## 0. 常用速查

### 0.1 关键路径与端口

| 项 | 值 |
|---|---|
| 项目根目录 | `/app`（容器内） / 项目克隆目录（裸机） |
| SQLite 数据文件 | `data/app.db`（容器内 `/app/data/app.db`） |
| 需求文档上传目录 | `web/uploads/`（容器内 `/app/uploads`） |
| Pipeline 产物目录 | `output/` |
| 应用端口 | `8080` |
| 日志输出 | stdout（structlog JSON 格式，docker logs / journalctl 可查） |

### 0.2 常用运维命令

```bash
# 查看服务状态（Docker 部署）
docker compose ps
docker compose logs --tail=200 app

# 查看服务状态（裸机 systemd 假设服务名 ai-test）
systemctl status ai-test
journalctl -u ai-test -n 200 --no-pager

# 健康检查三件套
curl -fsS http://localhost:8080/health/live   # 进程存活（liveness）
curl -fsS http://localhost:8080/health/ready  # 依赖就绪（readiness，DB/LLM/KB）
curl -fsS http://localhost:8080/health        # 向后兼容，等价 /health/ready

# Prometheus 指标
curl -s http://localhost:8080/metrics | grep -E '^(llm_request|llm_provider_fallback|http_requests)'

# 重启
docker compose restart app
# 或裸机
systemctl restart ai-test
```

### 0.3 探针语义说明

| 探针 | 检查内容 | 失败时动作 |
|---|---|---|
| `/health/live` | 仅进程是否响应 | 失败 → 重启进程 |
| `/health/ready` | DB / LLM / KB 依赖连通性 | 失败（返回 503）→ 摘除流量（不重启） |
| `/health` | 等价 `/health/ready` | 同上 |

`/health/ready` 返回体示例：

```json
{
  "status": "degraded",
  "version": "2.1.0",
  "checks": {
    "database": "ok",
    "llm": "error: timeout",
    "knowledge_base": "ok"
  }
}
```

各 `checks.*` 值含义：`ok` / `disabled` / `not_configured` 视为通过；其他字符串（尤其 `error: ...`）视为该依赖异常。

### 0.4 Prometheus 关键指标

| 指标 | 含义 | 关注点 |
|---|---|---|
| `llm_request_duration_seconds_bucket` | LLM 单次调用耗时直方图 | p99 持续上升 → 上游变慢 |
| `llm_provider_fallback_total` | Provider 故障转移次数 | 突增 → 主 Provider 异常 |
| `llm_request_total{status="error"}` | LLM 失败调用数 | 持续增长 → 介入场景 2 |
| `http_requests_total` / `http_request_duration_seconds` | HTTP 维度（由 instrumentator 自动采集） | 5xx 突增 → 服务异常 |

### 0.5 关键设计参数（处置时需牢记）

- **workers: 1**（SQLite 模式强制单 worker，并发写受限）
- **TaskManager MAX_WORKERS = 2**（同时只允许 2 个 Pipeline 运行，超出会拒绝）
- **SQLite WAL + busy_timeout=5000ms**（写冲突最多等 5 秒，仍冲突才报 `database is locked`）
- **LLM 断路器**：连续失败 3 次熔断 60s，半开探测恢复
- **LLM 重试**：单 Provider 默认重试 2 次，间隔 2s
- **Docker restart: unless-stopped**，healthcheck 间隔 30s，超时 10s，重试 3 次

### 0.6 升级/回滚前置原则

- 任何升级前先备份 `data/app.db`
- 生产环境必须设置 `AI_TEST_ENV=production` 和 `JWT_SECRET`（≥32 字符）
- 涉及 DB schema 变更必须先跑 alembic 迁移

---

## 1. 数据库故障

### 1.1 SQLite 锁冲突（`database is locked`）

#### 现象
- 日志频繁出现：`sqlite3.OperationalError: database is locked`
- Pipeline 步骤写入 DB 时失败（但 Pipeline 主流程不阻塞，仅记录 WARN："DB 持久化失败（不影响执行）"）
- 前端任务列表可能短暂不更新最新状态
- `/health/ready` 的 `checks.database` 通常仍为 `ok`（读没锁，锁的是写）

#### 诊断步骤
```bash
# 1. 查看最近 200 行日志，过滤锁相关错误
docker compose logs --tail=500 app | grep -iE 'locked|database|sqlite'

# 2. 检查当前活跃任务数（>2 说明并发超限）
curl -s http://localhost:8080/api/v1/pipeline/list | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print('running:', d.get('all_stats',{}).get('running',0))"

# 3. 检查 WAL 文件大小（异常大说明有长事务未提交）
ls -lh data/app.db data/app.db-wal data/app.db-shm

# 4. 检查是否有长时间持有的 DB 连接（如有进程级排查需求）
# 容器内：
docker compose exec app python3 -c "
from db.session import get_engine
import sqlite3
conn = sqlite3.connect('data/app.db')
print('journal_mode:', conn.execute('PRAGMA journal_mode').fetchone())
print('busy_timeout:', conn.execute('PRAGMA busy_timeout').fetchone())
"
```

#### 处置步骤
1. **短期缓解**：错峰使用，避免 2+ 用户同时启动 Pipeline（系统设计 `MAX_WORKERS=2`，并发触发 pipeline 是最常见诱因）
2. **若任务卡死**：重启服务让 startup 清理逻辑把 `running/paused/pending` 标记为 `interrupted`：
   ```bash
   docker compose restart app
   ```
   （重启不会丢已完成步骤，可续跑任务会自动重建到内存 `paused` 状态）
3. **WAL 文件膨胀**（>100MB）：等待所有连接释放后 checkpoint：
   ```bash
   docker compose exec app python3 -c "
   import sqlite3; c=sqlite3.connect('data/app.db'); c.execute('PRAGMA wal_checkpoint(TRUNCATE)'); print('checkpoint done')
   "
   ```
   若 checkpoint 不收敛，说明有未关闭的连接，需重启服务。

#### 验证方法
```bash
# 1. 重启后确认启动清理生效
docker compose logs --tail=50 app | grep -E '僵尸任务|interrupted|持久化恢复'
# 2. 触发一次健康检查
curl -fsS http://localhost:8080/health/ready | python3 -m json.tool
# 3. 再次启动一个测试 Pipeline，观察是否仍报 locked
```

---

### 1.2 SQLite 文件损坏

#### 现象
- 启动即失败，日志含：`database disk image is malformed` / `file is not a database` / `no such table: pipelines`
- `/health/ready` 的 `checks.database` 变为 `error: ...`
- 所有 API 返回 500

#### 诊断步骤
```bash
# 1. 完整性检查（容器内执行）
docker compose exec app python3 -c "
import sqlite3
c = sqlite3.connect('data/app.db')
print('integrity:', c.execute('PRAGMA integrity_check').fetchone())
"

# 2. 查看文件大小是否为 0 或异常小
ls -lh data/app.db

# 3. 查看磁盘是否曾满过（见场景 5）
df -h

# 4. 检查最近的备份
ls -lh data/ | grep -i bak
```

#### 处置步骤
1. **立即停止服务**避免进一步写入：
   ```bash
   docker compose stop app
   ```
2. **保留现场**用于事后分析：
   ```bash
   cp data/app.db data/app.db.corrupt.$(date +%s)
   cp data/app.db-wal data/app.db-wal.corrupt.$(date +%s) 2>/dev/null || true
   ```
3. **尝试恢复**（用 `.recover` 命令导出到新库）：
   ```bash
   docker compose run --rm --no-deps app python3 -c "
   import sqlite3
   src = sqlite3.connect('data/app.db.corrupt.$(date +%s)')
   dst = sqlite3.connect('data/app.db.recovered')
   src.backup(dst)
   print('recover attempted')
   "
   ```
   或直接用 sqlite3 CLI：`sqlite3 data/app.db ".recover" > /tmp/dump.sql && sqlite3 data/app.db.new < /tmp/dump.sql`
4. **无可用恢复 → 用最近备份覆盖**：
   ```bash
   cp data/app.db.bak.<timestamp> data/app.db
   rm -f data/app.db-wal data/app.db-shm   # 清掉旧 WAL，防止 schema 不一致
   ```
5. **无备份 → 重建空库**（丢失历史 Pipeline 记录，但 `output/` 下的产物文件仍在）：
   ```bash
   rm -f data/app.db data/app.db-wal data/app.db-shm
   docker compose up -d app    # 启动时 Base.metadata.create_all 会重建空表
   ```
6. **重新执行 alembic 迁移**确保 schema 一致：
   ```bash
   docker compose exec app alembic upgrade head
   ```

#### 验证方法
```bash
docker compose exec app python3 -c "import sqlite3; print(sqlite3.connect('data/app.db').execute('PRAGMA integrity_check').fetchone())"
# 应输出 ('ok',)
curl -fsS http://localhost:8080/health/ready | python3 -m json.tool
# checks.database 应为 ok
```

---

### 1.3 磁盘满导致 DB 写入失败

#### 现象
- 日志出现 `OSError: [Errno 28] No space left on device` 或 SQLite 的 `disk I/O error`
- 任务持久化失败，前端任务列表停滞
- 新上传文件失败

#### 诊断步骤
```bash
df -h                       # 查看挂载点使用率
du -sh data/ output/ uploads/   # 定位大目录
docker system df            # 看 Docker 层占用
```

#### 处置步骤
见 **场景 5：磁盘空间告警**。处置完成后重启服务，让 startup 清理逻辑把中断任务恢复为 `interrupted`，可续跑的自动重建。

#### 验证方法
```bash
curl -fsS http://localhost:8080/health/ready
df -h <挂载点>   # 使用率回到安全水位（建议 < 80%）
```

---

## 2. LLM 服务不可用

### 2.1 主 + 备 Provider 全部不可用

#### 现象
- `/health/ready` 的 `checks.llm` 变为 `error: ...` 或 `not_configured`
- Pipeline 执行到 Step 1（需求分析）/ Step 4（生成用例）等 AI 步骤时报 `LLMError`
- Prometheus 指标 `llm_request_total{status="error"}` 持续增长
- Step4 会自动降级到脚本模板生成（质量下降，日志有 WARN："LLM 不可用，降级到脚本模板生成"）

#### 诊断步骤
```bash
# 1. 查看健康检查的 LLM 依赖状态
curl -s http://localhost:8080/health/ready | python3 -c "import sys,json;print(json.load(sys.stdin)['checks'].get('llm'))"

# 2. 查看最近 LLM 错误
docker compose logs --tail=500 app | grep -iE 'LLMError|provider|timeout|429|quota|余额'

# 3. 查看断路器/故障转移情况
curl -s http://localhost:8080/metrics | grep -E 'llm_provider_fallback_total|llm_request_total'

# 4. 直接测试上游连通性（替换为实际 base_url 和 key）
curl -i --max-time 10 -H "Authorization: Bearer $LLM_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"hi"}]}' \
     ${LLM_BASE_URL:-https://api.deepseek.com/v1}/chat/completions

# 5. 查看当前生效的 LLM 配置
curl -s http://localhost:8080/api/v1/config | python3 -c "import sys,json;d=json.load(sys.stdin);print(json.dumps(d.get('llm',{}),indent=2,ensure_ascii=False))"
```

#### 处置步骤
1. **区分故障类型**（按诊断步骤 4 的 HTTP 响应码）：
   - **超时 / 网络不通**（curl 无响应或 5xx）→ 等 60s 断路器半开探测自动恢复；若长时间不恢复，检查出口网络/防火墙
   - **401 / 403**（鉴权失败）→ `LLM_API_KEY` 失效或被禁用，更换 Key：
     ```bash
     # 编辑 .env 或 docker-compose.yml 的 environment
     # 改 LLM_API_KEY 后重启
     docker compose up -d app
     ```
   - **429 / 限流**（rate limit）→ 降低并发或等待上游配额恢复；临时切到备 Provider
   - **额度耗尽 / 余额不足**（通常响应体含 `insufficient_quota` / `余额不足`）→ 充值或切换 Provider
2. **切换 Provider**（通过 WebUI 设置页或 API，热生效，新任务使用新配置）：
   ```bash
   curl -X PUT http://localhost:8080/api/v1/config \
     -H "Authorization: Bearer <JWT>" -H "Content-Type: application/json" \
     -d '{"llm":{"provider":"glm","model":"glm-4-flash","base_url":"https://open.bigmodel.cn/api/paas/v4","api_key":"<新key>"}}'
   ```
   注意：LLM 配置修改只对**新任务**生效，正在运行的 Pipeline 仍用旧配置。
3. **配置备 Provider（fallback 链）**：编辑 `config.yaml` 的 `llm.fallback` 段，添加备选 Provider 列表，重启服务。fallback 链工作方式：
   - 主 Provider 连续失败 3 次 → 熔断 60s
   - 熔断期间自动跳到下一个备 Provider
   - 60s 后主 Provider 半开探测，成功则恢复
4. **完全无可用 LLM 时的降级运行**：Pipeline 仍可运行，AI 步骤会降级到脚本模板（日志 WARN），产物质量下降但流程不中断。

#### 验证方法
```bash
# 1. 健康检查恢复
curl -s http://localhost:8080/health/ready | python3 -c "import sys,json;print(json.load(sys.stdin)['checks'].get('llm'))"
# 应为 ok 或 not_configured（若有意禁用 LLM）

# 2. 指标恢复
curl -s http://localhost:8080/metrics | grep 'llm_request_total.*status="success"'
# 应看到新的 success 计数

# 3. 启动一个测试 Pipeline 验证端到端可用
```

---

### 2.2 LLM 响应超时（慢但可用）

#### 现象
- Pipeline 执行缓慢，单步耗时 >2 分钟
- Prometheus `llm_request_duration_seconds_bucket` 的 p99 持续上升
- 偶发 `LLMError`（默认 timeout=120s）

#### 诊断与处置
```bash
# 查看耗时分布
curl -s http://localhost:8080/metrics | grep llm_request_duration_seconds | tail -20
```
1. 若上游普遍变慢：在 `config.yaml` 的 `llm` 段调大 `timeout`（如 180）并重启
2. 若是限流前兆：降低并发（确保同时只有 1 个 Pipeline 在跑）
3. 检查出口带宽 / 代理配置（容器内 `curl --max-time 10 ${LLM_BASE_URL}` 对比）

---

## 3. 应用启动失败

### 3.1 JWT_SECRET 缺失或弱密钥（生产环境）

#### 现象
- 容器启动后立即退出（`docker compose ps` 显示 Restarting 或 Exited）
- 日志含明确错误（进程在 `SystemExit` 前打印）：
  ```
  ❌ 生产环境必须配置 JWT_SECRET 环境变量（>=32 字符）。拒绝启动。
  ```
  或：
  ```
  ❌ 生产环境 JWT_SECRET 不安全（< 32 字符或为默认值）。拒绝启动。
  ```

#### 诊断步骤
```bash
docker compose logs app | grep -A2 -iE 'JWT_SECRET|拒绝启动'
# 确认 AI_TEST_ENV 取值
docker compose exec app printenv AI_TEST_ENV JWT_SECRET 2>/dev/null || echo "容器未运行，改用配置文件检查"
grep -E 'AI_TEST_ENV|JWT_SECRET' .env docker-compose.yml
```

#### 处置步骤
1. 生成一个安全的密钥：
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(48))"
   # 输出类似：xK9...（>=32 字符）
   ```
2. 写入 `.env`（或 docker-compose 的 environment）：
   ```bash
   echo "JWT_SECRET=<上一步输出>" >> .env
   echo "AI_TEST_ENV=production" >> .env   # 生产必须
   ```
3. 重启：
   ```bash
   docker compose up -d app
   ```

#### 验证方法
```bash
docker compose ps            # 状态应为 Up (healthy)
curl -fsS http://localhost:8080/health/live
```

> **注意**：非生产环境（`AI_TEST_ENV` 未设或为 `development`）会回退到不安全默认密钥并打印 WARN，不会拒绝启动。生产环境务必设置 `AI_TEST_ENV=production`。

---

### 3.2 端口 8080 被占用

#### 现象
- 启动日志含：`[Errno 98] Address already in use` 或 `uvicorn.error | ERROR | ... port 8080`
- 容器反复重启

#### 诊断步骤
```bash
# 宿主机
sudo lsof -i :8080
# 或
ss -tlnp | grep 8080
```

#### 处置步骤
1. **方案 A：停掉占用进程**
   ```bash
   sudo kill <PID>   # 谨慎，确认是哪个服务
   ```
2. **方案 B：改用其他端口**（修改 `docker-compose.yml` 的端口映射）
   ```yaml
   ports:
     - "8081:8080"   # 宿主机 8081 → 容器 8080
   ```
   随后所有访问地址改为 `http://host:8081`，并更新前端反向代理（如有）。
3. 重启：
   ```bash
   docker compose up -d app
   ```

#### 验证方法
```bash
curl -fsS http://localhost:8080/health/live   # 或新端口
```

---

### 3.3 Python 依赖缺失 / 导入失败

#### 现象
- 启动日志含 `ModuleNotFoundError` / `ImportError`
- 常见缺失：`fastapi`、`uvicorn`、`sqlalchemy`、`openai`、`openpyxl`、`prometheus_fastapi_instrumentator`
- 容器退出码非 0

#### 诊断步骤
```bash
docker compose logs app | grep -iE 'ModuleNotFoundError|ImportError|No module'
# 确认镜像构建方式
docker compose exec app pip list 2>/dev/null | grep -iE 'fastapi|uvicorn|openai' || echo "容器未运行"
```

#### 处置步骤
1. **Docker 部署**：重建镜像（多阶段构建可能漏了 extras）：
   ```bash
   docker compose build --no-cache app
   docker compose up -d app
   ```
   Dockerfile 安装的是 `.[web,xmind,excel,db]`，确认 `pyproject.toml` 的 extras 完整。
2. **裸机部署**：在项目根目录重装：
   ```bash
   # 推荐用 uv（项目已用 uv.lock）
   uv sync --extra web --extra xmind --extra excel --extra db
   # 或 pip
   pip install -e ".[web,xmind,excel,db]"
   ```
3. **可选依赖缺失**（`prometheus_fastapi_instrumentator` / `structlog`）：代码已 try/except 优雅降级，缺失只会让 `/metrics` 或结构化日志不可用，不会阻塞启动。生产建议补装。

#### 验证方法
```bash
docker compose ps   # Up (healthy)
curl -fsS http://localhost:8080/health/ready
```

---

## 4. Pipeline 任务异常中断

### 4.1 进程被杀（OOM / 人工 kill / 宿主机重启）

#### 现象
- 任务列表中存在大量 `interrupted` 状态的任务
- 用户反馈"任务跑着跑着就没了"
- 日志可能有 OOM 记录（`oom-kill`）或容器重启记录

#### 诊断步骤
```bash
# 1. 查看是否有 OOM（Docker）
docker inspect <container_id> | grep -A5 OOMKilled
dmesg | grep -i 'out of memory' | tail

# 2. 查看任务状态分布
curl -s http://localhost:8080/api/v1/pipeline/list | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('stats:', d.get('all_stats',{}))
for t in d.get('items',[])[:10]:
    print(f\"  {t.get('pipeline_id','?')} status={t.get('status')} steps={t.get('completed_steps',0)}/{t.get('total_steps','?')}\")"

# 3. 查看启动时的清理日志
docker compose logs --tail=100 app | grep -E '僵尸任务|interrupted|持久化恢复|启动清理'
```

#### 处置步骤
**大多数情况下无需手动干预**——系统设计为自恢复：

1. **启动清理（自动）**：服务重启时，`lifespan` 的 startup 会把所有 `running` / `pending` / `paused` 状态的任务自动标记为 `interrupted`，并在 `error` 字段写入"服务重启，任务中断"。
2. **持久化恢复（自动）**：对 `interrupted` 中满足以下条件的任务，系统自动重建到内存 `paused` 状态：
   - `requirements_path` 对应的文件仍存在（uploads 未被清理）
   - 已有至少 1 个完成的步骤（`completed_steps` 非空）
3. **用户手动续跑**：前端任务详情页点"继续执行"按钮，或调用 API：
   ```bash
   curl -X POST http://localhost:8080/api/v1/pipeline/<pipeline_id>/resume \
     -H "Authorization: Bearer <JWT>"
   ```
   resume 会从最近完成的步骤之后继续（`auto` 模式，跳过人工检查点）。

4. **无法自动恢复的任务**（`requirements_path` 文件已被清理）：
   - 任务保持 `interrupted`，`output/<pipeline_id>/` 下的产物仍可下载
   - 如需重跑，请新建任务重新上传需求文档

5. **OOM 根因处置**：
   ```bash
   # 查看容器内存限制
   docker stats <container>
   # 适当调高 docker-compose.yml 的 deploy.resources.limits.memory
   # 或排查是否有需求文档过大导致 prompt 膨胀
   ```

#### 验证方法
```bash
# 1. 重启后确认恢复日志
docker compose logs --tail=50 app | grep -E '持久化恢复|recovered'
# 2. 任务列表中 interrupted 任务应能通过前端 resume
# 3. 续跑后状态变为 running → done/paused
curl -s "http://localhost:8080/api/v1/pipeline/<id>/progress" | python3 -c "import sys,json;print(json.load(sys.stdin)['status'])"
```

---

### 4.2 任务卡在 `running` 状态（假死）

#### 现象
- 任务状态长时间显示 `running`，进度条不动
- 日志最后一条停留在某个 Step 的开始，无新输出
- 后台线程可能已挂（死循环、LLM 无限重试、外部资源挂起）

#### 诊断步骤
```bash
# 1. 查看任务进度（重点看 logs 末尾）
curl -s "http://localhost:8080/api/v1/pipeline/<pipeline_id>/progress" | python3 -m json.tool

# 2. 看日志是否停在 LLM 调用
docker compose logs --tail=200 app | grep -iE 'LLM|retry|timeout'

# 3. 看是否有活跃的 Pipeline 线程（Python 线程名形如 Thread-N）
docker compose exec app python3 -c "
import threading
for t in threading.enumerate():
    if t.name != 'MainThread': print(t.name, t.is_alive())
"

# 4. 确认 LLM 是否在熔断中
curl -s http://localhost:8080/metrics | grep llm_provider_fallback
```

#### 处置步骤
1. **先尝试优雅取消**（协作式，在下一个步骤间隙生效）：
   ```bash
   curl -X POST http://localhost:8080/api/v1/pipeline/<pipeline_id>/cancel \
     -H "Authorization: Bearer <JWT>"
   ```
   等待 30-60s，任务应转为 `cancelled`。
2. **取消无效 → 重启服务**（最直接）：
   ```bash
   docker compose restart app
   ```
   重启后 startup 清理会把卡住的任务标记为 `interrupted`，可续跑的自动重建为 `paused`，用户可 resume。
3. **根因排查**：
   - 若是 LLM 超时：按场景 2 处理上游
   - 若是死循环：保留日志，提 issue 给开发
   - 若是资源耗尽：检查内存/磁盘

#### 验证方法
```bash
# 重启后任务状态
curl -s "http://localhost:8080/api/v1/pipeline/<id>/progress" | python3 -c "import sys,json;d=json.load(sys.stdin);print('status:',d['status'],'steps:',d['completed_steps'])"
# 应为 interrupted 或 paused（可 resume）
```

---

## 5. 磁盘空间告警（output / uploads 膨胀）

### 5.1 现象
- 监控告警：磁盘使用率 >85%
- 新上传失败：`OSError: [Errno 28] No space left on device`
- Pipeline 写产物失败
- 严重时触发场景 1.3（DB 写入失败）

### 5.2 诊断步骤
```bash
# 1. 总览
df -h

# 2. 定位大目录
du -sh output/ uploads/ data/ 2>/dev/null | sort -rh

# 3. output 下各 Pipeline 目录大小（找出异常大的）
du -sh output/*/ 2>/dev/null | sort -rh | head -20

# 4. uploads 文件数与总量
ls uploads/ | wc -l
du -sh uploads/

# 5. Docker 层占用（镜像/容器/卷）
docker system df -v
```

### 5.3 处置步骤

#### 方法 A：使用项目自带的清理脚本（推荐，安全）

项目提供 `scripts/clean_workspace.py`，**默认 dry-run**（只报告不删除），加 `--execute` 才实际删除。

```bash
# 1. 先 dry-run 看会清理什么
docker compose exec app python scripts/clean_workspace.py

# 输出示例：
# 📤 uploads 清理：
#    保留：被活跃任务引用的 + 3 天内的文件
#    总文件: 150 | 保留(引用): 8 | 将删除: 42 | 释放: 12.3 MB
# 📁 output 清理：
#    删除文件数 ≤ 1 的空目录（interrupted 任务遗留）
#    总目录: 80 | 将删除: 23 | 保留: 57 | 释放: 0.5 MB

# 2. 确认无误后执行
docker compose exec app python scripts/clean_workspace.py --execute

# 3. 可调参数（按需）
docker compose exec app python scripts/clean_workspace.py \
  --days 7 \           # uploads: 超过 7 天才清（默认 3）
  --max-files 2 \      # output: 文件数 ≤2 的目录视为空（默认 1）
  --execute
```

**清理策略说明**（脚本已内置安全逻辑）：
- `uploads/`：只删超过 `--days` 天 **且** 不被任何活跃任务（`interrupted` / `paused` / `running` / `pending`）引用的文件。被引用的文件一律保留（否则 resume 会失败）。
- `output/`：只删文件数 ≤ `--max-files` 的空/近空目录（通常是 interrupted 任务遗留）。有完整产物的目录（默认 ≥2 个文件）保留。
- 保留 `.gitkeep`，不删目录本身。

#### 方法 B：手动清理已确认可删的任务

```bash
# 1. 查看已完成/取消的任务（其 output 可归档后删）
curl -s http://localhost:8080/api/v1/pipeline/list | python3 -c "
import sys,json
d=json.load(sys.stdin)
for t in d.get('items',[]):
    if t.get('status') in ('done','cancelled','error'):
        print(t['pipeline_id'], t['status'])
"

# 2. 归档重要产物后删除
tar -czf /backup/output-$(date +%Y%m%d).tar.gz output/<pipeline_id>/
rm -rf output/<pipeline_id>/
```

#### 方法 C：Docker 系统清理（镜像/停止的容器）

```bash
docker system prune -a --volumes
# ⚠️ 谨慎：会删除未被 docker-compose 引用的卷。确认 data/ 有挂载到宿主机 volume（docker-compose.yml 已挂 ./data:/app/data）
```

### 5.4 验证方法
```bash
df -h <挂载点>          # 使用率回到安全水位（建议 < 80%）
du -sh output/ uploads/ # 应明显下降
# 再次 dry-run 确认无大量待删
docker compose exec app python scripts/clean_workspace.py
```

### 5.5 长期建议
- 设置 cron 定期清理（如每天凌晨）：
  ```bash
  # crontab -e
  0 3 * * * cd /path/to/ai-test-system && docker compose exec -T app python scripts/clean_workspace.py --execute --days 7 >> /var/log/ai-test-cleanup.log 2>&1
  ```
- 监控 `output/` 增长趋势，设置磁盘告警阈值（85%）

---

## 6. 回滚操作

### 6.1 代码回滚（git revert / reset）

#### 适用场景
- 新版本引入 Bug，需快速回到上一个稳定版本
- 前提：有可回退的 git 历史，且 DB schema 未发生不兼容变更

#### 操作步骤
```bash
cd /path/to/ai-test-system

# 1. 备份当前状态（万一回滚也要能再前进）
git stash || git branch backup-pre-rollback-$(date +%Y%m%d)

# 2. 查看最近提交，确定回退目标
git log --oneline -20

# 3. 方案 A：用 revert（保留历史，生成反向提交，推荐生产用）
git revert <bad_commit_hash>   # 可多个
git push

# 4. 方案 B：用 reset（直接回到某版本，丢弃中间历史，适合紧急）
git reset --hard <stable_commit_hash>
# 注意：--hard 会丢失未提交改动，确认已备份

# 5. 重建并重启
docker compose build app
docker compose up -d app

# 6. 观察启动日志
docker compose logs -f --tail=50 app
```

#### 验证方法
```bash
curl -fsS http://localhost:8080/health/ready | python3 -c "import sys,json;d=json.load(sys.stdin);print('version:',d['version'])"
# 版本号应符合回退后的预期
```

---

### 6.2 DB Migration 回滚（alembic downgrade）

#### 适用场景
- 新版本带了 DB schema 变更（新增表/列/索引），回滚代码后需同步回滚 schema
- 本项目当前 migration 版本链：
  - `24d34db69863`（initial schema）
  - → `8ac84689a8a2`（add kb_configs table）
  - → `0bf0948203b6`（add missing composite indexes，当前 head）

#### ⚠️ 前置必做：备份 DB
```bash
docker compose stop app
cp data/app.db "data/app.db.bak.$(date +%Y%m%d-%H%M%S)"
docker compose start app   # 或保持停止状态做回滚
```

#### 诊断步骤
```bash
# 查看当前 migration 版本
docker compose exec app alembic current
# 查看版本历史
docker compose exec app alembic history --verbose
```

#### 操作步骤
```bash
# 1. 回退一个版本（推荐，最小步进）
docker compose exec app alembic downgrade -1

# 2. 回退到指定版本（更精确）
docker compose exec app alembic downgrade 8ac84689a8a2

# 3. 回退到初始版本（谨慎，会丢表）
docker compose exec app alembic downgrade 24d34db69863

# 4. 回退到 base（极度谨慎，清空所有迁移管理的 schema）
# docker compose exec app alembic downgrade base
```

#### 回滚失败处置
若 `downgrade` 失败（常见于 SQLite 对 ALTER TABLE 的限制），alembic 会报错并停止。此时：

1. **优先恢复备份**（最安全）：
   ```bash
   docker compose stop app
   cp data/app.db.bak.<timestamp> data/app.db
   rm -f data/app.db-wal data/app.db-shm
   docker compose start app
   ```
2. **如果只是回退到旧代码 + 旧 DB**：直接用备份的 `app.db` 覆盖即可，无需 alembic（旧代码与新 schema 不兼容时，旧 DB 反而最匹配）。

#### 验证方法
```bash
# 1. 确认 migration 版本
docker compose exec app alembic current
# 应为目标版本号

# 2. DB 完整性
docker compose exec app python3 -c "import sqlite3;print(sqlite3.connect('data/app.db').execute('PRAGMA integrity_check').fetchone())"

# 3. 应用健康
curl -fsS http://localhost:8080/health/ready

# 4. 抽查核心表存在
docker compose exec app python3 -c "
import sqlite3
c=sqlite3.connect('data/app.db')
for t in ['pipelines','pipeline_steps','artifacts','users']:
    print(t, c.execute(f'SELECT count(*) FROM {t}').fetchone())
"
```

---

### 6.3 完整回滚 Checklist（代码 + DB + 配置）

紧急全量回滚时，按顺序执行：

- [ ] 通知用户即将维护（如有）
- [ ] 停止服务：`docker compose stop app`
- [ ] 备份 DB：`cp data/app.db data/app.db.bak.$(date +%s)`
- [ ] 备份当前代码版本：`git branch backup-$(date +%Y%m%d)`
- [ ] 回退代码：`git reset --hard <stable_commit>` 或 `git revert <bad_commits>`
- [ ] 恢复匹配的 DB 备份（若有）**或** 执行 `alembic downgrade` 到匹配版本
- [ ] 检查 `.env` / `config.yaml` / `docker-compose.yml` 配置是否需同步回退
- [ ] 重建镜像：`docker compose build app`
- [ ] 启动：`docker compose up -d app`
- [ ] 验证：`curl -fsS http://localhost:8080/health/ready`
- [ ] 验证：启动一个测试 Pipeline 确认端到端
- [ ] 通知用户恢复

---

## 附录 A：环境变量速查

| 变量 | 作用 | 生产要求 |
|---|---|---|
| `AI_TEST_ENV` | 环境标识（`development` / `production`） | 必须为 `production` |
| `JWT_SECRET` | JWT 签名密钥 | ≥32 字符，生产强制（缺失/弱密钥拒绝启动） |
| `LLM_API_KEY` | LLM 服务 API Key | 必填（缺失则 LLM 步骤降级） |
| `LLM_BASE_URL` | LLM 服务地址 | 默认 `https://api.deepseek.com/v1` |
| `LLM_MODEL` | 模型名 | 默认 `deepseek-chat` |
| `DATABASE_URL` | 数据库 URL | 默认 `sqlite:///data/app.db` |
| `DATABASE_PATH` | SQLite 文件路径（覆盖 URL） | 默认 `<project>/data/app.db` |
| `OBSIDIAN_SSL_VERIFY` | Obsidian Local REST API 的 SSL 校验 | `true` / `false`，自签证书时设 `false` |

## 附录 B：日志关键词速查

| 日志关键词 | 含义 | 对应场景 |
|---|---|---|
| `database is locked` | SQLite 写冲突 | 场景 1.1 |
| `disk I/O error` / `No space left` | 磁盘满 | 场景 1.3 / 5 |
| `malformed` / `no such table` | DB 文件损坏 | 场景 1.2 |
| `LLMError` / `LLM 调用失败` | LLM 上游异常 | 场景 2 |
| `降级到脚本模板` | LLM 不可用，自动降级生成 | 场景 2.1（非致命） |
| `拒绝启动` / `JWT_SECRET` | 启动校验失败 | 场景 3.1 |
| `Address already in use` | 端口占用 | 场景 3.2 |
| `ModuleNotFoundError` | 依赖缺失 | 场景 3.3 |
| `僵尸任务` / `启动清理` | 服务重启后的任务状态清理 | 场景 4.1（正常自动恢复） |
| `持久化恢复` / `recovered` | interrupted 任务重建到内存 | 场景 4.1（正常自动恢复） |
| `DB 持久化失败（不影响执行）` | Pipeline 写 DB 失败但不阻塞主流程 | 场景 1.1（非致命） |

## 附录 C：值班决策树（快速定位）

```
告警触发
  │
  ├─ 服务不可达（curl 无响应）
  │    ├─ 容器未运行 → 场景 3（启动失败）
  │    └─ 端口不通 → 场景 3.2（端口占用）
  │
  ├─ /health/ready 返回 503
  │    ├─ database: error → 场景 1（DB 故障）
  │    ├─ llm: error → 场景 2（LLM 不可用）
  │    └─ knowledge_base: error → 检查 Obsidian Vault 连接（非致命，可降级）
  │
  ├─ 磁盘告警 → 场景 5
  │
  ├─ 用户反馈任务异常 → 场景 4
  │
  └─ 需要回滚 → 场景 6
```
