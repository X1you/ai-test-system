#!/usr/bin/env python3
"""
SQLAlchemy 数据模型 — Track A 基线

四张核心表：
  - Pipeline      Pipeline 实例
  - PipelineStep  每步执行记录
  - Artifact      产物元数据
  - User          用户（认证）

所有表预留 tenant_id 字段用于 Track B 多租户演进。
"""

from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""
    pass


class Pipeline(Base):
    """Pipeline 实例"""

    __tablename__ = "pipelines"

    __table_args__ = (
        Index("ix_pipelines_status_started_at", "status", "started_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    requirements_path: Mapped[str] = mapped_column(String(512))
    mode: Mapped[str] = mapped_column(String(16), default="semi")
    dimensions: Mapped[str] = mapped_column(String(64), default="basic")
    formats: Mapped[str] = mapped_column(String(64), default="excel")
    status: Mapped[str] = mapped_column(String(16), default="pending")
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_dir: Mapped[str] = mapped_column(String(512), default="")

    # Track B 预留字段
    tenant_id: Mapped[str | None] = mapped_column(
        String(32), nullable=True, index=True
    )
    workflow_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )

    steps: Mapped[list["PipelineStep"]] = relationship(
        back_populates="pipeline", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list["Artifact"]] = relationship(
        back_populates="pipeline", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Pipeline {self.id} status={self.status}>"


class PipelineStep(Base):
    """Pipeline 步骤执行记录"""

    __tablename__ = "pipeline_steps"

    __table_args__ = (
        Index("ix_pipeline_steps_pipeline_step", "pipeline_id", "step_id", unique=True),
        Index("ix_pipeline_steps_status", "status"),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    pipeline_id: Mapped[str] = mapped_column(
        ForeignKey("pipelines.id", ondelete="CASCADE")
    )
    step_id: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    # Track B 预留
    llm_calls: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON 格式的 LLM 调用详情
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    pipeline: Mapped["Pipeline"] = relationship(back_populates="steps")

    def __repr__(self) -> str:
        return f"<PipelineStep {self.step_id} status={self.status}>"


class Artifact(Base):
    """Pipeline 产物元数据"""

    __tablename__ = "artifacts"

    __table_args__ = (
        Index("ix_artifacts_pipeline_id", "pipeline_id"),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    pipeline_id: Mapped[str] = mapped_column(
        ForeignKey("pipelines.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(32))  # md / xlsx / xmind / json
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    pipeline: Mapped["Pipeline"] = relationship(back_populates="artifacts")

    def __repr__(self) -> str:
        return f"<Artifact {self.name} type={self.type}>"


class User(Base):
    """用户模型"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    username: Mapped[str] = mapped_column(
        String(64), unique=True, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="user")
    api_key: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    # Track B 预留
    tenant_id: Mapped[str | None] = mapped_column(
        String(32), nullable=True, index=True
    )

    def __repr__(self) -> str:
        return f"<User {self.username} role={self.role}>"


class KBConfig(Base):
    """知识库动态配置（Sprint 6.0）

    替代 config.yaml 静态读取，支持运行时热切换 + 冷启动容错。
    同时仅一行 is_active=True 的记录生效。
    """
    __tablename__ = "kb_configs"
    __table_args__ = (
        Index("ix_kb_configs_active", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # obsidian_api / mcp_filesystem / dummy
    provider_type: Mapped[str] = mapped_column(String(32), default="obsidian_api")
    # Obsidian Local REST API 的 base_url，或 MCP server 的连接 URL
    connection_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Bearer token 或 API key
    auth_token: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # 本地 Vault 路径（mcp_filesystem provider 必填）
    vault_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    def __repr__(self) -> str:
        return f"<KBConfig id={self.id} provider={self.provider_type} active={self.is_active}>"
