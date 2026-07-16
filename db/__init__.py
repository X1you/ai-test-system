"""
数据持久化层 — SQLAlchemy 数据模型 + Repository + Session 管理

Track A 使用 SQLite (WAL 模式)；
Track B 可无缝切换 PostgreSQL（仅需修改 DATABASE_URL）。
"""
