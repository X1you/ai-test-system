#!/usr/bin/env python3
"""
Pipeline 任务包装器 — 对 core/pipeline.py 的包装，增加实时状态追踪。

WebUI 通过此包装器追踪 Pipeline 执行进度。
状态变更时同步写入 DB（Phase 2 持久化层），重启后不丢失。

架构说明：
  - PipelineTask 是 dataclass，持有运行时状态（status/logs/steps），
    并通过 on_log / on_step_done 回调与 core.Pipeline 双向通信。
  - 执行在后台 daemon 线程中完成；cancel() 设置协作式取消标志，
    步骤间隙检查并抛出 _PipelineCancelled。
  - 所有状态变更经 _persist_pipeline() 写入 DB，经 _publish_event()
    推送到 EventBus 供 SSE 订阅。
"""

import json
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from core.pipeline import STEP_REGISTRY, TOTAL_STEPS, Pipeline

# DB 持久化（Phase 2）
from db.repository import get_repository
from db.session import init_db

# EventBus（Phase 3）— 事件实时推送
from web.services.event_bus import get_event_bus

# 步骤 id → 中文名映射，复用 STEP_REGISTRY（单一数据源，不再多处硬编码）
STEP_NAMES: dict[int, str] = {meta.id: meta.name for meta in STEP_REGISTRY}

# 日志缓冲上限 — 超出后保留最新窗口，避免无界增长占用内存
MAX_LOGS = 200
# 进度查询时返回给前端的最近日志条数
LOG_RETURN_WINDOW = 20

# 首次调用时确保 DB 已初始化
_db_initialized = False


class _PipelineCancelled(Exception):
    """Pipeline 执行被取消（内部信号异常）。"""


def _ensure_db():
    """延迟初始化 DB 表（首次创建任务时）。"""
    global _db_initialized
    if not _db_initialized:
        init_db()
        _db_initialized = True


