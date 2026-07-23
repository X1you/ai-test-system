# 🎼 Bard (吟游诗人) 图标资源管理规范

> **版本**：v4.1.0  
> **更新**：2026-07-22  
> **品牌主线**：吟游诗人演奏笛子 — 动态填充插画、单色流线型  
> **权威源文件**：`/Users/x1you/Downloads/bard.svg` (390×444 填充插画)

---

## 📁 目录结构

```
webui/src/assets/icons/
├── bard-flute.svg              # 主图标（Web 组件用，currentColor 自适应主题）
├── bard-flute-emoji.svg        # 白底黑线版（Favicon / 文档页眉 / 外部场景）
├── bard-flute-inverted.svg     # 黑底白线版（暗色徽章 / 终端）
├── bardIconData.js             # 路径数据模块（AUTO-GENERATED，供 Vue 组件导入）
├── generate_icons.py           # 生成脚本（Python + cairosvg，单一数据源）
├── manifest.json               # 资源清单（自动生成）
├── png/                        # 多尺寸 PNG（自动生成）
│   ├── bard-flute-{512,256,192,128,64,48,32,24,16,12}.png
│   ├── bard-flute-transparent-{...}.png
│   ├── bard-flute-inverted-{...}.png
│   └── …
└── README.md                   # 本文档
```

---

## 🎨 SVG 源文件三件套

| 文件 | 用途 | 颜色策略 | viewBox |
|------|------|----------|---------|
| `bard-flute.svg` | Web 组件、BardIcon、Sidebar Logo | `currentColor` 填充（自动适配主题） | 0 0 512 512 |
| `bard-flute-emoji.svg` | Favicon、PDF/Word 文档页眉、Markdown 徽章 | 白底圆 + `#080808` 填充 + 白色高光 | 0 0 512 512 |
| `bard-flute-inverted.svg` | 暗色徽章、终端主题 | 黑底圆 + `#ffffff` 填充 | 0 0 512 512 |

> ⚠️ **不要直接修改 `png/` 目录或 `bardIconData.js`** —— 这些文件由 `generate_icons.py` 从权威源文件 `bard.svg` 自动生成。每次源文件改动后需重新运行 `npm run icons:build`。

---

## 📐 PNG 规格对照表

### 三种变体

| 变体 | 文件前缀 | 背景 | 填充 | 典型场景 |
|------|----------|------|------|----------|
| **主品牌** | `bard-flute-` | 白底圆 | 黑 | 应用商店、文档、通用 |
| **透明版** | `bard-flute-transparent-` | 透明 | 黑 | 嵌入深色 HTML、邮件签名 |
| **反色版** | `bard-flute-inverted-` | 黑底圆 | 白 | 暗色 GitHub 徽章、终端主题 |

### 10 个尺寸

| 尺寸 | 用途 |
|------|------|
| **512×512** | 应用商店主图标 |
| **256×256** | PWA / macOS icon |
| **192×192** | PWA manifest |
| **128×128** | Windows 工具栏 / Linux desktop |
| **64×64** | Retina 工具栏 |
| **48×48** | 界面元素 |
| **32×32** | Favicon（标准） |
| **24×24** | 界面元素 |
| **16×16** | Favicon（旧浏览器） |
| **12×12** | 终端 / 极小徽章 |

> **命名规范**：`bard-flute[-{variant}]-{size}.png`  
> 示例：`bard-flute-256.png`、`bard-flute-inverted-32.png`

---

## 🔄 重建图标的单命令

```bash
cd webui
npm run icons:build
# 或直接运行：
DYLD_LIBRARY_PATH=/opt/homebrew/lib python3 src/assets/icons/generate_icons.py
```

**内部流程**：
1. 读取权威源文件 `bard.svg`（390×444 填充插画）
2. 按亮度分类路径（79 暗色主体 + 3 高光细节）
3. 计算内容 bbox → 规范化到 512×512 viewBox（居中，留 48px 边距）
4. 生成 3 个 SVG 变体（brand / emoji / inverted）
5. cairosvg 4x 超采样渲染 → 10 尺寸 × 3 变体 = **30 个 PNG**
6. Pillow 打包 16/32/48 → `public/favicon.ico`
7. 导出 `bardIconData.js`（路径数据模块，供 BardIcon.vue / FlowSpinner.vue 导入）
8. 写 `manifest.json` 资源清单

