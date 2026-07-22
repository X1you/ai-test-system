#!/usr/bin/env python3
"""
Pipeline Repository — 数据访问层

封装 Pipeline / PipelineStep / Artifact 的 CRUD 操作，
提供面向业务逻辑的高级接口。
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from db.models import Artifact, Pipeline, PipelineStep, User
from db.session import session_scope


class PipelineRepository:
    """Pipeline 数据访问层"""

    def __init__(self, session: Session | None = None):
        self._session = session

    def _get_session(self) -> Session:
        if self._session:
            return self._session
        return session_scope().__enter__()

    def _close_session(self, session: Session, owned: bool):
        if owned:
            session_scope().__exit__(None, None, None)

    # ─── Pipeline ───

    def create_pipeline(
        self,
        pipeline_id: str,
        requirements_path: str,
        mode: str = "semi",
        dimensions: str = "basic",
        formats: str = "excel",
        output_dir: str = "",
    ) -> Pipeline:
        """创建 Pipeline 记录"""
        with session_scope() as session:
            pipeline = Pipeline(
                id=pipeline_id,
                requirements_path=requirements_path,
                mode=mode,
                dimensions=dimensions,
                formats=formats,
                status="pending",
                output_dir=output_dir,
            )
            session.add(pipeline)
            session.flush()
            session.refresh(pipeline)
            # detach
            session.expunge(pipeline)
            return pipeline

    def get_pipeline(self, pipeline_id: str) -> Pipeline | None:
        """查询 Pipeline"""
        with session_scope() as session:
            pipeline = (
                session.query(Pipeline)
                .filter(Pipeline.id == pipeline_id)
                .first()
            )
            if pipeline:
                session.expunge(pipeline)
            return pipeline

    def list_pipelines(
        self, limit: int = 50, offset: int = 0
    ) -> list[Pipeline]:
        """列出 Pipeline（按时间倒序）"""
        with session_scope() as session:
            pipelines = (
                session.query(Pipeline)
                .order_by(Pipeline.started_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )
            for p in pipelines:
                session.expunge(p)
            return pipelines

    def update_pipeline_status(
        self,
        pipeline_id: str,
        status: str,
        error: str | None = None,
    ):
        """更新 Pipeline 状态"""
        with session_scope() as session:
            pipeline = (
                session.query(Pipeline)
                .filter(Pipeline.id == pipeline_id)
                .first()
            )
            if pipeline:
                pipeline.status = status
                if status in ("done", "paused", "error", "cancelled", "failed", "completed"):
                    pipeline.finished_at = datetime.now(UTC)
                if error:
                    pipeline.error = error

    # ─── PipelineStep ───

    def record_step(
        self,
        pipeline_id: str,
        step_id: int,
        name: str,
        status: str,
        detail: str | None = None,
    ):
        """记录/更新步骤状态（使用 upsert 确保并发安全）

        方言适配：
          - SQLite: ON CONFLICT DO UPDATE
          - PostgreSQL: ON CONFLICT DO UPDATE
          两种语法结构相同，仅 import 来源不同，通过运行时方言判断选择。
        """
        from sqlalchemy.dialects import postgresql, sqlite

        with session_scope() as session:
            now = datetime.now(UTC)
            bind = session.bind
            dialect_name = bind.dialect.name if bind else "sqlite"

            values = dict(
                pipeline_id=pipeline_id,
                step_id=step_id,
                name=name,
                status=status,
                detail=detail,
                started_at=now,
                finished_at=now if status == "completed" else None,
            )
            update_set = {
                "status": status,
                "detail": detail,
                "finished_at": now if status == "completed" else None,
            }

            if dialect_name == "postgresql":
                stmt = postgresql.insert(PipelineStep).values(**values)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["pipeline_id", "step_id"],
                    set_=update_set,
                )
            else:
                stmt = sqlite.insert(PipelineStep).values(**values)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["pipeline_id", "step_id"],
                    set_=update_set,
                )
            session.execute(stmt)

    def get_steps(self, pipeline_id: str) -> list[PipelineStep]:
        """获取 Pipeline 的所有步骤"""
        with session_scope() as session:
            steps = (
                session.query(PipelineStep)
                .filter(PipelineStep.pipeline_id == pipeline_id)
                .order_by(PipelineStep.step_id)
                .all()
            )
            for s in steps:
                session.expunge(s)
            return steps

    def get_completed_step_ids(self, pipeline_id: str) -> list[int]:
        """获取已完成的步骤 ID 列表"""
        with session_scope() as session:
            steps = (
                session.query(PipelineStep.step_id)
                .filter(
                    PipelineStep.pipeline_id == pipeline_id,
                    PipelineStep.status == "completed",
                )
                .all()
            )
            return [s[0] for s in steps]

    # ─── Artifact ───

    def record_artifact(
        self,
        pipeline_id: str,
        name: str,
        display_name: str,
        type: str,
        size: int = 0,
    ):
        """记录产物元数据"""
        with session_scope() as session:
            artifact = Artifact(
                pipeline_id=pipeline_id,
                name=name,
                display_name=display_name,
                type=type,
                size=size,
            )
            session.add(artifact)

    def get_artifacts(self, pipeline_id: str) -> list[Artifact]:
        """获取 Pipeline 的所有产物"""
        with session_scope() as session:
            artifacts = (
                session.query(Artifact)
                .filter(Artifact.pipeline_id == pipeline_id)
                .order_by(Artifact.created_at)
                .all()
            )
            for a in artifacts:
                session.expunge(a)
            return artifacts

    # ─── User ───

    def get_user_by_username(self, username: str) -> User | None:
        """按用户名查询用户"""
        with session_scope() as session:
            user = (
                session.query(User)
                .filter(User.username == username)
                .first()
            )
            if user:
                session.expunge(user)
            return user

    def get_user_by_api_key(self, api_key: str) -> User | None:
        """按 API Key 查询用户"""
        with session_scope() as session:
            user = (
                session.query(User).filter(User.api_key == api_key).first()
            )
            if user:
                session.expunge(user)
            return user

    def create_user(
        self,
        username: str,
        password_hash: str,
        role: str = "user",
        api_key: str | None = None,
    ) -> User:
        """创建用户"""
        with session_scope() as session:
            user = User(
                username=username,
                password_hash=password_hash,
                role=role,
                api_key=api_key,
            )
            session.add(user)
            session.flush()
            session.refresh(user)
            session.expunge(user)
            return user


# 全局单例
_repo: PipelineRepository | None = None


def get_repository() -> PipelineRepository:
    """获取全局 Repository 单例"""
    global _repo
    if _repo is None:
        _repo = PipelineRepository()
    return _repo
