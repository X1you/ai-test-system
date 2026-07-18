#!/usr/bin/env python3
"""
前端静态资源压缩脚本

将 web/static/ 下的 CSS/JS 压缩后输出到 web/static/dist/，
在保持功能不变的前提下减小传输体积 60-80%。

用法：
    python scripts/build_static.py
"""

import sys
from pathlib import Path

try:
    import rcssmin
    import rjsmin
except ImportError:
    print("错误：请先安装压缩工具：pip install rcssmin rjsmin", file=sys.stderr)
    sys.exit(1)


STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "static"
DIST_DIR = STATIC_DIR / "dist"

# 待压缩的文件清单：(文件名, 压缩器, 标签)
_FILES = [
    ("custom.css", rcssmin.cssmin, "CSS"),
    ("app.js", rjsmin.jsmin, "JS"),
]


def _minify(source: Path, target: Path, minifier, label: str):
    """压缩单个文件并打印压缩率"""
    content = source.read_text(encoding="utf-8")
    minified = minifier(content)
    target.write_text(minified, encoding="utf-8")
    ratio = (1 - len(minified) / len(content)) * 100 if content else 0
    print(f"  {label}: {source.name} "
          f"{len(content) // 1024}KB → {len(minified) // 1024}KB (-{ratio:.0f}%)")


def main():
    print("🔨 开始压缩前端静态资源...")
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    for filename, minifier, label in _FILES:
        src = STATIC_DIR / filename
        if src.exists():
            _minify(src, DIST_DIR / filename, minifier, label)
        else:
            print(f"  ⚠️  跳过不存在的文件: {filename}")

    print(f"\n✅ 压缩完成，输出目录: {DIST_DIR}")


if __name__ == "__main__":
    main()
