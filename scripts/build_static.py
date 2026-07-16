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


def minify_css(source: Path, target: Path):
    """压缩 CSS"""
    content = source.read_text(encoding="utf-8")
    minified = rcssmin.cssmin(content)
    target.write_text(minified, encoding="utf-8")
    ratio = (1 - len(minified) / len(content)) * 100 if content else 0
    print(f"  CSS: {source.name} {len(content)//1024}KB → {len(minified)//1024}KB (-{ratio:.0f}%)")


def minify_js(source: Path, target: Path):
    """压缩 JS"""
    content = source.read_text(encoding="utf-8")
    minified = rjsmin.jsmin(content)
    target.write_text(minified, encoding="utf-8")
    ratio = (1 - len(minified) / len(content)) * 100 if content else 0
    print(f"  JS:  {source.name} {len(content)//1024}KB → {len(minified)//1024}KB (-{ratio:.0f}%)")


def main():
    print("🔨 开始压缩前端静态资源...")
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    # 压缩 CSS
    for css_file in ["custom.css"]:
        src = STATIC_DIR / css_file
        if src.exists():
            minify_css(src, DIST_DIR / css_file)

    # 压缩 JS
    for js_file in ["app.js"]:
        src = STATIC_DIR / js_file
        if src.exists():
            minify_js(src, DIST_DIR / js_file)

    print(f"\n✅ 压缩完成，输出目录: {DIST_DIR}")


if __name__ == "__main__":
    main()
