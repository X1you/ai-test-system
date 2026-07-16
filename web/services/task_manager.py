#!/usr/bin/env python3
"""
任务管理器 — Pipeline 异步任务管理

线程池执行 + 内存状态追踪。
重启后通过磁盘 _pipeline_state.json 恢复可 resume 的任务。
"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from web.services.pipeline_task import PipelineTask


class TaskManager:
    """Pipeline 异步任务管理器"""

    MAX_WORKERS = 2

    def __init__(self, output_base: str = "./output"):
        self.output_base = Path(output_base)
        self.output_base.mkdir(parents=True, exist_ok=True)
        self._executor = ThreadPoolExecutor(max_workers=self.MAX_WORKERS)
        self._tasks: dict[str, PipelineTask] = {}
        self._active_count = 0

    def create_task(
        self,
        config: dict,
        requirements_path: str,
        mode: str = "semi",
        dimensions: str = "basic",
        formats: str = "excel",
    ) -> PipelineTask:
        """创建并启动 Pipeline 任务"""
        if self._active_count >= self.MAX_WORKERS:
            raise RuntimeError(
                f"并发任务已达上限 ({self.MAX_WORKERS})，请等待现有任务完成"
            )

        pipeline_id = uuid.uuid4().hex[:12]
        output_dir = str(self.output_base / pipeline_id)

        task = PipelineTask(
            pipeline_id=pipeline_id,
            output_dir=output_dir,
            config=config,
            requirements_path=requirements_path,
            mode=mode,
            dimensions=dimensions,
            formats=formats,
        )

        self._tasks[pipeline_id] = task
        self._active_count += 1
        task.start_background()

        return task

    def get_task(self, pipeline_id: str) -> PipelineTask | None:
        """获取任务"""
        return self._tasks.get(pipeline_id)

    def list_tasks(self) -> list:
        """列出所有任务

        合并内存中的活跃任务 + DB 中的历史任务，
        确保重启后仍能看到之前的 Pipeline 记录。
        """
        tasks = []
        seen_ids = set()

        # 1. 先从内存中的活跃任务获取
        for tid, task in self._tasks.items():
            tasks.append({
                "pipeline_id": tid,
                "status": task.status,
                "completed_steps": len(task.completed_steps),
                "total_steps": 7,
                "started_at": task.started_at,
                "requirements": Path(task.requirements_path).name,
            })
            seen_ids.add(tid)

        # 2. 从 DB 补充历史任务（内存中没有的）
        try:
            from db.repository import get_repository
            repo = get_repository()
            db_pipelines = repo.list_pipelines(limit=50)
            for p in db_pipelines:
                if p.id not in seen_ids:
                    completed = repo.get_completed_step_ids(p.id)
                    tasks.append({
                        "pipeline_id": p.id,
                        "status": p.status,
                        "completed_steps": len(completed),
                        "total_steps": 7,
                        "started_at": p.started_at.isoformat() if p.started_at else "",
                        "requirements": Path(p.requirements_path).name if p.requirements_path else "",
                    })
                    seen_ids.add(p.id)
        except Exception:
            # DB 未就绪时仅返回内存任务
            pass

        return tasks

    def is_full(self) -> bool:
        """是否已达并发上限"""
        running = sum(1 for t in self._tasks.values() if t.status in ("running", "pending"))
        self._active_count = running
        return running >= self.MAX_WORKERS

    def get_running_count(self) -> int:
        """获取运行中任务数"""
        return sum(1 for t in self._tasks.values() if t.status in ("running", "pending"))


# 全局单例
_task_manager: TaskManager | None = None


def get_task_manager() -> TaskManager:
    """获取全局 TaskManager 单例"""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager
