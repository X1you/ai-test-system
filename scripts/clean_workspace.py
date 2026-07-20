#!/usr/bin/env python3
"""
工作区清理脚本（uploads + output 磁盘泄漏防护）。

问题：
  - web/uploads/：每次启动 pipeline 上传需求文档，无清理机制
  - output/：interrupted 任务的空 output 目录持续堆积

策略（安全）：
  uploads:
    1. 扫描 DB 中 interrupted/paused 状态任务的 requirements_path（resume 仍需引用）
    2. 删除超过 --days 天且不被任何活跃任务引用的文件
  output:
    1. 删除文件数 ≤ --max-files 的空/近空目录（interrupted 任务遗留）
    2. 保留有产物的目录（≥ max-files 个文件）

  通用：
    - dry-run（默认）：只报告，加 --execute 才实际删除
    - 保留 .gitkeep，不删目录本身

用法：
  python scripts/clean_workspace.py                          # dry-run 全部
  python scripts/clean_workspace.py --execute                # 执行全部清理
  python scripts/clean_workspace.py --uploads --execute      # 只清 uploads
  python scripts/clean_workspace.py --output --execute       # 只清 output
  python scripts/clean_workspace.py --days 1 --execute
"""

import argparse
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = PROJECT_ROOT / "web" / "uploads"
OUTPUT_DIR = PROJECT_ROOT / "output"


def get_referenced_uploads() -> set[str]:
    """获取被 DB 中活跃任务（interrupted/paused/running/pending）引用的 uploads。"""
    referenced = set()
    try:
        from db.session import session_scope
        from db.models import Pipeline

        with session_scope() as s:
            rows = s.query(Pipeline).filter(
                Pipeline.status.in_(("interrupted", "paused", "running", "pending"))
            ).all()
            for p in rows:
                if p.requirements_path:
                    referenced.add(str(p.requirements_path))
    except Exception as e:
        print(f"⚠️  读取 DB 失败（保留所有文件以防误删）: {e}", file=sys.stderr)
    return referenced


def clean_uploads(days: int = 3, execute: bool = False) -> dict:
    """清理陈旧 uploads 文件。"""
    if not UPLOAD_DIR.exists():
        return {"total": 0, "would_delete": 0, "deleted": 0, "freed_bytes": 0}

    referenced = get_referenced_uploads()
    cutoff = datetime.now() - timedelta(days=days)

    all_files = [f for f in UPLOAD_DIR.iterdir() if f.is_file() and f.name != ".gitkeep"]
    to_delete = []
    kept_referenced = 0
    freed_bytes = 0

    for f in all_files:
        if str(f) in referenced:
            kept_referenced += 1
            continue
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        if mtime < cutoff:
            to_delete.append(f)
            freed_bytes += f.stat().st_size

    deleted = 0
    if execute:
        for f in to_delete:
            try:
                f.unlink()
                deleted += 1
            except OSError as e:
                print(f"⚠️  删除失败 {f.name}: {e}", file=sys.stderr)

    return {
        "total": len(all_files),
        "would_delete": len(to_delete),
        "kept_referenced": kept_referenced,
        "deleted": deleted,
        "freed_bytes": freed_bytes,
    }


def clean_output(max_files: int = 1, execute: bool = False) -> dict:
    """清理 output/ 下的空/近空目录（interrupted 任务遗留）。

    Args:
        max_files: 文件数 ≤ 此值的目录视为空，删除
        execute: False=dry-run，True=实际删除
    """
    if not OUTPUT_DIR.exists():
        return {"total_dirs": 0, "would_delete": 0, "deleted": 0, "freed_bytes": 0}

    all_dirs = [d for d in OUTPUT_DIR.iterdir() if d.is_dir()]
    to_delete = []
    kept = 0
    freed_bytes = 0

    for d in all_dirs:
        files = list(d.rglob("*"))
        file_count = sum(1 for f in files if f.is_file())
        if file_count <= max_files:
            to_delete.append(d)
            freed_bytes += sum(f.stat().st_size for f in files if f.is_file())
        else:
            kept += 1

    deleted = 0
    if execute:
        for d in to_delete:
            try:
                shutil.rmtree(d)
                deleted += 1
            except OSError as e:
                print(f"⚠️  删除失败 {d.name}: {e}", file=sys.stderr)

    return {
        "total_dirs": len(all_dirs),
        "would_delete": len(to_delete),
        "kept": kept,
        "deleted": deleted,
        "freed_bytes": freed_bytes,
    }


def fmt_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 / 1024:.1f} MB"


def main():
    parser = argparse.ArgumentParser(description="清理工作区（uploads + output）")
    parser.add_argument("--days", type=int, default=3, help="uploads: 超过 N 天才清理（默认 3）")
    parser.add_argument("--max-files", type=int, default=1, help="output: 文件数≤N 的目录视为空（默认 1）")
    parser.add_argument("--uploads", action="store_true", help="只清 uploads")
    parser.add_argument("--output", action="store_true", help="只清 output")
    parser.add_argument("--execute", action="store_true", help="实际执行删除（默认 dry-run）")
    args = parser.parse_args()

    # 默认两个都清
    do_uploads = args.uploads or not (args.uploads or args.output)
    do_output = args.output or not (args.uploads or args.output)

    mode = "执行" if args.execute else "dry-run（加 --execute 实际删除）"
    print(f"🧹 工作区清理（{mode}）\n")

    if do_uploads:
        print("📤 uploads 清理：")
        print(f"   保留：被活跃任务引用的 + {args.days} 天内的文件")
        r = clean_uploads(days=args.days, execute=args.execute)
        verb = "删除" if args.execute else "将删除"
        print(f"   总文件: {r['total']} | 保留(引用): {r['kept_referenced']} | {verb}: {r['would_delete']} | 释放: {fmt_bytes(r['freed_bytes'])}")
        if args.execute:
            print(f"   实际已删: {r['deleted']}")
        print()

    if do_output:
        print("📁 output 清理：")
        print(f"   删除文件数 ≤ {args.max_files} 的空目录（interrupted 任务遗留）")
        r = clean_output(max_files=args.max_files, execute=args.execute)
        verb = "删除" if args.execute else "将删除"
        print(f"   总目录: {r['total_dirs']} | {verb}: {r['would_delete']} | 保留: {r['kept']} | 释放: {fmt_bytes(r['freed_bytes'])}")
        if args.execute:
            print(f"   实际已删: {r['deleted']}")


if __name__ == "__main__":
    main()
