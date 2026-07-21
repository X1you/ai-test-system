#!/usr/bin/env bash
# PostgreSQL 逻辑备份脚本
# 用法：./backup_postgres.sh [BACKUP_DIR]
set -euo pipefail

BACKUP_DIR="${1:-/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# 从环境变量读取连接信息
PG_HOST="${POSTGRES_HOST:-postgres}"
PG_PORT="${POSTGRES_PORT:-5432}"
PG_USER="${POSTGRES_USER:-aitest}"
PG_DB="${POSTGRES_DB:-aitest}"

mkdir -p "$BACKUP_DIR"

BACKUP_FILE="$BACKUP_DIR/pg_${TIMESTAMP}.sql.gz"

# 自定义格式备份（支持并行恢复 + 选择性恢复）
pg_dump -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" \
  --format=custom --no-owner --no-privileges |
  gzip > "$BACKUP_FILE"

echo "[$(date)] PostgreSQL backup completed: $BACKUP_FILE"

# 清理过期备份
find "$BACKUP_DIR" -name "pg_*.sql.gz" -mtime +"$RETENTION_DAYS" -delete
echo "[$(date)] Cleaned backups older than ${RETENTION_DAYS} days"
