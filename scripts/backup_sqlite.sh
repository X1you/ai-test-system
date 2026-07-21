#!/usr/bin/env bash
# SQLite 在线备份脚本 — 使用 .backup 命令保证一致性
# 用法：./backup_sqlite.sh [DB_PATH] [BACKUP_DIR]
set -euo pipefail

DB_PATH="${1:-/app/data/app.db}"
BACKUP_DIR="${2:-/app/data/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

mkdir -p "$BACKUP_DIR"

# 使用 SQLite .backup 命令（在线备份，不阻塞写入）
BACKUP_FILE="$BACKUP_DIR/app_${TIMESTAMP}.db"
sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"

# 压缩节省空间
gzip "$BACKUP_FILE"

echo "[$(date)] Backup completed: ${BACKUP_FILE}.gz"

# 清理过期备份
find "$BACKUP_DIR" -name "app_*.db.gz" -mtime +"$RETENTION_DAYS" -delete
echo "[$(date)] Cleaned backups older than ${RETENTION_DAYS} days"
