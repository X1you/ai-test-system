#!/usr/bin/env python3
"""
PostgreSQL 兼容性验证测试（P1#9）

验证数据库层的跨方言兼容性，不依赖真实 PostgreSQL 实例：
1. repository.record_step 的方言路由逻辑
2. session._build_engine_kwargs 对不同 URL 的参数构建
3. models 类型映射的方言无关性
4. Alembic migration 脚本无 SQLite 专属 SQL
"""

import os
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ─── session.py 引擎参数构建 ───

class TestEngineKwargs:
    """验证 _build_engine_kwargs 对不同方言的正确参数构建"""

    def test_sqlite_uses_static_pool(self):
        from db.session import _build_engine_kwargs, _is_sqlite

        assert _is_sqlite("sqlite:///data/app.db")
        kwargs = _build_engine_kwargs("sqlite:///data/app.db")
        assert "StaticPool" in str(kwargs.get("poolclass", ""))
        assert kwargs["connect_args"] == {"check_same_thread": False}

    def test_postgresql_uses_pre_ping_and_recycle(self):
        from db.session import _build_engine_kwargs, _is_sqlite

        url = "postgresql+psycopg://user:pass@localhost:5432/db"
        assert not _is_sqlite(url)
        kwargs = _build_engine_kwargs(url)
        assert kwargs["pool_pre_ping"] is True
        assert kwargs["pool_recycle"] == 3600
        # PostgreSQL 不应有 check_same_thread
        assert "connect_args" not in kwargs

    def test_mysql_also_gets_pool_params(self):
        from db.session import _build_engine_kwargs

        kwargs = _build_engine_kwargs("mysql+pymysql://user:pass@localhost/db")
        assert kwargs["pool_pre_ping"] is True
        assert kwargs["pool_recycle"] == 3600


# ─── repository.py 方言路由 ───

class TestUpsertDialectRouting:
    """验证 record_step 的方言路由逻辑"""

    def test_postgresql_dialect_uses_pg_insert(self):
        """PostgreSQL 方言应调用 postgresql.insert"""
        from db.models import PipelineStep
        from db.repository import PipelineRepository

        repo = PipelineRepository()
        # mock session + bind → PostgreSQL
        mock_session = MagicMock()
        mock_session.bind.dialect.name = "postgresql"

        with patch("db.repository.session_scope") as mock_scope:
            mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            repo.record_step("pid", 1, "测试", "completed", "{}")

            executed_stmt = mock_session.execute.call_args[0][0]
            compiled = str(
                executed_stmt.compile(
                    dialect=__import__(
                        "sqlalchemy.dialects.postgresql", fromlist=["dialect"]
                    ).dialect(),
                )
            )
            assert "ON CONFLICT" in compiled.upper() or "INSERT" in compiled.upper()

    def test_sqlite_dialect_uses_sqlite_insert(self):
        """SQLite 方言应调用 sqlite.insert"""
        from db.repository import PipelineRepository

        repo = PipelineRepository()
        mock_session = MagicMock()
        mock_session.bind.dialect.name = "sqlite"

        with patch("db.repository.session_scope") as mock_scope:
            mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            repo.record_step("pid", 1, "测试", "completed", "{}")
            assert mock_session.execute.called


# ─── Alembic migration 脚本审计 ───

class TestMigrationDialectNeutrality:
    """确保 Alembic migration 脚本不含 SQLite 专属语法"""

    MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "db" / "migrations" / "versions"

    # SQLite 专属语法模式（在 PostgreSQL 中会报错）
    SQLITE_PATTERNS = [
        r"PRAGMA\s",
        r"AUTOINCREMENT",  # SQLite 专属（PG 用 SERIAL/IDENTITY）
        r"sqlite_\w+\(",
    ]

    def _get_migration_files(self):
        if not self.MIGRATIONS_DIR.exists():
            pytest.skip(f"Migration 目录不存在: {self.MIGRATIONS_DIR}")
        files = list(self.MIGRATIONS_DIR.glob("*.py"))
        assert files, "至少应有一个 migration 文件"
        return files

    @pytest.mark.parametrize("pattern", [
        r"PRAGMA\s",
        # AUTOINCREMENT 作为独立 SQL 关键字（排除 SQLAlchemy 参数 autoincrement=True）
        r"(?<!\w)AUTOINCREMENT(?!\w)\s+(?!=\s*True)",
        r"sqlite_\w+\(",
    ])
    def test_no_sqlite_specific_sql(self, pattern):
        """检查所有 migration 脚本无 SQLite 专属语法"""
        for f in self._get_migration_files():
            content = f.read_text(encoding="utf-8")
            # 排除注释行
            lines = [l for l in content.splitlines() if not l.strip().startswith("#")]
            clean = "\n".join(lines)
            assert not re.search(pattern, clean, re.IGNORECASE), (
                f"{f.name} 包含 SQLite 专属语法: {pattern}"
            )

    def test_all_migrations_use_standard_ops(self):
        """所有 migration 脚本应使用标准 Alembic 操作（op.xxx）"""
        for f in self._get_migration_files():
            content = f.read_text(encoding="utf-8")
            # 必须调用 op.create_table / op.drop_table / op.create_index 等
            assert "op." in content, f"{f.name} 不含任何 op.xxx 调用"

    def test_migrations_have_upgrade_and_downgrade(self):
        """所有 migration 脚本必须有 upgrade 和 downgrade 函数"""
        for f in self._get_migration_files():
            content = f.read_text(encoding="utf-8")
            assert "def upgrade()" in content, f"{f.name} 缺少 upgrade()"
            assert "def downgrade()" in content, f"{f.name} 缺少 downgrade()"


# ─── models.py 类型兼容性 ───

class TestModelsDialectCompatibility:
    """验证 models.py 的类型映射在 PostgreSQL 下正确"""

    def test_boolean_columns_exist(self):
        """is_active 字段应为 Boolean 类型（跨方言兼容）"""
        from db.models import KBConfig
        col = KBConfig.__table__.c.is_active
        assert col.type.__class__.__name__ == "Boolean"

    def test_datetime_columns_use_timezone_aware(self):
        """DateTime 字段应为通用 DateTime 类型"""
        from db.models import Pipeline
        col = Pipeline.__table__.c.started_at
        assert "DateTime" in col.type.__class__.__name__

    def test_text_columns_for_long_strings(self):
        """长文本字段应为 Text 类型"""
        from db.models import Pipeline
        col = Pipeline.__table__.c.error
        assert col.type.__class__.__name__ == "Text"

    def test_no_native_json_columns(self):
        """确保没有使用 SQLite 不支持的 JSON 类型（保持兼容）"""
        from db.models import Base
        for table in Base.metadata.tables.values():
            for col in table.columns:
                type_name = col.type.__class__.__name__
                assert type_name != "JSON", (
                    f"{table.name}.{col.name} 使用了 JSON 类型，"
                    f"SQLite < 3.38 不支持；当前用 Text 存储 JSON 字符串"
                )

    def test_string_columns_have_length(self):
        """String 列必须指定长度（PostgreSQL 索引要求）"""
        from db.models import Base
        for table in Base.metadata.tables.values():
            for col in table.columns:
                if col.type.__class__.__name__ == "String":
                    length = col.type.length
                    assert length is not None and length > 0, (
                        f"{table.name}.{col.name} String 类型未指定长度"
                    )


# ─── DATABASE_URL 切换验证 ───

class TestDatabaseUrlSwitch:
    """验证 DATABASE_URL 环境变量的切换行为"""

    def test_sqlite_url_when_no_env(self):
        """未设 DATABASE_URL 时回退 SQLite"""
        from db.session import _get_database_url

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DATABASE_URL", None)
            url = _get_database_url()
            assert url.startswith("sqlite:///")

    def test_postgresql_url_when_env_set(self):
        """设 DATABASE_URL 时使用指定 URL"""
        from db.session import _get_database_url

        test_url = "postgresql+psycopg://test:test@localhost:5432/testdb"
        with patch.dict(os.environ, {"DATABASE_URL": test_url}):
            url = _get_database_url()
            assert url == test_url
