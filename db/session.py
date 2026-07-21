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
    """配置 SQLite PRAGMA：WAL 模式 + 外键约束

    仅对 SQLite 生效（db_path 以 .db 结尾或路径含 sqlite 时应用）。
    """
    # db_path 是文件路径（如 /data/app.db），用后缀和路径名判断是否 SQLite
    path_str = str(db_path).lower()
    if not (path_str.endswith(".db") or path_str.endswith(".sqlite") or "sqlite" in path_str):
        return

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=15000")
        cursor.close()


def _is_sqlite(url: str) -> bool:
    """判断是否 SQLite 数据库"""
    return url.startswith("sqlite")


def _build_engine_kwargs(url: str) -> dict:
    """根据数据库类型构建 engine 参数。

    SQLite: StaticPool + check_same_thread=False（单文件多线程）
    PostgreSQL（未来切换）: QueuePool 默认 + pool_pre_ping + pool_recycle，
        这两个参数解决长连接断线问题（数据库侧 idle_timeout / 云数据库
        主动断连后连接池里的死连接），SQLite 不需要也不兼容 pool_recycle。
    """
    kwargs: dict = {"echo": False}
    if _is_sqlite(url):
        # SQLite 单文件：StaticPool 保证多线程共用同一原生连接
        from sqlalchemy.pool import StaticPool

        kwargs["poolclass"] = StaticPool
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # PostgreSQL / MySQL 等网络数据库：启用连接健康检查 + 定期回收
        kwargs["pool_pre_ping"] = True  # 借出前 ping，剔除死连接
        kwargs["pool_recycle"] = 3600  # 连接最大存活 1 小时（< 服务端 idle_timeout）
    return kwargs


def get_engine() -> Engine:
    """获取/创建全局同步 Engine"""
    global _engine
    if _engine is None:
        db_path = _get_db_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)

        url = _get_database_url()
        _engine = create_engine(url, **_build_engine_kwargs(url))
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
    # 释放旧 engine 的连接池资源，防止文件描述符/连接泄漏
    if _engine is not None:
        try:
            _engine.dispose()
        except Exception:
            pass
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
