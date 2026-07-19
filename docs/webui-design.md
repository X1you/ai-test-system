# AI Test System — WebUI 设计文档 v2.0

> 基于 Vercel Web Interface Guidelines + ui-ux-pro-max 规则体系
> 技术栈：Vue 3 + vue-router + Vite 6（零 UI 框架依赖，纯 CSS 变量驱动）

---

## 1. 设计原则

| # | 原则 | 说明 |
|---|------|------|
| 1 | 密度优先 | QA 工具 = 高信息密度，减少装饰性留白 |
| 2 | 暗黑为主 | 默认 dark，light 为备选（`color-scheme: dark`） |
| 3 | 单色相体系 | Indigo 243°，状态靠饱和度/亮度区分 |
| 4 | 实时可观测 | SSE 驱动，Pipeline 执行全程可视 |
| 5 | 零框架 | 不引入 Element/Ant/Naive，CSS 变量 + 原生语义 HTML |
| 6 | 渐进增强 | 无 JS 时 API 仍可用；SSE 降级为轮询 |

---

## 2. Design Tokens

### 2.1 色彩（Monochrome Indigo）

```css
:root {
  /* ─── 色相基础 ─── */
  --mono-hue: 243deg;

  /* ─── 语义色（Light） ─── */
  --bg-app: hsl(var(--mono-hue) 15% 97%);
  --bg-surface: hsl(0 0% 100%);
  --bg-surface-raised: hsl(var(--mono-hue) 20% 98%);
  --bg-inset: hsl(var(--mono-hue) 12% 94%);

  --text-primary: hsl(var(--mono-hue) 20% 12%);
  --text-secondary: hsl(var(--mono-hue) 10% 42%);
  --text-tertiary: hsl(var(--mono-hue) 8% 60%);

  --border-default: hsl(var(--mono-hue) 12% 88%);
  --border-strong: hsl(var(--mono-hue) 15% 78%);

  /* ─── 品牌/交互 ─── */
  --accent: hsl(var(--mono-hue) 72% 55%);
  --accent-hover: hsl(var(--mono-hue) 72% 47%);
  --accent-subtle: hsl(var(--mono-hue) 60% 95%);
  --accent-text: hsl(0 0% 100%);

  /* ─── 状态色（饱和度/亮度变体，非换色相） ─── */
  --status-running: hsl(var(--mono-hue) 72% 55%);
  --status-done: hsl(var(--mono-hue) 45% 40%);
  --status-paused: hsl(var(--mono-hue) 30% 55%);
  --status-error: hsl(var(--mono-hue) 80% 45%);
  --status-cancelled: hsl(var(--mono-hue) 8% 55%);

  /* ─── 反馈 ─── */
  --feedback-success-bg: hsl(var(--mono-hue) 30% 94%);
  --feedback-success-text: hsl(var(--mono-hue) 45% 30%);
  --feedback-error-bg: hsl(var(--mono-hue) 50% 95%);
  --feedback-error-text: hsl(var(--mono-hue) 80% 35%);
  --feedback-warn-bg: hsl(var(--mono-hue) 25% 94%);
  --feedback-warn-text: hsl(var(--mono-hue) 30% 40%);

  /* ─── 间距 ─── */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 12px;
  --space-lg: 16px;
  --space-xl: 24px;
  --space-2xl: 32px;
  --space-3xl: 48px;

  /* ─── 圆角 ─── */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;

  /* ─── 字体 ─── */
  --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Noto Sans SC', sans-serif;
  --font-mono: 'SF Mono', 'JetBrains Mono', 'Fira Code', monospace;
  --text-xs: 0.75rem;   /* 12px */
  --text-sm: 0.8125rem; /* 13px */
  --text-base: 0.875rem;/* 14px — 工具型 UI 基准 */
  --text-lg: 1rem;      /* 16px */
  --text-xl: 1.25rem;   /* 20px */
  --text-2xl: 1.5rem;   /* 24px */

  /* ─── 阴影 ─── */
  --shadow-sm: 0 1px 2px hsl(var(--mono-hue) 20% 10% / 0.05);
  --shadow-md: 0 2px 8px hsl(var(--mono-hue) 20% 10% / 0.08);
  --shadow-lg: 0 8px 24px hsl(var(--mono-hue) 20% 10% / 0.12);

  /* ─── 布局 ─── */
  --sidebar-width: 220px;
  --header-height: 0px; /* 无顶栏，侧栏承载导航 */
  --content-max-width: 1200px;

  /* ─── 动效 ─── */
  --duration-fast: 120ms;
  --duration-normal: 200ms;
  --duration-slow: 300ms;
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
}
```

