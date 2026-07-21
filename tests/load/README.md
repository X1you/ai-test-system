# Locust 压测脚本

针对 ai-test-system 核心 API 的压力测试，用于：

1. 测出系统在不同并发下的 **QPS 上限** 和 **响应延迟分布**（P50 / P95 / P99）
2. 暴露 **SQLite WAL 模式下的 `database is locked` 写冲突点**

---

## 覆盖的端点

| 任务                  | 端点                          | 类型        | 认证 | 说明                           |
| --------------------- | ----------------------------- | ----------- | ---- | ------------------------------ |
| `health_live`         | `GET /health/live`            | 轻量读      | 否   | 进程存活，不碰 DB              |
| `health_ready`        | `GET /health/ready`           | 中量读      | 否   | 查 DB / LLM / KB 连通性        |
| `kb_status`           | `GET /api/v1/knowledge/status` | 轻量读      | 是   | KB 统计，60s 缓存              |
| `kb_search`           | `GET /api/v1/knowledge/search` | 中量读      | 是   | KB 搜索 + 分页                 |
| `pipeline_list`       | `GET /api/v1/pipeline/list`   | DB 读       | 是   | 全量遍历任务做仪表盘统计       |
| `start_pipeline`      | `POST /api/v1/pipeline/start` | **重量写**  | 是   | 建 Pipeline + 后台 7 Step（LLM） |

`start_pipeline` 默认**跳过**（避免烧 LLM 额度），用环境变量打开。

---

## 前置条件

1. **服务已启动**（默认 `http://127.0.0.1:8080`）：

   ```bash
   uv run uvicorn web.app:app --port 8080
   ```

2. **管理员账户存在**（首次启动会自动创建 `admin/admin123`）。

3. **locust 不进项目依赖**，用 `uv --with` 临时拉起，保持压测工具独立：

   ```bash
   uv run --with locust locust --version
   ```

---

## 快速开始

### 1. Web UI 模式（推荐第一次跑）

```bash
uv run --with locust locust \
    -f tests/load/locustfile.py \
    --host http://127.0.0.1:8080
```

浏览器打开 `http://localhost:8089`，在 UI 里设：
- **Number of users**：虚拟用户数（从 50 开始往上加）
- **Ramp up**：每秒新增用户数（建议 5~10）
- **Host**：已在命令行传入，UI 里可留空

### 2. Headless 模式（CI / 批量跑）

```bash
uv run --with locust locust \
    -f tests/load/locustfile.py \
    --host http://127.0.0.1:8080 \
    --headless \
    -u 100 \
    -r 10 \
    --run-time 2m \
    --csv tests/load/report
```

- `-u 100`：100 个并发虚拟用户
- `-r 10`：每秒新增 10 个用户（10 秒爬坡到 100）
- `--run-time 2m`：跑 2 分钟
- `--csv tests/load/report`：输出 `report_stats.csv` / `report_failures.csv` 等

### 3. 分布式压测（更高并发）

单进程 locust 大约能模拟 ~1000 并发用户。要更高：
```bash
# Master
uv run --with locust locust -f tests/load/locustfile.py --master --host http://...

# Worker（可多机/多进程）
uv run --with locust locust -f tests/load/locustfile.py --worker --master-host=<master-ip>
```

---

## 环境变量

| 变量                    | 默认值                   | 说明                                              |
| ----------------------- | ------------------------ | ------------------------------------------------- |
| `LOCUST_USERNAME`       | `admin`                  | 登录用户名                                        |
| `LOCUST_PASSWORD`       | `admin123`               | 登录密码                                          |
| `LOCUST_SKIP_PIPELINE`  | `1`                      | `1`=跳过 POST /pipeline/start；`0`=启用（烧 LLM） |
| `LOCUST_PIPELINE_WEIGHT`| `1`                      | start_pipeline 任务权重（仅 SKIP=0 时生效）       |
| `LOCUST_SEARCH_QUERIES` | `测试,登录,异常,性能,安全` | 搜索关键词池，逗号分隔                            |

示例 —— 启用 pipeline 触发：
```bash
LOCUST_SKIP_PIPELINE=0 LOCUST_PIPELINE_WEIGHT=1 \
uv run --with locust locust -f tests/load/locustfile.py --host http://127.0.0.1:8080
```

---

