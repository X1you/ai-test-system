#!/usr/bin/env python3
"""
清理 web/uploads 中的陈旧需求文档（磁盘泄漏防护）。

问题：每次启动 pipeline 都上传一份需求文档到 web/uploads/，
没有任何清理机制，1917 个文件持续堆积（7.2M+）。

策略（安全）：
  1. 扫描 DB 中 interrupted/paused 状态任务的 requirements_path（resume 仍需引用）
  2. 删除 uploads/ 中超过 --days 天且不被任何活跃任务引用的文件
  3. 保留 .gitkeep，不删目录本身
  4. dry-run 模式（默认）：只报告将删除什么，不实际删除
     加 --execute 才真正删除

用法：
  python scripts/clean_uploads.py            # dry-run，看会删什么
  python scripts/clean_uploads.py --execute  # 实际执行
  python scripts/clean_uploads.py --days 7 --execute
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = PROJECT_ROOT / "web" / "uploads"


def get_referenced_uploads() -> set[str]:
    """获取被 DB 中活跃任务（interrupted/paused/done/error）引用的 uploads 路径。

    resume 需要引用 requirements_path，不能删这些文件。
    """
    referenced = set()
    try:
        from db.session import session_scope
        from db.models import Pipeline

        with session_scope() as s:
            # interrupted/paused 任务可能 resume，保留它们的 requirements
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
    """清理陈旧 uploads 文件。

    Args:
        days: 超过 N 天的文件才清理
        execute: False=dry-run（只报告），True=实际删除

    Returns:
        {"total": N, "would_delete": N, "kept_referenced": N, "deleted": N, "freed_bytes": N}
    """
    if not UPLOAD_DIR.exists():
        return {"total": 0, "would_delete": 0, "deleted": 0, "freed_bytes": 0}

    referenced = get_referenced_uploads()
    cutoff = datetime.now() - timedelta(days=days)

    all_files = [f for f in UPLOAD_DIR.iterdir() if f.is_file() and f.name != ".gitkeep"]
    to_delete = []
    kept_referenced = 0
    freed_bytes = 0

    for f in all_files:
        # 被活跃任务引用 → 跳过
        if str(f) in referenced:
            kept_referenced += 1
            continue
        # 超过 cutoff 的才删
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


def main():
    parser = argparse.ArgumentParser(description="清理 web/uploads 陈旧需求文档")
    parser.add_argument("--days", type=int, default=3, help="超过 N 天的文件才清理（默认 3）")
    parser.add_argument("--execute", action="store_true", help="实际执行删除（默认 dry-run）")
    args = parser.parse_args()

    print(f"📤 uploads 清理{'（执行模式）' if args.execute else '（dry-run，加 --execute 实际删除）'}")
    print(f"   保留：被 interrupted/paused 任务引用的 + {args.days} 天内的文件")
    print()

    result = clean_uploads(days=args.days, execute=args.execute)

    mode = "删除" if args.execute else "将删除"
    print(f"📊 扫描结果：")
    print(f"   总文件数:     {result['total']}")
    print(f"   保留（引用）:  {result['kept_referenced']}")
    print(f"   {mode}:       {result['would_delete']}")
    print(f"   释放空间:     {result['freed_bytes'] / 1024 / 1024:.1f} MB")
    if args.execute:
        print(f"   实际已删:     {result['deleted']}")


if __name__ == "__main__":
    main()
