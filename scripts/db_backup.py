#!/usr/bin/env python3
"""SQLite 数据库定时备份脚本。

用法：
    python scripts/db_backup.py              # 立即备份一次
    python scripts/db_backup.py --keep 7     # 保留最近 7 份备份（默认 5）
    python scripts/db_backup.py --dry-run    # 仅打印将要执行的操作

备份策略：
    - 使用 SQLite Online Backup API（sqlite3.backup），保证一致性
    - 备份文件存放于 data/backups/，命名格式 app_YYYYMMDD_HHMMSS.db
    - 自动清理超过 --keep 数量的旧备份
    - 适合 cron 定时调用：0 */6 * * * cd /path/to/project && python scripts/db_backup.py

退出码：
    0 = 成功
    1 = 备份失败（源文件不存在/不可读/磁盘空间不足）
"""

import argparse
import shutil
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "app.db"
BACKUP_DIR = PROJECT_ROOT / "data" / "backups"


def backup(db_path: Path, backup_dir: Path, keep: int = 5, dry_run: bool = False) -> Path | None:
    """执行一次 SQLite 在线备份，返回备份文件路径。"""
    if not db_path.exists():
        print(f"[ERROR] 数据库文件不存在: {db_path}", file=sys.stderr)
        sys.exit(1)

    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"app_{timestamp}.db"

    if dry_run:
        print(f"[DRY-RUN] 将备份 {db_path} -> {backup_file}")
        print(f"[DRY-RUN] 保留最近 {keep} 份备份")
        return None

    # SQLite Online Backup API — 保证备份一致性（即使有并发写入）
    start = time.monotonic()
    try:
        src = sqlite3.connect(str(db_path))
        dst = sqlite3.connect(str(backup_file))
        src.backup(dst)
        dst.close()
        src.close()
    except Exception as e:
        # 清理不完整的备份文件
        backup_file.unlink(missing_ok=True)
        print(f"[ERROR] 备份失败: {e}", file=sys.stderr)
        sys.exit(1)

    elapsed = time.monotonic() - start
    size_mb = backup_file.stat().st_size / (1024 * 1024)
    print(f"[OK] 备份完成: {backup_file.name} ({size_mb:.1f} MB, {elapsed:.2f}s)")

    # 清理旧备份（按文件名排序，保留最近 keep 份）
    backups = sorted(backup_dir.glob("app_*.db"), reverse=True)
    for old in backups[keep:]:
        old.unlink()
        print(f"[CLEAN] 删除旧备份: {old.name}")

    return backup_file


def main():
    parser = argparse.ArgumentParser(description="SQLite 数据库备份")
    parser.add_argument("--keep", type=int, default=5, help="保留最近 N 份备份（默认 5）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印操作，不实际执行")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="数据库文件路径")
    parser.add_argument("--backup-dir", type=Path, default=BACKUP_DIR, help="备份存放目录")
    args = parser.parse_args()

    backup(args.db, args.backup_dir, keep=args.keep, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