## 关键指标解读（Locust 统计表）

| 指标            | 含义                                   | 健康参考                          |
| --------------- | -------------------------------------- | --------------------------------- |
| **Requests**    | 总请求数                               | 越高越好                          |
| **Fails**       | 失败请求数                             | 读操作应接近 0                    |
| **Average**     | 平均响应时间（ms）                     | 读 < 100ms，写 < 500ms            |
| **Min / Max**   | 最快 / 最慢响应                        | Max 飙高通常是锁等待或 GC         |
| **Content Size**| 响应体大小                             | 异常变大检查是否返回了错误堆栈    |
| **RPS**         | 每秒请求数                             | **这是 QPS 上限的直接指标**       |
| **Current RPS** | 当前实时 RPS                           | 稳定后看拐点                      |

### 找 QPS 上限的方法（阶梯加压）

```
跑 1：-u 50  -r 5  --run-time 1m   → 记 RPS₁、P95
跑 2：-u 100 -r 10 --run-time 1m   → 记 RPS₂、P95
跑 3：-u 200 -r 20 --run-time 1m   → 记 RPS₃、P95
跑 4：-u 400 -r 40 --run-time 1m   → 记 RPS₄、P95
```

- **RPS 不再增长**（或开始下降）的点 = 系统吞吐上限
- **P95 突然飙升**（如从 50ms → 2000ms）的点 = 资源饱和拐点
- 两个点的较小值就是当前部署的 QPS 上限

### 延迟分布要看分位数

Locust 默认显示 Average，但**判断瓶颈要看 P95 / P99**：
- 在 Web UI 的 Charts 页面切到 Response Time (ms)
- Headless 模式看 `*_stats.csv` 的 `95%` / `99%` 列
- 长尾变宽（P99 远大于 P50）通常意味着 **锁等待** 或 **连接排队**

---

## SQLite 锁冲突 —— 预期表现

### 背景

项目用 SQLite（`data/app.db`），`db/session.py` 配置了：
- `PRAGMA journal_mode=WAL` —— 写不阻塞读
- `PRAGMA busy_timeout=5000` —— 写冲突时等 5 秒再放弃

WAL 缓解了读写互斥，但**多个写事务之间仍然串行**。压测触发写的主要路径：
1. `POST /api/v1/auth/login` → 更新 `users.last_login`（每次登录都写！）
2. `POST /api/v1/pipeline/start` → 建 `pipelines` + `steps` 行
3. Pipeline 后台 Step 执行 → 大量 Step 记录写入

### 预期出现的现象

| 并发用户 | 预期表现                                                |
| -------- | ------------------------------------------------------- |
| < 50     | 一切正常，WAL + busy_timeout 足够消化                   |
| 50~200   | `/auth/login` 开始出现 P95 抬升（last_login 写串行）     |
| 200+     | 高并发登录时可能出现 **500 + "database is locked"**     |
| 开启 pipeline | 4xx/5xx 混合：**429**（is_full 并发上限）+ **500**（锁）|

### 在日志里怎么找锁错误

locustfile 里注册了 `events.request` 监听器，一旦响应文本含 `database is locked` / `database is busy`，会打一条醒目的：

```
🔴 [SQLite LOCK DETECTED] POST /auth/login rt=5012ms :: {"detail":"...database is locked..."}
```

在 headless 模式重定向 stderr 到文件方便事后 grep：
```bash
uv run --with locust locust ... 2>tests/load/stderr.log
grep "SQLite LOCK DETECTED" tests/load/stderr.log | wc -l
```

### 如果锁冲突太多怎么办（不是 bug，是架构限制）

1. **短期**：把 `busy_timeout` 从 5000 提到 10000~30000（`db/session.py`）
2. **中期**：给写热点加批量/去抖（比如 `last_login` 改为每分钟批量更新一次）
3. **长期**：迁移到 PostgreSQL（`db/session.py` 已为 PG 预留了 QueuePool 分支）

---

## 安全提示

- **压测别打生产**：默认密码 `admin/admin123` 只在本地用
- **locust 不进 pyproject.toml**：保持压测工具与生产依赖隔离，避免供应链膨胀
- **开 `LOCUST_SKIP_PIPELINE=0` 前确认 LLM 额度**：每个 pipeline 触发会跑 7 个 Step，每个 Step 都调 LLM
