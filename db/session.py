#!/usr/bin/env python3
"""
SQLAlchemy Session 管理 — Engine + SessionFactory

支持同步和异步两种引擎：
  - 同步引擎（默认）：用于 CLI / 脚本 / 简单查询
  - 异步引擎：用于 FastAPI 异步路由

SQLite 配置：
  - WAL 模式（提升并发读写）
  - 外键约束开启
  - 连接池：StaticPool（SQLite 单文件）
"""

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base

# ─── 数据库路径 ───

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _get_db_path() -> Path:
    """获取 SQLite 数据库文件路径"""
    # 支持环境变量覆盖（用于测试）
    env_path = os.environ.get("DATABASE_PATH")
    if env_path:
        return Path(env_path)
    return PROJECT_ROOT / "data" / "app.db"


def _get_database_url() -> str:
    """获取数据库 URL"""
    db_path = _get_db_path()
    # SQLite URL 格式
    return f"sqlite:///{db_path}"


# ─── 同步引擎 ───

_engine: Engine | None = None
_SessionFactory: sessionmaker | None = None


def _configure_sqlite_pragma(db_path: Path, engine: Engine):
    """配置 SQLite PRAGMA：WAL 模式 + 外键约束"""
    if "sqlite" not in str(db_path):
        return

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


def get_engine() -> Engine:
    """获取/创建全局同步 Engine"""
    global _engine
    if _engine is None:
        db_path = _get_db_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)

        url = f"sqlite:///{db_path}"
        _engine = create_engine(
            url,
            echo=False,
            # SQLite 需要使用 StaticPool 以支持多线程
            connect_args={"check_same_thread": False},
        )
        _configure_sqlite_pragma(db_path, _engine)
    return _engine


def get_session_factory() -> sessionmaker:
    """获取/创建全局 SessionFactory"""
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(
            bind=get_engine(), expire_on_commit=False
        )
    return _SessionFactory


def get_session() -> Session:
    """获取一个新的 DB Session"""
    return get_session_factory()()


def init_db():
    """初始化数据库 — 创建所有表"""
    engine = get_engine()
    Base.metadata.create_all(engine)


def reset_engine():
    """重置引擎缓存（主要用于测试切换数据库）"""
    global _engine, _SessionFactory
    _engine = None
    _SessionFactory = None


# ─── 上下文管理器 ───

from contextlib import contextmanager


@contextmanager
def session_scope():
    """事务作用域上下文管理器

    用法：
        with session_scope() as session:
            session.add(obj)
    """
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