**依赖**：`cairosvg` + `pillow`（Python），系统库 `cairo`（macOS: `brew install cairo`）

---

## 🧩 在代码中使用

### ✅ 推荐：BardIcon 组件（统一接口）

```vue
<script setup>
import BardIcon from '@/components/BardIcon.vue'
</script>

<template>
  <!-- 侧边栏 Logo（带呼吸流光动画） -->
  <BardIcon :size="36" variant="brand" :animated="true" />

  <!-- 应用图标（白底黑线） -->
  <BardIcon :size="48" variant="emoji" />

  <!-- 深色徽章（黑底白线） -->
  <BardIcon :size="24" variant="inverted" />
</template>
```

### ✅ FlowSpinner 加载动画

```vue
<script setup>
import FlowSpinner from '@/components/FlowSpinner.vue'
</script>

<template>
  <FlowSpinner size="large" label="加载中" />
</template>
```

### ⚠️ 备选：直接引用 PNG

```html
<img src="/src/assets/icons/png/bard-flute-inverted-32.png" alt="Bard" />
```

### ❌ 反模式（禁止）

```vue
<!-- ❌ 不要在多个组件里复制粘贴 SVG path —— 用 bardIconData.js 统一导入 -->
<svg viewBox="0 0 512 512">
  <path d="M0,0 L7,0 L17,3..." />
</svg>
```

---

## 🛡️ 视觉一致性约束

### 设计语言
- **填充插画**（非描边线稿）：人物主体为实心填充，体现"动态、连续形态"
- **单色系**：黑、白、灰，无彩色 —— 这是"吟游诗人"品牌 DNA
- **流线型**：通过呼吸缩放动画（`bard-breathe`）传达流动感，而非 stroke 描边动画

### 颜色约束
- **Web 端**：必须用 `currentColor`，跟随 `tokens.css` 的主题 token
- **PNG 端**：emoji 变体硬编码 `#080808/#ffffff`；inverted 变体硬编码 `#ffffff/#0a0a0a`
- **不允许**：使用任何彩色（红/蓝/绿）

### 动效约束
- 所有动画必须使用 `--ease-flow` / `--ease-breath` token
- 不允许使用 `linear`（生硬）
- 填充插画用 opacity 呼吸 + scale 缩放，而非 stroke-dasharray
- 必须支持 `prefers-reduced-motion`

---

## 🔍 故障排查

| 现象 | 原因 | 解决 |
|------|------|------|
| `cairosvg` 报 `no library called cairo` | 系统未安装 cairo | macOS: `brew install cairo`，并设 `DYLD_LIBRARY_PATH=/opt/homebrew/lib` |
| 图标偏左上角 | 路径 transform 未保留 | 确认 `generate_icons.py` 提取了每条 path 的 `transform` 属性 |
| Sidebar Logo 静态不动 | `animated` prop 未传 | `<BardIcon :animated="true" />` |
| favicon.ico 不显示 | 浏览器版本太老 | 改用 `<link rel="icon" type="image/svg+xml" href="/favicon.svg">` |
| 路径数据不同步 | 手动编辑了 `bardIconData.js` | 重新运行 `npm run icons:build`（该文件 AUTO-GENERATED） |

---

## 🔗 相关资源

- 权威源文件：`/Users/x1you/Downloads/bard.svg`
- 主题 token：[`webui/src/styles/tokens.css`](../styles/tokens.css)
- BardIcon 组件：[`webui/src/components/BardIcon.vue`](../components/BardIcon.vue)
- FlowSpinner 组件：[`webui/src/components/FlowSpinner.vue`](../components/FlowSpinner.vue)
- 生成脚本：[`webui/src/assets/icons/generate_icons.py`](./generate_icons.py)
- 资源清单：[`webui/src/assets/icons/manifest.json`](./manifest.json)
