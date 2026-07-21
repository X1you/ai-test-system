#!/usr/bin/env python3
"""
Locust 压测脚本 — ai-test-system 核心 API 端点。

目标：
  1. 测出系统在不同并发下的 QPS 上限 / 响应延迟分布（P50/P95/P99）
  2. 暴露 SQLite WAL 模式下的「database is locked」写冲突点

真实用户行为建模：
  登录拿 JWT → 轮询知识库状态 → 搜索 → 查任务列表 → （偶尔）触发 pipeline

Pipeline 触发会真实调用 LLM（烧钱 + 慢）。默认不触发，靠环境变量打开：
  LOCUST_SKIP_PIPELINE=1   （默认）跳过 POST /pipeline/start
  LOCUST_SKIP_PIPELINE=0   启用 pipeline 触发（会打 LLM，谨慎）

运行（不修改 pyproject.toml，locust 通过 uv --with 临时拉起）：
  uv run --with locust locust -f tests/load/locustfile.py \
      --host http://127.0.0.1:8080

其它环境变量（均有默认值）：
  LOCUST_USERNAME         登录用户名（默认 admin）
  LOCUST_PASSWORD         登录密码（默认 admin123）
  LOCUST_PIPELINE_WEIGHT  start_pipeline 任务权重（默认 1，仅 SKIP=0 时生效）
  LOCUST_SEARCH_QUERIES   搜索关键词，逗号分隔（默认 测试,登录,异常）
"""

from __future__ import annotations

import io
import os
import random

from locust import HttpUser, between, events, task

# ─── 配置（从环境变量读，给个安全默认值）───

HOST_DEFAULT = "http://127.0.0.1:8080"
USERNAME = os.environ.get("LOCUST_USERNAME", "admin")
PASSWORD = os.environ.get("LOCUST_PASSWORD", "admin123")
SKIP_PIPELINE = os.environ.get("LOCUST_SKIP_PIPELINE", "1") == "1"
PIPELINE_WEIGHT = int(os.environ.get("LOCUST_PIPELINE_WEIGHT", "1"))
# 搜索关键词池：从知识库里能命中的高频词
SEARCH_QUERIES = [
    q.strip()
    for q in os.environ.get("LOCUST_SEARCH_QUERIES", "测试,登录,异常,性能,安全").split(",")
    if q.strip()
] or ["测试"]

# mock 需求文档内容（POST /pipeline/start 需要 multipart 上传 .md/.txt）
# 极简内容，避免 Step0/Step1 LLM 思考太久；真正的目的是压 DB 写 + 任务创建路径
_MOCK_REQ_FILENAME = "locust_loadtest.md"
_MOCK_REQ_CONTENT = (
    "# Locust 压测需求\n\n"
    "这是一份用于压测的占位需求文档。\n\n"
    "## 功能点\n\n"
    "1. 用户登录\n2. 查询状态\n3. 触发任务\n"
)


@events.init.add_listener
def _on_init(environment, **kwargs):
    """Locust 启动时打印一次配置，避免每个 worker 都刷屏。"""
    print(
        "\n========== Locust 压测配置 ==========\n"
        f"  Target host        : {environment.host}\n"
        f"  Username           : {USERNAME}\n"
        f"  Skip pipeline      : {SKIP_PIPELINE}\n"
        f"  Pipeline weight    : {PIPELINE_WEIGHT} (仅 SKIP=False 时生效)\n"
        f"  Search queries     : {SEARCH_QUERIES}\n"
        "=====================================\n"
    )
    if not SKIP_PIPELINE:
        print(
            "⚠️  LOCUST_SKIP_PIPELINE=0：POST /pipeline/start 已启用！\n"
            "    每次触发会真实调用 LLM 并写入大量产物文件，建议：\n"
            "      - 用极小的 --spawn-rate 和低的 pipeline 权重\n"
            "      - 准备好 LLM 额度被消耗\n"
            "      - 优先用 mock LLM 后端（把 config.yaml 指向 echo 模型）\n"
        )