### 2.2 暗黑模式

```css
[data-theme="dark"] {
  color-scheme: dark;

  --bg-app: hsl(var(--mono-hue) 15% 8%);
  --bg-surface: hsl(var(--mono-hue) 12% 11%);
  --bg-surface-raised: hsl(var(--mono-hue) 12% 14%);
  --bg-inset: hsl(var(--mono-hue) 10% 7%);

  --text-primary: hsl(var(--mono-hue) 10% 92%);
  --text-secondary: hsl(var(--mono-hue) 8% 62%);
  --text-tertiary: hsl(var(--mono-hue) 6% 45%);

  --border-default: hsl(var(--mono-hue) 10% 18%);
  --border-strong: hsl(var(--mono-hue) 12% 28%);

  --accent: hsl(var(--mono-hue) 72% 65%);
  --accent-hover: hsl(var(--mono-hue) 72% 72%);
  --accent-subtle: hsl(var(--mono-hue) 40% 16%);
  --accent-text: hsl(var(--mono-hue) 20% 8%);

  --status-running: hsl(var(--mono-hue) 72% 65%);
  --status-done: hsl(var(--mono-hue) 40% 60%);
  --status-paused: hsl(var(--mono-hue) 25% 60%);
  --status-error: hsl(var(--mono-hue) 80% 60%);
  --status-cancelled: hsl(var(--mono-hue) 6% 50%);

  --feedback-success-bg: hsl(var(--mono-hue) 25% 13%);
  --feedback-success-text: hsl(var(--mono-hue) 40% 70%);
  --feedback-error-bg: hsl(var(--mono-hue) 40% 13%);
  --feedback-error-text: hsl(var(--mono-hue) 70% 70%);
  --feedback-warn-bg: hsl(var(--mono-hue) 20% 13%);
  --feedback-warn-text: hsl(var(--mono-hue) 25% 65%);

  --shadow-sm: 0 1px 2px hsl(0 0% 0% / 0.3);
  --shadow-md: 0 2px 8px hsl(0 0% 0% / 0.4);
  --shadow-lg: 0 8px 24px hsl(0 0% 0% / 0.5);
}
```

### 2.3 动效约束

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

- 仅动画 `transform` / `opacity`（compositor-friendly）
- 禁止 `transition: all`
- 持续时间 120-300ms，ease-out

---

## 3. 布局架构

