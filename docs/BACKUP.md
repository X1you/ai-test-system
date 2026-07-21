# 数据库自动备份方案

## 概述

本文档描述 AI 测试用例生成系统的数据库自动备份配置，支持 SQLite 和 PostgreSQL 两种部署模式。

## SQLite 备份方案

### 备份脚本

创建 `scripts/backup_sqlite.sh`：

```bash
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
```

### Cron 配置

在宿主机或容器内配置 crontab：

```bash
# 编辑 crontab
crontab -e

# 每天凌晨 2:00 执行备份
0 2 * * * /app/scripts/backup_sqlite.sh >> /app/data/logs/backup.log 2>&1
```

### Docker 环境下使用

在 `docker-compose.yml` 中添加备份 sidecar 容器：

```yaml
services:
  backup:
    image: alpine:latest
    command: >
      sh -c "apk add --no-cache sqlite &&
             echo '0 2 * * * /app/scripts/backup_sqlite.sh >> /var/log/backup.log 2>&1' > /etc/crontabs/root &&
             crond -f -l 2"
    volumes:
      - ./data:/app/data
      - ./scripts:/app/scripts
      - ./data/backups:/app/data/backups
      - ./data/logs:/var/log
    restart: unless-stopped
```

## PostgreSQL 备份方案

### pg_dump 备份脚本

创建 `scripts/backup_postgres.sh`：

```bash
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
```

### Docker Compose 集成

在 `docker-compose.postgres.yml` 中添加备份服务：

```yaml
services:
  backup:
    image: postgres:16-alpine
    environment:
      POSTGRES_HOST: postgres
      POSTGRES_USER: ${POSTGRES_USER:-aitest}
      POSTGRES_DB: ${POSTGRES_DB:-aitest}
      BACKUP_RETENTION_DAYS: "30"
    command: >
      sh -c "echo '0 2 * * * /scripts/backup_postgres.sh >> /var/log/backup.log 2>&1' > /etc/crontabs/root &&
             crond -f -l 2"
    volumes:
      - ./scripts/backup_postgres.sh:/scripts/backup_postgres.sh:ro
      - ./backups:/backups
      - ./logs:/var/log
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped
```

## 恢复流程

### SQLite 恢复

```bash
# 1. 停止应用
docker-compose stop app

# 2. 恢复备份
gunzip -c /app/data/backups/app_20250101_020000.db.gz > /app/data/app.db

# 3. 重启应用
docker-compose start app
```

### PostgreSQL 恢复

```bash
# 1. 停止应用（保持 postgres 运行）
docker-compose stop app

# 2. 恢复备份
gunzip -c /backups/pg_20250101_020000.sql.gz | \
  pg_restore -h postgres -U aitest -d aitest --clean --if-exists

# 3. 重启应用
docker-compose start app
```

## 备份验证

建议每周验证一次备份可恢复性：

```bash
# SQLite 验证
sqlite3 /tmp/verify.db ".recover" < <(gunzip -c /app/data/backups/app_latest.db.gz)
sqlite3 /tmp/verify.db "SELECT COUNT(*) FROM pipelines;"

# PostgreSQL 验证
createdb verify_aitest
pg_restore -h postgres -U aitest -d verify_aitest < <(gunzip -c /backups/pg_latest.sql.gz)
psql -h postgres -U aitest -d verify_aitest -c "SELECT COUNT(*) FROM pipelines;"
dropdb verify_aitest
```

## 备份策略建议

| 策略 | 频率 | 保留 | 说明 |
|------|------|------|------|
| 全量备份 | 每日 02:00 | 30 天 | 低峰期执行，减少影响 |
| 周备份 | 每周日 01:00 | 12 周 | 长期保留，应对延迟发现的数据问题 |
| 手动备份 | 变更前 | 永久 | 重大版本升级 / 数据迁移前手动执行 |