class AiTestSystemUser(HttpUser):
    """模拟一个真实前端用户：登录后做读操作，偶尔触发任务。

    所有需要认证的端点都用 self.client 的 headers 带 JWT。
    """

    # Think time：真实用户两次操作之间有思考间隔
    wait_time = between(1, 3)

    # on_start 在每个虚拟用户启动时跑一次 → 登录拿 token
    def on_start(self):
        self.token: str | None = None
        self._login()

    # ─── 任务：健康检查（无需认证，最轻量读）───
    @task(5)
    def health_live(self):
        """Liveness 探针，纯进程存活检查，不碰 DB。"""
        with self.client.get(
            "/health/live", name="GET /health/live", catch_response=True
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"liveness 非 200: {resp.status_code}")

    @task(2)
    def health_ready(self):
        """Readiness 探针，会查 DB / LLM / KB 连通性 —— 中量读。"""
        with self.client.get(
            "/health/ready", name="GET /health/ready", catch_response=True
        ) as resp:
            # readiness 在依赖降级时返回 503，也算正常响应（探针本身的正确行为）
            if resp.status_code not in (200, 503):
                resp.failure(f"readiness 异常: {resp.status_code}")

    # ─── 任务：知识库状态（轻量读，带 60s 缓存）───
    @task(8)
    def kb_status(self):
        """GET /api/v1/knowledge/status —— KB 统计，走 60s 缓存。"""
        if not self._ensure_token():
            return
        with self.client.get(
            "/api/v1/knowledge/status",
            name="GET /knowledge/status",
            headers=self._auth_headers(),
            catch_response=True,
        ) as resp:
            if resp.status_code == 401:
                # token 过期 → 重新登录（JWT 默认 24h，几乎不会触发，兜底）
                self.token = None
                self._login()
            elif resp.status_code != 200:
                resp.failure(f"status {resp.status_code}: {resp.text[:200]}")

    # ─── 任务：知识库搜索（中量读，缓存层上限 500 条 + 分页切片）───
    @task(6)
    def kb_search(self):
        """GET /api/v1/knowledge/search?q=..."""
        if not self._ensure_token():
            return
        q = random.choice(SEARCH_QUERIES)
        with self.client.get(
            "/api/v1/knowledge/search",
            name="GET /knowledge/search",
            params={"q": q, "page": 1, "page_size": 20},
            headers=self._auth_headers(),
            catch_response=True,
        ) as resp:
            if resp.status_code == 401:
                self.token = None
                self._login()
            elif resp.status_code != 200:
                resp.failure(f"search {resp.status_code}: {resp.text[:200]}")

    # ─── 任务：pipeline 列表（DB 读，分页 + 统计仪表盘全量遍历）───
    @task(5)
    def pipeline_list(self):
        """GET /api/v1/pipeline/list —— 全量遍历任务做仪表盘统计。"""
        if not self._ensure_token():
            return
        with self.client.get(
            "/api/v1/pipeline/list",
            name="GET /pipeline/list",
            params={"page": 1, "page_size": 20},
            headers=self._auth_headers(),
            catch_response=True,
        ) as resp:
            if resp.status_code == 401:
                self.token = None
                self._login()
            elif resp.status_code != 200:
                resp.failure(f"list {resp.status_code}: {resp.text[:200]}")

    # ─── 任务：触发 pipeline（重量写，会调 LLM + DB 写 + 落盘）───
    # 默认 SKIP_PIPELINE=1 时整个 task 方法不注册（见类末尾的动态摘除）
    @task(PIPELINE_WEIGHT if not SKIP_PIPELINE else 0)
    def start_pipeline(self):
        """POST /api/v1/pipeline/start —— multipart 上传需求文档。

        这是系统里最重的写操作：写 uploads/、写 DB（建 Pipeline + Step 记录）、
        后台线程跑 7 个 Step（每个都调 LLM）。
        在压测中触发它会：
          1. 触发 SQLite 写事务（暴露 'database is locked'）
          2. 触发 tm.is_full() 并发上限 → 可能返回 429
          3. 烧 LLM 额度
        默认跳过，需 LOCUST_SKIP_PIPELINE=0 显式开启。
        """
        if not self._ensure_token():
            return

        files = {
            "file": (
                _MOCK_REQ_FILENAME,
                io.BytesIO(_MOCK_REQ_CONTENT.encode("utf-8")),
                "text/markdown",
            )
        }
        data = {"mode": "auto", "dimensions": "basic", "formats": "excel"}

        with self.client.post(
            "/api/v1/pipeline/start",
            name="POST /pipeline/start",
            files=files,
            data=data,
            headers=self._auth_headers(exclude_json=True),
            catch_response=True,
        ) as resp:
            # 201 = 创建成功（正常）
            # 429 = 并发上限（is_full）—— 这是预期的压测结果，标记为成功
            # 401 = token 失效，重新登录
            if resp.status_code == 201:
                pass  # 成功
            elif resp.status_code == 429:
                # 并发任务已满 —— 这是压测想暴露的点，标 success 让统计干净
                resp.success()
            elif resp.status_code == 401:
                self.token = None
                self._login()
            else:
                resp.failure(
                    f"start_pipeline {resp.status_code}: {resp.text[:200]}"
                )

    # ─── 辅助方法 ───

    def _login(self):
        """POST /api/v1/auth/login 拿 access_token。

        login 端点本身无 verify_token 依赖，但可能命中 slowapi 速率限制
        （压测高并发登录时会看到 429，属于预期行为）。
        """
        with self.client.post(
            "/api/v1/auth/login",
            json={"username": USERNAME, "password": PASSWORD},
            name="POST /auth/login",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"登录失败 {resp.status_code}: {resp.text[:200]}")
                return
            try:
                self.token = resp.json().get("access_token")
            except Exception as e:
                resp.failure(f"登录响应解析失败: {e}")
                return
            if not self.token:
                resp.failure("登录响应缺少 access_token")

    def _ensure_token(self) -> bool:
        """确保有 token，没有就登录一次。"""
        if not self.token:
            self._login()
        return self.token is not None

    def _auth_headers(self, exclude_json: bool = False) -> dict:
        """构造带 JWT 的请求头。

        exclude_json=True 时只返回 Authorization（用于 multipart 上传，
        requests 库会自己加 Content-Type: multipart/form-data + boundary，
        我们不能手动塞 application/json 或会破坏 boundary）。
        """
        h = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        return h


# ─── 全局失败监听：把 SQLite 锁错误单独高亮，方便从 Locust 日志里一眼看到 ───


@events.request.add_listener
def _on_request(
    request_type, name, response_time, response_length, response, context, exception, **kwargs
):
    """捕获响应文本中的 'database is locked' / 'database is busy'。

    FastAPI 的全局异常处理器会把未捕获异常包成 500 + JSON。
    SQLite 写冲突（超过 busy_timeout=5000ms）会抛 OperationalError，
    最终在响应体里体现为 'database is locked' 之类的字符串。
    这里抓出来打一条醒目的 stderr，避免淹没在 Locust 默认日志里。
    """
    if exception:
        msg = str(exception)
    elif response is not None:
        try:
            # response 在 headless 模式可能是 None，用 text 兜底
            text = getattr(response, "text", "") or ""
            msg = text
        except Exception:
            return
    else:
        return

    lowered = msg.lower()
    if "database is locked" in lowered or "database is busy" in lowered:
        # 不改 Locust 自己的统计，只额外打一行便于事后 grep
        print(
            f"\n🔴 [SQLite LOCK DETECTED] {request_type} {name} "
            f"rt={response_time}ms :: {msg[:300]}\n"
        )