```
┌─────────────────────────────────────────────────────────────┐
│ ┌──────────┐ ┌────────────────────────────────────────────┐ │
│ │          │ │  Page Header (breadcrumb + actions)        │ │
│ │  Side    │ ├────────────────────────────────────────────┤ │
│ │  bar     │ │                                            │ │
│ │  220px   │ │  Main Content (flex: 1, overflow-y: auto)  │ │
│ │  fixed   │ │  max-width: 1200px, margin: 0 auto         │ │
│ │          │ │                                            │ │
│ │  • Logo  │ │                                            │ │
│ │  • Nav   │ │                                            │ │
│ │  • Theme │ │                                            │ │
│ │  • Health│ │                                            │ │
│ │          │ │                                            │ │
│ └──────────┘ └────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

**侧栏（AppSidebar.vue）：**
- 固定左侧，宽 220px，`position: sticky; top: 0; height: 100vh`
- 顶部：SVG logo + 系统名
- 中部：导航链接（Dashboard / 新建任务 / 任务列表 / 知识库 / 设置）
- 底部：主题切换 + 健康状态指示灯（`GET /health` 轮询 60s）
- 移动端（<768px）：折叠为底部 tab bar（≤5 项）

**主内容区：**
- `flex: 1; overflow-y: auto; padding: var(--space-xl)`
- 每页顶部有 PageHeader 组件（标题 + 面包屑 + 操作按钮）

---

## 4. 页面设计

### 4.1 Dashboard（`/`）

**信息架构：**
```
┌─────────────────────────────────────────────┐
│ 系统状态条（health checks 4 项）             │
├─────────────────────────────────────────────┤
│ 统计卡片行                                   │
│ [运行中 N] [已完成 N] [总任务 N] [知识库 N条] │
├─────────────────────────────────────────────┤
│ 最近任务（表格，最新 5 条）                    │
│ 状态 | 文件名 | 模式 | 进度 | 创建时间        │
├─────────────────────────────────────────────┤
│ 快速启动（拖拽上传区 + 一键启动）             │
└─────────────────────────────────────────────┘
```

**数据来源：**
- `GET /health` → 状态条
- `GET /api/v1/pipeline/list?page_size=5` → 最近任务 + `all_stats`
- `GET /api/v1/knowledge/status` → 知识库统计

**交互：**
- 状态条：4 个圆点（api/database/llm/kb），绿色=ok，黄色=degraded，红色=error
- 点击任务行 → 跳转 `/pipeline/:id`
- 快速启动区：拖拽上传 → 自动跳转 `/pipeline/new?file=xxx`（或内联配置后直接提交）

---

### 4.2 新建任务（`/pipeline/new`）

**信息架构：**
```
┌─────────────────────────────────────────────┐
│ 上传区（拖拽 / 点击，.md/.txt，≤10MB）       │
├─────────────────────────────────────────────┤
│ 配置区（三列网格）                            │
│ ┌─────────┐ ┌─────────────┐ ┌────────────┐ │
│ │ 执行模式 │ │ 测试维度     │ │ 输出格式   │ │
│ │ ○ auto  │ │ ☑ functional│ │ ☑ excel   │ │
│ │ ● semi  │ │ ☑ api       │ │ ☑ json    │ │
│ │ ○ full  │ │ ☑ security  │ │ ☐ xmind   │ │
│ │         │ │ ☐ performance│ │           │ │
│ │         │ │ ☐ compatibility│ │          │ │
│ │         │ │ ☐ usability │ │           │ │
│ └─────────┘ └─────────────┘ └────────────┘ │
├─────────────────────────────────────────────┤
│ [启动生成] 按钮 + 并发提示                    │
└─────────────────────────────────────────────┘
```

**后端对齐：**
- `POST /api/v1/pipeline/start` 的 `mode`（auto/semi/full）、`dimensions`（6 维度逗号分隔）、`formats`（excel/json/xmind）
- 并发限制：`TaskManager.MAX_WORKERS = 2`，前端显示"当前 N/2 槽位占用"
- 提交成功 → 自动跳转 `/pipeline/:id`（利用返回的 `pipeline_id`）

**表单规则（Guidelines 合规）：**
- 每个 radio/checkbox 有 `<label>` 包裹
- 文件输入有 `aria-label`
- 提交按钮在请求发出前保持 enabled，发出后显示 spinner + disabled
- 错误信息 inline 显示在对应字段旁

---

### 4.3 任务列表（`/pipelines`）

**信息架构：**
```
┌─────────────────────────────────────────────┐
│ 统计条：[全部 N] [运行中 N] [已完成 N] [其他 N]│ ← all_stats
├─────────────────────────────────────────────┤
│ 工具栏：[搜索框] [状态筛选 ▼] [刷新]         │
├─────────────────────────────────────────────┤
│ 表格                                         │
│ 状态 | 文件名 | 模式 | 进度 | 创建时间 | 操作 │
│ ●    | req.md | semi | 62%  | 10:32   | ... │
│ ●    | api.txt| full | 100% | 09:15   | ... │
├─────────────────────────────────────────────┤
│ 分页：[← 上一页] 第 1/3 页 [下一页 →]        │
└─────────────────────────────────────────────┘
```

**后端对齐：**
- `GET /api/v1/pipeline/list?page=&page_size=&keyword=&status=` → 分页 + 筛选
- `all_stats` 渲染统计条
- 操作列：运行中→取消 / 暂停→继续 / 完成→下载+详情
- 点击行 → `/pipeline/:id`

**URL 状态同步（Guidelines: URL reflects state）：**
- `?q=xxx&status=running&page=2` 同步到 URL query
- 支持浏览器前进/后退恢复筛选状态

**实时更新：**
- 有 running 任务时，启动 5s 轮询 `GET /list`（或全局 SSE 后续迭代）
- 无 running 任务时停止轮询

---

### 4.4 任务详情（`/pipeline/:id`）★ 核心页面

**信息架构：**
```
┌─────────────────────────────────────────────────────────────┐
│ PageHeader: [← 返回列表] 文件名.md  [状态徽章]  [取消/继续]  │
├─────────────────────────────────────────────────────────────┤
│ 步骤进度条（8 步横向 stepper）                                │
│ [0 需求扫描]→[1 需求分析]→[2 KB检索]→[3 测试点]→            │
│ [4 生成用例]→[5 评审]→[6 执行]→[7 报告]                     │
│  ● done      ● done      ○ running   ○ pending ...         │
├──────────────────────────────┬──────────────────────────────┤
│ 实时日志面板（左 60%）        │ 产物面板（右 40%）            │
│ ┌──────────────────────────┐ │ ┌──────────────────────────┐ │
│ │ 10:32:01 [STEP] 启动...  │ │ │ 📄 需求分析.md    [预览] │ │
│ │ 10:32:05 [OK] 分析完成   │ │ │ 📄 测试点.md      [预览] │ │
│ │ 10:32:06 [STEP] KB检索   │ │ │ 📊 用例.xlsx      [预览] │ │
│ │ ...                      │ │ │ 📦 下载 PyTest 工程      │ │
│ │ (auto-scroll, mono font) │ │ │                          │ │
│ └──────────────────────────┘ │ └──────────────────────────┘ │
├──────────────────────────────┴──────────────────────────────┤
│ LLM 统计：tokens_in / tokens_out / calls / cost（如有）      │
└─────────────────────────────────────────────────────────────┘
```

**SSE 接入（核心）：**
```javascript
const es = new EventSource(`/api/v1/pipeline/${id}/stream`)
es.addEventListener('step_done', (e) => { /* 更新步骤状态 */ })
es.addEventListener('log', (e) => { /* 追加日志 */ })
es.addEventListener('done', (e) => { /* 终态，关闭连接 */ })
es.addEventListener('error', (e) => { /* 终态 */ })
es.addEventListener('cancelled', (e) => { /* 终态 */ })
es.addEventListener('ping', () => { /* 心跳，忽略 */ })
```

**降级策略：** SSE 连接失败 → 回退到 3s 轮询 `GET /{id}/progress`

**产物面板：**
- `GET /{id}/artifacts` → 文件列表
- 点击"预览" → 模态框调用 `GET /{id}/preview/{name}`
  - markdown → 渲染 HTML（后端已返回 `{type: "markdown", html: "..."}`)
  - excel → 表格渲染（后端返回 `{type: "excel", rows: [[...]]}`)
- "下载 PyTest 工程" → `GET /{id}/export_pytest_project`（blob 下载）

**暂停态交互（semi 模式）：**
- 步骤 1/3/5 完成后 Pipeline 暂停（`status: paused`）
- 显示"继续执行"按钮 + 可选上传已执行 Excel（Step 6 前）
- 上传区：`POST /{id}/resume` + FormData(file)

---

### 4.5 知识库（`/knowledge`）

**信息架构：**
```
┌─────────────────────────────────────────────┐
│ Tab: [配置] [搜索] [导入]                    │
├─────────────────────────────────────────────┤
│ [配置 Tab]                                   │
│  当前状态卡片 + 配置表单（同现有，优化布局）   │
│  统计信息（总条目 + 分类 badges）             │
├─────────────────────────────────────────────┤
│ [搜索 Tab]                                   │
│  搜索框 + 结果列表                           │
│  GET /api/v1/knowledge/search?q=xxx         │
├─────────────────────────────────────────────┤
│ [导入 Tab]                                   │
│  Excel 上传（POST /import）                  │
│  单条添加表单（POST /add）                   │
└─────────────────────────────────────────────┘
```

**后端对齐：**
- `GET /status` → 统计
- `GET /search?q=` → 搜索结果
- `POST /import` → Excel 回灌
- `POST /add` → 单条添加（title/category/content/tags/module）
- `POST /update_config` → 热切换配置
- `GET /current_config` → 当前配置

---

### 4.6 设置（`/settings`）

**信息架构：**
```
┌─────────────────────────────────────────────┐
│ 系统配置（GET /api/v1/config）               │
│  LLM: provider / model / base_url / key(脱敏)│
│  Pipeline 默认值: mode / dimensions / formats │
│  知识库: enabled / vault_path                 │
│  配置校验: valid / errors[]                   │
├─────────────────────────────────────────────┤
│ 健康检查（GET /health）                       │
│  api / database / llm / knowledge_base       │
│  每项状态 + 最后检查时间                      │
├─────────────────────────────────────────────┤
│ 外观                                         │
│  主题: [跟随系统] [亮色] [暗色]              │
└─────────────────────────────────────────────┘
```

---

## 5. 组件拆分

```
webui/src/
├── main.js                    # 入口 + router
├── App.vue                    # 布局壳（sidebar + main）
├── assets/
│   └── tokens.css             # Design tokens（:root + [data-theme=dark]）
├── composables/
│   ├── useSSE.js              # SSE 连接管理（connect/close/reconnect/fallback）
│   ├── usePolling.js          # 轮询 hook（interval/auto-stop on unmount）
│   ├── useTheme.js            # 主题切换（localStorage 持久化）
│   └── useApi.js              # fetch 封装（baseURL/error handling/JSON parse）
├── components/
│   ├── AppSidebar.vue         # 侧栏导航
│   ├── PageHeader.vue         # 页面标题 + 面包屑 + 操作区
│   ├── StatusBadge.vue        # 状态徽章（running/done/paused/error/cancelled）
│   ├── StepProgress.vue       # 8 步横向进度条
│   ├── LogPanel.vue           # 实时日志面板（mono font, auto-scroll）
│   ├── ArtifactList.vue       # 产物列表 + 预览/下载
│   ├── ArtifactPreview.vue    # 模态框预览（markdown/excel）
│   ├── FileDropZone.vue       # 拖拽上传组件（复用）
│   ├── StatCard.vue           # 统计数字卡片
│   ├── HealthIndicator.vue    # 健康状态指示灯
│   ├── DataTable.vue          # 通用表格（排序/空状态）
│   ├── Pagination.vue         # 分页控件
│   ├── EmptyState.vue         # 空状态占位
│   └── ToastMessage.vue       # 全局 toast（aria-live=polite）
├── views/
│   ├── Dashboard.vue          # /
│   ├── PipelineNew.vue        # /pipeline/new
│   ├── PipelineList.vue       # /pipelines
│   ├── PipelineDetail.vue     # /pipeline/:id
│   ├── Knowledge.vue          # /knowledge
│   └── Settings.vue           # /settings
└── router/
    └── index.js               # 路由定义（lazy load）
