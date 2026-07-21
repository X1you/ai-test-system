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
        self._shutdown = False

    def shutdown(self):
        """优雅关闭：释放线程池资源。

        应用退出时应调用，避免线程池资源泄漏。
        幂等：多次调用安全。
        """
        if self._shutdown:
            return
        self._shutdown = True
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _running_count(self) -> int:
        """实时计算运行中任务数"""
        return sum(
            1 for t in self._tasks.values() if t.status in ("running", "pending")
        )

    def create_task(
        self,
        config: dict,
        requirements_path: str,
        mode: str = "semi",
        dimensions: str = "basic",
        formats: str = "excel",
    ) -> PipelineTask:
        """创建并启动 Pipeline 任务"""
        running = self._running_count()
        if running >= self.MAX_WORKERS:
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
        task.start_background()

        return task

    def get_task(self, pipeline_id: str) -> PipelineTask | None:
        """获取任务"""
        return self._tasks.get(pipeline_id)

    def rebuild_task_from_db(self, pipeline_id: str) -> PipelineTask | None:
        """从 DB 重建 interrupted 任务的内存 PipelineTask（方案 A）。

        场景：服务重启后 DB 中 interrupted/paused 的任务不在内存，
              用户点「继续执行」时需要先重建内存 task 才能 resume。

        重建逻辑：
          1. 从 DB Pipeline 表读 requirements_path / mode / dimensions / formats / output_dir
          2. 校验 requirements_path 仍存在（临时上传文件可能已清）
          3. 从 DB PipelineStep 读已完成的 step ids（断点续跑依据）
          4. 构造 PipelineTask 注入内存 _tasks，但不启动执行（由 resume_background 负责）

        Args:
            pipeline_id: Pipeline ID

        Returns:
            重建的 PipelineTask，DB 无记录或 requirements_path 丢失返回 None
        """
        from db.repository import get_repository

        repo = get_repository()
        p = repo.get_pipeline(pipeline_id)
        if p is None:
            return None

        # 校验需求文件仍存在（临时上传文件可能被清理）
        if not p.requirements_path or not Path(p.requirements_path).exists():
            return None

        # 加载当前配置（config 不持久化在 Pipeline 表，动态加载即可）
        from core.config_loader import load_config
        config = load_config()

        # 读 DB 已完成步骤（断点续跑依据）
        completed_steps = repo.get_completed_step_ids(pipeline_id)

        task = PipelineTask(
            pipeline_id=p.id,
            output_dir=p.output_dir or str(self.output_base / p.id),
            config=config,
            requirements_path=p.requirements_path,
            mode=p.mode or "semi",
            dimensions=p.dimensions or "basic",
            formats=p.formats or "excel",
        )
        # 恢复 DB 中已完成的步骤（断点续跑）
        task.completed_steps = list(completed_steps)
        # 保留 DB 原始状态（interrupted/paused/cancelled 等），由 resume 端点校验
        task.status = p.status or "interrupted"
        task.started_at = p.started_at.isoformat() if p.started_at else ""

        self._tasks[pipeline_id] = task
        return task

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
                "mode": task.mode,
            })
            seen_ids.add(tid)

        # 2. 从 DB 补充历史任务（内存中没有的）
        #    ★ 自愈：DB 中 running/pending/paused 但不在内存 → 僵尸任务，标记 interrupted
        try:
            from db.models import Pipeline
            from db.repository import get_repository
            from db.session import session_scope
            repo = get_repository()
            db_pipelines = repo.list_pipelines(limit=50)
            zombie_ids = []
            for p in db_pipelines:
                if p.id not in seen_ids:
                    status = p.status
                    # 僵尸检测：DB 说 running 但内存中没有 → 服务重启后遗留
                    if status in ("running", "pending", "paused"):
                        status = "interrupted"
                        zombie_ids.append(p.id)
                    completed = repo.get_completed_step_ids(p.id)
                    tasks.append({
                        "pipeline_id": p.id,
                        "status": status,
                        "completed_steps": len(completed),
                        "total_steps": 7,
                        "started_at": p.started_at.isoformat() if p.started_at else "",
                        "requirements": Path(p.requirements_path).name if p.requirements_path else "",
                        "mode": p.mode,
                    })
                    seen_ids.add(p.id)
            # 批量修复僵尸任务（写回 DB）
            if zombie_ids:
                with session_scope() as session:
                    session.query(Pipeline).filter(
                        Pipeline.id.in_(zombie_ids)
                    ).update(
                        {"status": "interrupted", "error": "服务重启，任务中断（列表自愈）"},
                        synchronize_session="fetch",
                    )
                import logging
                logging.getLogger("web").info(
                    f"列表自愈：{len(zombie_ids)} 个僵尸任务标记为 interrupted"
                )
        except Exception as e:
            # DB 未就绪时仅返回内存任务
            import logging
            logging.getLogger("web").warning(f"DB 任务列表回退失败: {e}")

        return tasks

    def is_full(self) -> bool:
        """是否已达并发上限"""
        return self._running_count() >= self.MAX_WORKERS

    def get_running_count(self) -> int:
        """获取运行中任务数"""
        return self._running_count()


# 全局单例
_task_manager: TaskManager | None = None


def get_task_manager() -> TaskManager:
    """获取全局 TaskManager 单例"""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager
