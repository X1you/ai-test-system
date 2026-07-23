#!/usr/bin/env python3
"""
Bard Icon Generator (Version Four — filled illustration)
═══════════════════════════════════════════════════════════
权威源文件: /Users/x1you/Downloads/bard.svg  (390×444, filled B/W illustration)

本脚本将源文件规范化到 512×512 viewBox，生成三种变体：
  - brand      : currentColor 填充，透明背景（Web 组件用，自适应主题）
  - emoji      : 白底黑线（Favicon / 文档页眉 / 外部展示）
  - inverted   : 黑底白线（暗色徽章 / 终端）

并渲染所有尺寸的 PNG (12-512px) + favicon.ico + manifest.json。

用法:
  DYLD_LIBRARY_PATH=/opt/homebrew/lib python3 generate_icons.py
═══════════════════════════════════════════════════════════
"""
import re, json, os
from pathlib import Path
from datetime import datetime, timezone

os.environ.setdefault('DYLD_LIBRARY_PATH', '/opt/homebrew/lib')

import cairosvg
from PIL import Image

# LANCZOS 在新版 Pillow 中更名为 Resampling.LANCZOS
try:
    RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:  # Pillow < 9.1
    RESAMPLE = Image.LANCZOS

# ─── 路径配置 ───
SOURCE_SVG = Path('/Users/x1you/Downloads/bard.svg')
ICONS_DIR = Path(__file__).parent                     # .../src/assets/icons/
PNG_DIR = ICONS_DIR / 'png'
PUBLIC_DIR = ICONS_DIR.parents[2] / 'public'           # .../webui/public/

SIZES = [512, 256, 192, 128, 64, 48, 32, 24, 16, 12]

# ─── 读取源文件 ───
SRC = SOURCE_SVG.read_text()
# 源 viewBox = 390×444。规范化到 512×512，居中，留 ~12.5% padding。
SRC_W, SRC_H = 390, 444
CANVAS = 512
PAD = 32  # 边距像素 (512 的 ~6%)
scale = (CANVAS - 2 * PAD) / SRC_H  # 以高度为约束
offset_x = (CANVAS - SRC_W * scale) / 2
offset_y = (CANVAS - SRC_H * scale) / 2

# 提取源文件内部 path 元素
inner_start = SRC.index('<path')
inner = SRC[inner_start:SRC.rindex('</svg>')].strip()

# ─── 按填充亮度分类 path（保留每条 path 的 transform 属性） ───
def luminance(fill_hex):
    r = int(fill_hex[1:3], 16)
    g = int(fill_hex[3:5], 16)
    b = int(fill_hex[5:7], 16)
    return 0.299 * r + 0.587 * g + 0.114 * b

# 每条 path 提取 (d, fill, transform) 三元组
path_pattern = re.compile(
    r'<path\s+d="([^"]*)"[^>]*?fill="(#[0-9A-Fa-f]{6})"'
    r'(?:[^>]*?transform="([^"]*)")?[^>]*/>',
    re.DOTALL,
)
dark_paths = []   # 人物主体 (fill ≈ #08): list of (d, fill, transform)
light_paths = []  # 高光细节 (fill ≈ #F5)
for m in path_pattern.finditer(inner):
    d, fill, tf = m.group(1), m.group(2), (m.group(3) or '').strip()
    if 'L390,0 L390,444' in d:  # 跳过白色背景矩形
        continue
    entry = (d.strip(), fill, tf)
    (dark_paths if luminance(fill) < 128 else light_paths).append(entry)

# ─── 计算内容实际 bbox（含各 path transform），用于精确居中 ───
def num_bbox(d, tf):
    """近似 bbox：提取 path 数据中的所有数值，叠加 translate。"""
    nums = [float(x) for x in re.findall(r'-?[\d.]+', d)]
    xs, ys = nums[0::2], nums[1::2]
    tx = ty = 0.0
    tm = re.search(r'translate\(([^)]+)\)', tf)
    if tm:
        parts = [p.strip() for p in tm.group(1).split(',')]
        tx = float(parts[0])
        ty = float(parts[1]) if len(parts) > 1 else 0.0
    return min(xs) + tx, min(ys) + ty, max(xs) + tx, max(ys) + ty

all_xy = [num_bbox(d, tf) for d, _, tf in dark_paths + light_paths]
c_min_x = min(b[0] for b in all_xy)
c_min_y = min(b[1] for b in all_xy)
c_max_x = max(b[2] for b in all_xy)
c_max_y = max(b[3] for b in all_xy)
content_w = c_max_x - c_min_x
content_h = c_max_y - c_min_y

