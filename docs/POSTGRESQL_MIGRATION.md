# PostgreSQL 迁移指南

## 概述

本系统从 P1#9 起完全支持 PostgreSQL。数据库层（`db/`）已通过以下改造实现双数据库兼容：

- `db/session.py`：运行时检测 `DATABASE_URL` 协议，自动选择连接池策略
- `db/repository.py`：upsert 操作按方言（SQLite/PostgreSQL）选择对应编译器
- `db/models.py`：所有类型标注使用 SQLAlchemy 跨方言类型（`String`/`Text`/`Boolean`/`DateTime`）
- `db/migrations/`：Alembic 迁移脚本使用 `op.create_table` 等标准操作，无方言专属 SQL

## 迁移步骤

### 1. 安装 PostgreSQL 驱动

```bash
pip install -e ".[postgresql]"
# 或直接安装
pip install "psycopg[binary]>=3.1"
```

### 2. 启动 PostgreSQL 实例

**方式 A：Docker Compose（推荐开发环境）**

```bash
docker compose up -d
# 等待就绪（~3 秒）
docker compose exec postgres pg_isready -U aitest
```

**方式 B：已有 PostgreSQL 实例**

创建数据库和用户（需超级用户权限）：

```sql
CREATE USER aitest WITH PASSWORD 'your_password';
CREATE DATABASE aitest OWNER aitest;
GRANT ALL PRIVILEGES ON DATABASE aitest TO aitest;
```

### 3. 设置环境变量

```bash
export DATABASE_URL="postgresql+psycopg://aitest:aitest@localhost:5432/aitest"
```

> **驱动说明**：`postgresql+psycopg` 表示使用 psycopg3（SQLAlchemy 2.0 推荐）。
> 如需旧版 psycopg2，用 `postgresql+psycopg2://` 并安装 `psycopg2-binary`。

### 4. 运行数据库迁移

```bash
alembic upgrade head
```

### 5. （可选）迁移现有 SQLite 数据

```bash
# 导出 SQLite 数据
sqlite3 data/app.db .dump > /tmp/backup.sql

# 转换并导入 PostgreSQL（需手动调整 DDL 语法差异）
# 推荐用 pgloader 工具自动化迁移：
#   pgloader data/app.db postgresql://aitest:aitest@localhost/aitest
```

### 6. 启动应用

```bash
# 正常启动，无需额外配置
python -m web.app
# 或
make run
```

## 验证

迁移完成后执行验证：

```bash
# 检查表是否创建
docker compose exec postgres psql -U aitest -c "\dt"

# 运行数据库相关测试
pytest tests/ -k "repository or db or migration" -v

# 全量回归
pytest tests/ -v
```

## 回退方案

如需回退到 SQLite：

1. 注释掉 `DATABASE_URL` 环境变量
2. 重启应用（自动回退到 `data/app.db`）
3. SQLite 数据文件未受影响

## 连接池配置

| 参数 | SQLite | PostgreSQL |
|------|--------|------------|
| 池类型 | StaticPool | QueuePool（默认） |
| check_same_thread | True | — |
| pool_pre_ping | — | True（借出前检查死连接） |
| pool_recycle | — | 3600s（< 服务端 idle_timeout） |
| WAL 模式 | ✅ | —（PG 用 MVCC） |
| 外键约束 | PRAGMA foreign_keys=ON | ✅ 原生支持 |

## 常见问题

### Q: 切换后报 `ModuleNotFoundError: No module named 'psycopg'`

A: 未安装 PostgreSQL 驱动。执行 `pip install -e ".[postgresql]"`。

### Q: 连接超时 / Connection refused

A: 检查 PostgreSQL 是否运行、端口是否正确、防火墙是否放行。

### Q: Alembic 迁移报错

A: 确保 `DATABASE_URL` 在运行 alembic 前已设置。Alembic 通过 `db/session.py:_get_database_url()` 读取此变量。

### Q: 测试如何覆盖 PostgreSQL

A: 设置 `DATABASE_URL` 指向测试用 PostgreSQL 后运行 `pytest`。测试框架自动适配。
GitHub Actions CI 可添加 PostgreSQL service container 进行自动化测试。