@dataclass
class PipelineTask:
    """Pipeline 任务 — 状态追踪包装器。

    字段分组：
      - 静态配置：pipeline_id / output_dir / config / requirements_path / mode / ...
      - 运行时状态：status / completed_steps / step_details / logs / llm_stats / error
      - 内部控制：_thread / _cancel_flag / _logs_lock（修复 TC-002 线程安全）
    """

    pipeline_id: str
    output_dir: str
    config: dict
    requirements_path: str
    mode: str = "semi"
    dimensions: str = "basic"
    formats: str = "excel"

    # 运行时状态
    status: str = "pending"       # pending | running | paused | done | error | cancelled
    completed_steps: list[int] = field(default_factory=list)
    step_details: dict[int, dict] = field(default_factory=dict)
    logs: list[dict] = field(default_factory=list)
    llm_stats: dict = field(default_factory=dict)
    error: str = ""
    started_at: str = ""
    _thread: threading.Thread | None = None
    _cancel_flag: bool = False
    # ★ 修复 TC-002：logs 读写锁，保护 append+切片复合操作的原子性
    _logs_lock: threading.Lock = field(default_factory=threading.Lock)

    # ─── 生命周期入口 ───

    def start_background(self):
        """在后台线程执行（首次运行）。"""
        self._launch(self._run, "Pipeline 启动 — 模式: " + self.mode)

    def resume_background(self):
        """从断点继续（后台线程）。"""
        self._launch(self._run_resume, "Pipeline 继续执行")

    def _launch(self, target: Callable[[], None], startup_log: str):
        """统一的线程启动逻辑 — 设置状态、持久化、记录日志、启动线程。

        Args:
            target: 线程入口函数（_run / _run_resume）
            startup_log: 启动时输出的日志消息
        """
        _ensure_db()
        self.status = "running"
        self._cancel_flag = False
        self.started_at = datetime.now().isoformat()
        self._persist_pipeline("running")
        self._on_log("STEP", startup_log)
        self._thread = threading.Thread(target=target, daemon=True)
        self._thread.start()

    def cancel(self):
        """取消 Pipeline（协作式 — 在下一个步骤间隙生效）。"""
        self._cancel_flag = True
        self.status = "cancelled"
        self._persist_pipeline("cancelled")
        self._on_log("WARN", "Pipeline 已取消")
        self._publish_event("cancelled", {"pipeline_id": self.pipeline_id})

    def is_cancelled(self) -> bool:
        """检查是否已被取消（供步骤内部轮询）。"""
        return self._cancel_flag

    def _check_cancelled(self):
        """检查取消标志 — 被取消时抛出 _PipelineCancelled。

        在步骤间隙调用此方法实现协作式取消。
        """
        if self._cancel_flag:
            raise _PipelineCancelled()

    # ─── 事件 / 持久化 ───

    def _publish_event(self, event_type: str, data: dict):
        """发布事件到 EventBus（供 SSE 推送）。

        发布失败静默忽略 — EventBus 故障不应阻塞 Pipeline 主流程。
        """
        try:
            bus = get_event_bus()
            bus.publish_sync(self.pipeline_id, {"type": event_type, "data": data})
        except Exception as e:
            # 发布失败静默忽略 — EventBus 故障不应阻塞 Pipeline 主流程，但需留痕
            import logging
            logging.getLogger("web.services.pipeline_task").debug(
                "event_publish_failed: %s (pipeline_id=%s, event=%s)",
                e, self.pipeline_id, event_type,
            )

    def _run(self):
        """实际执行 — 首次运行。"""
        self._execute(self.mode)

    def _run_resume(self):
        """实际执行 — 从断点继续（强制 auto 模式，跳过人工检查点）。"""
        self._execute("auto")

    def _execute(self, run_mode: str):
        """统一的执行主逻辑 — 合并原 _run / _run_resume 的重复代码。

        Args:
            run_mode: 传入 Pipeline.run() 的 mode 参数
        """
        try:
            pipeline = Pipeline(self.config, self.output_dir)
            pipeline.on_log = self._on_log
            pipeline.on_step_done = self._on_step_done
            pipeline.interactive = False  # WebUI 非交互式，暂停由状态机管理

            state = pipeline.run(
                requirements_file=self.requirements_path,
                mode=run_mode,
                dimensions=self.dimensions,
                formats=self.formats,
            )

            self._finalize(state, pipeline, run_mode)
        except _PipelineCancelled:
            self.status = "cancelled"
            self._on_log("WARN", "Pipeline 已取消（中断执行）")
            self._persist_pipeline("cancelled")
            self._publish_event("cancelled", {"pipeline_id": self.pipeline_id})
        except Exception as e:
            self.status = "error"
            self.error = str(e)
            self._on_log("ERR", f"Pipeline 执行失败: {e}")
            self._persist_pipeline("error")
            self._publish_event(
                "error", {"pipeline_id": self.pipeline_id, "error": str(e)}
            )

    def _finalize(self, state: dict, pipeline: Pipeline | None = None, run_mode: str = "semi"):
        """根据最终状态设置任务状态、持久化、发布终态事件。"""
        done = state.get("completed_steps", [])
        if TOTAL_STEPS in done:
            self.status = "done"
            self._on_log("OK", "全流程执行完成 ✅")
        elif len(done) < 6:
            if run_mode == "auto":
                # auto 模式不应暂停 — 未完成即为错误
                self.status = "error"
                self.error = "Pipeline 未全部完成（auto 模式不暂停）"
                self._on_log("ERR", f"Pipeline 异常终止 — 仅完成 {len(done)}/{TOTAL_STEPS} 步")
            else:
                # semi/step 模式 → 暂停等待人工
                self.status = "paused"
                self._on_log("HUMAN", "Pipeline 暂停 — 等待人工执行测试")
        else:
            self.status = "done"

        if pipeline and pipeline.llm:
            self.llm_stats = pipeline.llm.stats

        # 持久化最终状态到 DB
        self._persist_pipeline(self.status)

        # 发布最终事件到 EventBus（供 SSE 终止流）
        self._publish_event(
            self.status, {"pipeline_id": self.pipeline_id, "status": self.status}
        )

    # ─── DB 持久化方法（Phase 2）───

    def _persist_pipeline(self, status: str):
        """将 Pipeline 状态写入 DB。

        如果 Pipeline 记录不存在则创建，存在则更新状态。
        DB 写入失败不阻塞 Pipeline 执行（仅记录警告日志）。
        """
        try:
            repo = get_repository()
            existing = repo.get_pipeline(self.pipeline_id)
            if existing is None:
                repo.create_pipeline(
                    pipeline_id=self.pipeline_id,
                    requirements_path=self.requirements_path,
                    mode=self.mode,
                    dimensions=self.dimensions,
                    formats=self.formats,
                    output_dir=self.output_dir,
                )
            repo.update_pipeline_status(self.pipeline_id, status)
        except Exception:
            # DB 写入失败不应阻塞 Pipeline 执行
            self._on_log("WARN", "DB 持久化失败（不影响执行）")

    def _persist_step(self, step_id: int, result: dict):
        """将步骤完成状态写入 DB。"""
        try:
            repo = get_repository()
            status = "completed" if result.get("ok") else "failed"
            detail = json.dumps(result.get("data", {}), ensure_ascii=False)[:500]
            repo.record_step(
                pipeline_id=self.pipeline_id,
                step_id=step_id,
                name=STEP_NAMES.get(step_id, f"Step {step_id}"),
                status=status,
                detail=detail,
            )
        except Exception:
            # 步骤持久化失败不影响主流程
            pass

    # ─── 回调（由 core.Pipeline 触发）───

    def _on_log(self, level: str, msg: str):
        """日志回调 — Pipeline 每输出一条日志时触发。

        保留最近 MAX_LOGS 条，超出窗口自动裁剪。
        ★ 修复 TC-002：用 _logs_lock 保护 append+切片复合操作的原子性。
        原实现 self.logs.append + self.logs = self.logs[-MAX_LOGS:] 非原子，
        多线程并发时（Pipeline 后台线程写 + API 线程读）可能丢日志。
        """
        ts = datetime.now().strftime("%H:%M:%S")
        with self._logs_lock:
            self.logs.append({"ts": ts, "level": level, "msg": msg})
            if len(self.logs) > MAX_LOGS:
                # 切片保留尾部，O(1) 分配新列表
                self.logs = self.logs[-MAX_LOGS:]

    def _on_step_done(self, step_id: int, result: dict):
        """步骤完成回调 — 更新内存状态、持久化 DB、发布事件。"""
        if step_id not in self.completed_steps:
            self.completed_steps.append(step_id)
        self.step_details[step_id] = result
        # 持久化到 DB
        self._persist_step(step_id, result)
        # 发布步骤完成事件到 EventBus
        self._publish_event(
            "step_done",
            {"pipeline_id": self.pipeline_id, "step_id": step_id, "result": result},
        )

    # ─── 进度视图（供 API / SSE 返回）───

    def get_progress(self) -> dict:
        """获取进度数据（供前端轮询或 SSE 推送）。

        ★ 修复 TC-002：读取 logs 时加锁，避免与后台线程的 append 并发竞争。
        """
        current_step = max(self.completed_steps, default=0) + 1
        if self.status == "done" and TOTAL_STEPS in self.completed_steps:
            current_step = TOTAL_STEPS
        # 加锁拷贝 logs 快照（避免迭代时被后台线程修改）
        with self._logs_lock:
            logs_snapshot = list(self.logs[-LOG_RETURN_WINDOW:])
        return {
            "pipeline_id": self.pipeline_id,
            "percent": round(len(self.completed_steps) / TOTAL_STEPS * 100),
            "status": self.status,
            "mode": self.mode,
            "completed_steps": list(self.completed_steps),
            "current_step": current_step,
            "steps": self._build_steps_view(),
            "logs": logs_snapshot,
            "llm_stats": self.llm_stats,
            "error": self.error,
            "started_at": self.started_at,
        }

    def _build_steps_view(self) -> list:
        """构建步骤状态视图 — 每步的 id/名称/状态/明细摘要。

        状态判定：
          done    — 已在 completed_steps 中
          running — 任务运行中且是当前待执行步骤
          pending — 其余
        """
        running_step = max(self.completed_steps, default=0) + 1
        is_running = self.status == "running"
        view = []
        for meta in STEP_REGISTRY:
            done = meta.id in self.completed_steps
            if done:
                step_status = "done"
            elif is_running and meta.id == running_step:
                step_status = "running"
            else:
                step_status = "pending"
            view.append(
                {
                    "id": meta.id,
                    "name": meta.name,
                    "status": step_status,
                    "detail": self._step_detail_str(meta.id, done),
                }
            )
        return view

    def _step_detail_str(self, step_id: int, done: bool) -> str:
        """根据步骤详情 dict 生成人类可读的摘要字符串。"""
        if not done:
            return ""
        detail = self.step_details.get(step_id, {}).get("data", {})
        # 各步骤的产出摘要格式
        if "modules" in detail:
            return f"{detail['modules']} 模块 {detail.get('features', 0)} 功能点"
        if "hits" in detail:
            return f"命中 {detail['hits']} 条" if detail.get("hits") else "未命中"
        if "count" in detail:
            return f"{detail['count']} 个测试点"
        if "case_count" in detail:
            return f"{detail['case_count']} 条用例"
        if "score" in detail:
            return f"评分 {detail['score']}/100"
        return ""
