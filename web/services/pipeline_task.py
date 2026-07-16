#!/usr/bin/env python3
"""
Pipeline 任务包装器 — 对 core/pipeline.py 的包装，增加实时状态追踪

WebUI 通过此包装器追踪 Pipeline 执行进度。
状态变更时同步写入 DB（Phase 2 持久化层），重启后不丢失。
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime

from core.pipeline import Pipeline

# DB 持久化（Phase 2）
from db.repository import get_repository
from db.session import init_db

# EventBus（Phase 3）— 事件实时推送
from web.services.event_bus import get_event_bus

# 首次调用时确保 DB 已初始化
_db_initialized = False


class _PipelineCancelled(Exception):
    """Pipeline 执行被取消（内部信号异常）"""


def _ensure_db():
    """延迟初始化 DB 表（首次创建任务时）"""
    global _db_initialized
    if not _db_initialized:
        init_db()
        _db_initialized = True


@dataclass
class PipelineTask:
    """Pipeline 任务 — 状态追踪包装器"""

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

    def start_background(self):
        """在后台线程执行"""
        _ensure_db()
        self.status = "running"
        self.started_at = datetime.now().isoformat()
        self._persist_pipeline("running")
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def resume_background(self):
        """从断点继续（后台线程）"""
        _ensure_db()
        self.status = "running"
        self._cancel_flag = False
        self.started_at = datetime.now().isoformat()
        self._persist_pipeline("running")
        self._thread = threading.Thread(target=self._run_resume, daemon=True)
        self._thread.start()

    def cancel(self):
        """取消 Pipeline"""
        self._cancel_flag = True
        self.status = "cancelled"
        self._persist_pipeline("cancelled")
        self._on_log("WARN", "Pipeline 已取消")
        self._publish_event("cancelled", {"pipeline_id": self.pipeline_id})

    def is_cancelled(self) -> bool:
        """检查是否已被取消（供步骤内部轮询）"""
        return self._cancel_flag

    def _check_cancelled(self):
        """检查取消标志 — 被取消时抛出 _PipelineCancelled

        在步骤间隙调用此方法实现协作式取消。
        """
        if self._cancel_flag:
            raise _PipelineCancelled()

    def _publish_event(self, event_type: str, data: dict):
        """发布事件到 EventBus（供 SSE 推送）"""
        try:
            bus = get_event_bus()
            bus.publish_sync(self.pipeline_id, {"type": event_type, "data": data})
        except Exception:
            pass

    def _run(self):
        """实际执行 — 首次运行"""
        try:
            pipeline = Pipeline(self.config, self.output_dir)
            pipeline.on_log = self._on_log
            pipeline.on_step_done = self._on_step_done

            self._on_log("STEP", f"Pipeline 启动 — 模式: {self.mode}")

            state = pipeline.run(
                requirements_file=self.requirements_path,
                mode=self.mode,
                dimensions=self.dimensions,
                formats=self.formats,
            )

            self._finalize(state, pipeline)
        except _PipelineCancelled:
            self.status = "cancelled"
            self._on_log("WARN", "Pipeline 已取消（中断执行）")
            self._persist_pipeline("cancelled")
            self._publish_event("cancelled", {"pipeline_id": self.pipeline_id})
        except Exception as e:
            self.status = "error"
            self.error = str(e)
            self._on_log("ERR", f"Pipeline 执行失败: {e}")
            self._publish_event("error", {"pipeline_id": self.pipeline_id, "error": str(e)})
    def _run_resume(self):
        """实际执行 — 从断点继续"""
        try:
            pipeline = Pipeline(self.config, self.output_dir)
            pipeline.on_log = self._on_log
            pipeline.on_step_done = self._on_step_done

            self._on_log("STEP", "Pipeline 继续执行")

            state = pipeline.run(
                requirements_file=self.requirements_path,
                mode="auto",
                dimensions=self.dimensions,
                formats=self.formats,
            )

            self._finalize(state, pipeline)
        except _PipelineCancelled:
            self.status = "cancelled"
            self._on_log("WARN", "Pipeline 已取消（中断执行）")
            self._persist_pipeline("cancelled")
            self._publish_event("cancelled", {"pipeline_id": self.pipeline_id})
        except Exception as e:
            self.status = "error"
            self.error = str(e)
            self._on_log("ERR", f"Pipeline 恢复失败: {e}")
            self._publish_event("error", {"pipeline_id": self.pipeline_id, "error": str(e)})

    def _finalize(self, state: dict, pipeline: Pipeline | None = None):
        """根据最终状态设置任务状态"""
        done = state.get("completed_steps", [])
        if 7 in done:
            self.status = "done"
            self._on_log("OK", "全流程执行完成 ✅")
        elif 6 not in done:
            self.status = "paused"
            self._on_log("HUMAN", "Pipeline 暂停 — 等待人工执行测试")
        else:
            self.status = "done"

        if pipeline and pipeline.llm:
            self.llm_stats = pipeline.llm.stats

        # 持久化最终状态到 DB
        self._persist_pipeline(self.status)

        # 发布最终事件到 EventBus（供 SSE 终止流）
        event_data = {"pipeline_id": self.pipeline_id, "status": self.status}
        self._publish_event(self.status, event_data)

    # ─── DB 持久化方法（Phase 2）───

    def _persist_pipeline(self, status: str):
        """将 Pipeline 状态写入 DB

        如果 Pipeline 记录不存在则创建，存在则更新状态。
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
            else:
                repo.update_pipeline_status(self.pipeline_id, status)
        except Exception:
            # DB 写入失败不应阻塞 Pipeline 执行
            self._on_log("WARN", "DB 持久化失败（不影响执行）")

    def _persist_step(self, step_id: int, result: dict):
        """将步骤完成状态写入 DB"""
        try:
            repo = get_repository()
            step_names = {
                1: "需求分析",
                2: "知识库检索",
                3: "测试点梳理",
                4: "生成用例",
                5: "用例评审",
                6: "执行测试",
                7: "生成报告",
            }
            status = "completed" if result.get("ok") else "failed"
            import json

            detail = json.dumps(result.get("data", {}), ensure_ascii=False)[
                :500
            ]
            repo.record_step(
                pipeline_id=self.pipeline_id,
                step_id=step_id,
                name=step_names.get(step_id, f"Step {step_id}"),
                status=status,
                detail=detail,
            )
        except Exception:
            pass

    def _on_log(self, level: str, msg: str):
        """日志回调 — Pipeline 每输出一条日志时触发"""
        ts = datetime.now().strftime("%H:%M:%S")
        self.logs.append({"ts": ts, "level": level, "msg": msg})
        if len(self.logs) > 200:
            self.logs = self.logs[-200:]

    def _on_step_done(self, step_id: int, result: dict):
        """步骤完成回调"""
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

    def get_progress(self) -> dict:
        """获取进度数据"""
        current_step = max(self.completed_steps, default=0) + 1
        if self.status == "done" and 7 in self.completed_steps:
            current_step = 7
        return {
            "pipeline_id": self.pipeline_id,
            "percent": round(len(self.completed_steps) / 7 * 100),
            "status": self.status,
            "mode": self.mode,
            "completed_steps": list(self.completed_steps),
            "current_step": current_step,
            "steps": self._build_steps_view(),
            "logs": self.logs[-20:],
            "llm_stats": self.llm_stats,
            "error": self.error,
            "started_at": self.started_at,
        }

    def _build_steps_view(self) -> list:
        """构建步骤状态视图"""
        step_names = {
            1: "需求分析",
            2: "知识库检索",
            3: "测试点梳理",
            4: "生成用例",
            5: "用例评审",
            6: "执行测试",
            7: "生成报告",
        }
        view = []
        for sid in range(1, 8):
            done = sid in self.completed_steps
            detail = self.step_details.get(sid, {}).get("data", {})
            detail_str = ""
            if done and detail:
                if "modules" in detail:
                    detail_str = f"{detail['modules']} 模块 {detail.get('features', 0)} 功能点"
                elif "hits" in detail:
                    detail_str = f"命中 {detail['hits']} 条" if detail.get("hits") else "未命中"
                elif "count" in detail:
                    detail_str = f"{detail['count']} 个测试点"
                elif "case_count" in detail:
                    detail_str = f"{detail['case_count']} 条用例"
                elif "score" in detail:
                    detail_str = f"评分 {detail['score']}/100"

            view.append({
                "id": sid,
                "name": step_names[sid],
                "status": "done" if done else ("running" if self.status == "running" and sid == max(self.completed_steps, default=0) + 1 else "pending"),
                "detail": detail_str,
            })
        return view