# 规范化到 512×512，内容居中，留 PAD 边距
PAD = 48
TARGET = CANVAS - 2 * PAD
scale = TARGET / max(content_w, content_h)
offset_x = (CANVAS - content_w * scale) / 2 - c_min_x * scale
offset_y = (CANVAS - content_h * scale) / 2 - c_min_y * scale

# ─── SVG 变体构建器 ───
def path_tag(d, fill, tf=''):
    """生成 <path> 标签，保留原始 transform 属性。"""
    tattr = f' transform="{tf}"' if tf else ''
    return f'<path d="{d}" fill="{fill}"{tattr}/>'

def build_svg(content, bg_circle=None, title="Bard"):
    circle = ''
    if bg_circle:
        circle = (f'<circle cx="256" cy="256" r="252" '
                  f'fill="{bg_circle["fill"]}" stroke="{bg_circle["stroke"]}" stroke-width="3"/>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" '
        f'role="img" aria-label="Bard">\n'
        f'<title>{title}</title>\n'
        f'{circle}\n'
        f'<g transform="translate({offset_x:.2f},{offset_y:.2f}) scale({scale:.4f})">\n'
        f'{content}\n'
        f'</g>\n</svg>'
    )

# 1. BRAND: currentColor 填充人物主体，透明背景
brand_content = '\n'.join(path_tag(d, 'currentColor', tf) for d, _, tf in dark_paths)
BRAND_SVG = build_svg(brand_content)

# 2. EMOJI: 白底圆 + 黑色人物 + 白色高光
emoji_content = ('\n'.join(path_tag(d, '#080808', tf) for d, _, tf in dark_paths) + '\n' +
                 '\n'.join(path_tag(d, '#ffffff', tf) for d, _, tf in light_paths))
EMOJI_SVG = build_svg(emoji_content, bg_circle={"fill": "#ffffff", "stroke": "#000000"})

# 3. INVERTED: 黑底圆 + 白色人物
inverted_content = '\n'.join(path_tag(d, '#ffffff', tf) for d, _, tf in dark_paths)
INVERTED_SVG = build_svg(inverted_content, bg_circle={"fill": "#0a0a0a", "stroke": "#ffffff"})


def render_png(svg_str, out_path, size):
    """用 cairosvg 渲染 SVG → PNG，超采样 4x 后缩放以获得更平滑的边缘。"""
    ss = size * 4
    cairosvg.svg2png(bytestring=svg_str.encode('utf-8'),
                     write_to=str(out_path),
                     output_width=ss, output_height=ss)
    if size != ss:
        img = Image.open(out_path)
        img = img.resize((size, size), RESAMPLE)
        img.save(out_path, 'PNG')


def main():
    PNG_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)

    # ─── 写入规范 SVG ───
    (ICONS_DIR / 'bard-flute.svg').write_text(BRAND_SVG)
    (ICONS_DIR / 'bard-flute-emoji.svg').write_text(EMOJI_SVG)
    (ICONS_DIR / 'bard-flute-inverted.svg').write_text(INVERTED_SVG)

    # ─── 写入 bardIconData.js（供 BardIcon.vue / FlowSpinner.vue 导入） ───
    norm = lambda s: re.sub(r'\s+', ' ', s).strip()
    # 导出 [{d, tf}, ...] 数组，保留每条 path 的 transform
    def js_path_objs(paths, ind='  '):
        lines = []
        for d, _, tf in paths:
            lines.append(f'{ind}{{ d: "{norm(d)}", tf: "{norm(tf)}" }},')
        return '\n'.join(lines)
    data_module = (
        '/**\n'
        ' * Bard 图标路径数据 (AUTO-GENERATED — 请勿手动编辑)\n'
        ' * 源文件: /Users/x1you/Downloads/bard.svg (390×444 填充插画)\n'
        f' * 生成时间: {datetime.now(timezone.utc).isoformat()}\n'
        ' */\n'
        f"export const BARD_TRANSFORM = 'translate({offset_x:.2f},{offset_y:.2f}) scale({scale:.4f})'\n\n"
        f'export const BARD_DARK_PATHS = [\n{js_path_objs(dark_paths)}\n]\n\n'
        f'export const BARD_LIGHT_PATHS = [\n{js_path_objs(light_paths)}\n]\n'
    )
    (ICONS_DIR / 'bardIconData.js').write_text(data_module)
    print(f'  ✓ bardIconData.js ({len(dark_paths)} dark + {len(light_paths)} light paths)')

    # ─── favicon.svg (使用 emoji 变体 — 白底黑线，浏览器友好) ───
    (PUBLIC_DIR / 'favicon.svg').write_text(EMOJI_SVG)
    (PUBLIC_DIR / 'bard-flute.svg').write_text(BRAND_SVG)

    # ─── 渲染所有 PNG 尺寸 ───
    variants = {
        '':          (BRAND_SVG, '白底黑线 — 默认主品牌'),      # 默认 = emoji 风格白底
        '-transparent': (BRAND_SVG, '透明背景 — 深色文档/HTML'),
        '-inverted':  (INVERTED_SVG, '黑底白线 — 暗色徽章'),
    }
    # 注：默认变体（无后缀）使用 emoji SVG（白底黑线），保持与现有引用一致
    variants[''] = (EMOJI_SVG, '白底黑线 — 默认主品牌')

    manifest_png = {'png_emoji': [], 'png_transparent': [], 'png_inverted': []}
    key_map = {'': 'png_emoji', '-transparent': 'png_transparent', '-inverted': 'png_inverted'}

    for suffix, (svg, desc) in variants.items():
        for size in SIZES:
            fname = f'bard-flute{suffix}-{size}.png'
            out = PNG_DIR / fname
            render_png(svg, out, size)
            manifest_png[key_map[suffix]].append(f'png/{fname}')
            print(f'  ✓ {fname} ({size}×{size})')

    # ─── 公共目录 PNG (favicon/app icon 常用尺寸) ───
    for size in [512, 256, 192, 32, 16]:
        render_png(EMOJI_SVG, PUBLIC_DIR / f'bard-flute-{size}.png', size)
    print('  ✓ public/ PNG icons')

    # ─── favicon.ico (多尺寸打包) ───
    ico_sizes = [16, 32, 48]
    ico_imgs = []
    for s in ico_sizes:
        tmp = PNG_DIR / f'_ico_{s}.png'
        render_png(EMOJI_SVG, tmp, s)
        ico_imgs.append(Image.open(tmp))
    ico_imgs[0].save(PUBLIC_DIR / 'favicon.ico',
                     format='ICO',
                     sizes=[(s, s) for s in ico_sizes])
    for s in ico_sizes:
        (PNG_DIR / f'_ico_{s}.png').unlink()
    print('  ✓ public/favicon.ico')

    # ─── manifest.json ───
    manifest = {
        'version': '4.1.0',
        'brand': 'Bard (吟游诗人) — AI Test System',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'source': str(SOURCE_SVG),
        'source_viewBox': f'0 0 {SRC_W} {SRC_H}',
        'normalized_viewBox': f'0 0 {CANVAS} {CANVAS}',
        'design': '动态填充插画 — 黑白连续形态，流线型',
        'sources': {
            'bard-flute.svg': {
                'usage': 'Web 组件 (currentColor 自适应主题)',
                'viewBox': '0 0 512 512',
                'style': 'filled silhouette, currentColor',
            },
            'bard-flute-emoji.svg': {
                'usage': 'Favicon / 文档页眉 / 外部展示 (白底黑线)',
                'viewBox': '0 0 512 512',
                'style': 'white circle bg, black figure + highlights',
            },
            'bard-flute-inverted.svg': {
                'usage': '暗色徽章 / 终端 (黑底白线)',
                'viewBox': '0 0 512 512',
                'style': 'black circle bg, white figure',
            },
        },
        **manifest_png,
        'favicon': {
            'ico': 'public/favicon.ico',
            'svg': 'public/favicon.svg',
            'sizes': ico_sizes,
        },
        'naming': {
            'pattern': 'bard-flute[-variant]-{size}.png',
            'variants': {
                '': '白底黑线 — 默认主品牌 (favicon/文档)',
                '-transparent': '透明背景 — 深色文档/HTML 组件内联',
                '-inverted': '黑底白线 — 暗色徽章/终端',
            },
            'sizes': SIZES,
        },
    }
    (ICONS_DIR / 'manifest.json').write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False))

    print('\n✅ All icons generated successfully.')
    print(f'   SVG variants: 3 | PNG files: {len(SIZES)*3 + len(ico_sizes)} | '
          f'Dark paths: {len(dark_paths)} | Light paths: {len(light_paths)}')


if __name__ == '__main__':
    main()