```

---

## 6. 无障碍合规清单（Guidelines 逐条）

| 规则 | 实现 |
|------|------|
| Icon-only buttons → `aria-label` | 所有图标按钮必须带 `aria-label` |
| Form controls → `<label>` | 每个 input/select/checkbox 有显式 label |
| `<button>` for actions | 禁止 `<div onClick>` / `<a href="#">` 做按钮 |
| `aria-live="polite"` | Toast / 日志面板 / 状态变更区域 |
| `:focus-visible` ring | 全局 `outline: 2px solid var(--accent); outline-offset: 2px` |
| Skip link | `<a href="#main" class="skip-link">跳到主内容</a>` |
| `prefers-reduced-motion` | 全局 media query 禁用动画 |
| 语义 HTML | `<nav>` / `<main>` / `<table>` / `<header>` |
| 标题层级 | 每页一个 `<h1>`，子区块 `<h2>`/`<h3>` |
| 键盘导航 | 所有交互元素 Tab 可达，Enter/Space 触发 |
| 对比度 ≥ 4.5:1 | tokens 设计已保证（text-primary on bg-app） |
| 触摸目标 ≥ 44px | 按钮/链接最小高度 36px（桌面）/ 44px（移动端） |
| `font-variant-numeric: tabular-nums` | 数字列（进度%、统计、时间） |
| `text-wrap: balance` | 标题 |
| 长文本处理 | `overflow: hidden; text-overflow: ellipsis; white-space: nowrap` + `min-w-0` |
| 空状态 | 每个列表/表格有 EmptyState 组件 |
| URL 状态同步 | 列表页筛选/分页 → query params |
| 破坏性操作确认 | 取消任务 → confirm 对话框 |
| `autocomplete` | 表单字段正确设置 |
| `spellcheck="false"` | ID/路径/URL 输入框 |
| `Intl.DateTimeFormat` | 所有时间显示 |
| `color-scheme: dark` | `<html>` 属性 |
| `<meta name="theme-color">` | 匹配 bg-app |

---

## 7. 实施分期

### Phase 1：骨架 + Tokens（0.5 天）
- [ ] `tokens.css`（light + dark 全套变量）
- [ ] `App.vue` 重写（sidebar 布局）
- [ ] `AppSidebar.vue` + `useTheme.js`
- [ ] `router/index.js`（6 路由 lazy load）
- [ ] `index.html` 加 `color-scheme` / `theme-color` / skip-link
- [ ] 验证：暗黑/亮色切换正常，导航正常

### Phase 2：Pipeline 核心链路（1.5 天）★
- [ ] `PipelineNew.vue`（上传 + 配置 + 提交）
- [ ] `PipelineDetail.vue`（SSE + 步骤进度 + 日志 + 产物）
- [ ] `useSSE.js`（EventSource 封装 + 降级轮询）
- [ ] `StepProgress.vue` / `LogPanel.vue` / `ArtifactList.vue` / `ArtifactPreview.vue`
- [ ] `PipelineList.vue` 重写（表格 + 筛选 + 分页 + all_stats）
- [ ] 验证：完整跑一次 Pipeline，SSE 实时推送正常，产物预览正常

### Phase 3：辅助页面（1 天）
- [ ] `Dashboard.vue`（health + stats + 最近任务 + 快速启动）
- [ ] `Knowledge.vue`（tabs: 配置/搜索/导入）
- [ ] `Settings.vue`（config + health + theme）
- [ ] `FileDropZone.vue` / `StatCard.vue` / `HealthIndicator.vue`
- [ ] 验证：所有 API 端点前端覆盖

### Phase 4：打磨 + QA（0.5 天）
- [ ] 移动端响应式（sidebar → bottom tab）
- [ ] 键盘导航全量测试
- [ ] `prefers-reduced-motion` 验证
- [ ] 空状态 / 错误状态 / 加载状态全覆盖
- [ ] Lighthouse 无障碍 ≥ 95
- [ ] 构建 → `web/static/dist/` → FastAPI SPA fallback 验证

---

## 8. 关键交互规范

### 8.1 SSE 连接生命周期
```
页面挂载 → new EventSource(/api/v1/pipeline/:id/stream)
  ├─ 收到 step_done → 更新步骤状态 + 刷新产物列表
  ├─ 收到 log → 追加日志（auto-scroll if 用户在底部）
  ├─ 收到 done/error/cancelled → 更新终态 → 关闭 EventSource
  ├─ 收到 ping → 忽略（心跳）
  └─ onerror → 3s 后重连（最多 5 次）→ 仍失败则降级轮询
页面卸载 → es.close()
```

### 8.2 日志面板
- 等宽字体 `var(--font-mono)`，字号 `var(--text-xs)`
- 日志级别着色：`[OK]` accent / `[ERR]` error / `[WARN]` warn / `[STEP]` secondary
- 最多显示 200 条（后端 MAX_LOGS），前端虚拟滚动或 `content-visibility: auto`
- Auto-scroll：仅当用户滚动位置在底部时自动跟随

### 8.3 产物预览模态框
- `<dialog>` 元素（原生，`overscroll-behavior: contain`）
- Markdown：`v-html` 渲染后端返回的 HTML（已 sanitize）
- Excel：`<table>` 渲染 rows 二维数组，表头加粗，最多 50 行
- ESC 关闭 / 点击 backdrop 关闭
- 焦点陷阱（focus trap）

### 8.4 主题切换
- 三态：`system` / `light` / `dark`
- `system` 监听 `matchMedia('(prefers-color-scheme: dark)')` 变化
- 持久化到 `localStorage('theme')`
- 切换时 `<html data-theme="dark">` + `<meta name="theme-color">` 同步更新

---

## 9. 性能约束

| 指标 | 目标 |
|------|------|
| 首屏 JS | < 50KB gzipped（Vue 3 + router 已 ~35KB） |
| CLS | < 0.1（所有动态区域预留空间） |
| LCP | < 1.5s（本地部署，无 CDN） |
| 列表虚拟化 | > 50 条日志启用 `content-visibility: auto` |
| 路由懒加载 | 所有 view 组件 `() => import(...)` |
| 图片 | 无外部图片，SVG inline |
| 字体 | 系统字体栈，零 web font 请求 |

---

## 10. 文件命名 & 代码规范

- 组件：PascalCase（`StepProgress.vue`）
- Composables：camelCase + `use` 前缀（`useSSE.js`）
- CSS：仅 `tokens.css` 全局，组件内 `<style scoped>`
- 禁止 `transition: all`
- 禁止内联 `style="..."` 超过 1 个属性
- 禁止 emoji 作图标（用 SVG 或 CSS 图形）
- 所有 fetch 走 `useApi.js`（统一 error handling + base URL）

---

## 附录 A：后端 API 完整清单（前端需覆盖）

| Method | Path | 用途 | 前端页面 |
|--------|------|------|----------|
| POST | /api/v1/pipeline/start | 启动 | PipelineNew |
| GET | /api/v1/pipeline/list | 列表 | PipelineList / Dashboard |
| GET | /api/v1/pipeline/{id}/progress | 进度 | PipelineDetail (fallback) |
| GET | /api/v1/pipeline/{id}/stream | SSE | PipelineDetail |
| POST | /api/v1/pipeline/{id}/cancel | 取消 | PipelineDetail / List |
| POST | /api/v1/pipeline/{id}/resume | 继续 | PipelineDetail |
| GET | /api/v1/pipeline/{id}/artifacts | 产物列表 | PipelineDetail |
| GET | /api/v1/pipeline/{id}/artifacts/{name} | 下载 | PipelineDetail |
| GET | /api/v1/pipeline/{id}/preview/{name} | 预览 | PipelineDetail |
| GET | /api/v1/pipeline/{id}/export_pytest_project | ZIP | PipelineDetail / List |
| GET | /api/v1/knowledge/status | 统计 | Knowledge / Dashboard |
| GET | /api/v1/knowledge/search | 搜索 | Knowledge |
| POST | /api/v1/knowledge/import | 导入 | Knowledge |
| POST | /api/v1/knowledge/add | 添加 | Knowledge |
| POST | /api/v1/knowledge/update_config | 配置 | Knowledge |
| GET | /api/v1/knowledge/current_config | 当前配置 | Knowledge |
| GET | /api/v1/config | 系统配置 | Settings |
| GET | /health | 健康检查 | Dashboard / Settings / Sidebar |

---

## 附录 B：Pipeline 8 步定义（来自 STEP_REGISTRY）

| ID | 名称 | 输出文件 | 暂停点 |
|----|------|----------|--------|
| 0 | 需求漏洞扫描 | requirement_gap_analysis.md | 否 |
| 1 | 需求分析 | requirements_analysis.md | 是（semi） |
| 2 | 知识库检索 | knowledge-context.md | 否 |
| 3 | 测试点梳理 | testpoints.md | 是（semi） |
| 4 | 生成测试用例 | testcases.xlsx | 否 |
| 5 | 用例评审 | test_case_review_report.md | 是（semi） |
| 6 | 执行测试 | testcases.xlsx | 否 |
| 7 | 生成测试报告 | test_report.md | 否 |
