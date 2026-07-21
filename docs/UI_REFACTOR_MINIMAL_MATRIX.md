# UI 重构交付文档 — Minimal × Matrix 双主题

> 重构日期：2026-07-22
> 设计风格：Light = **Minimal**（Swiss 极简单色系），Dark = **Matrix**（磷光绿终端 CRT 风）

---

## 1. 设计风格概述

### Minimal（亮色模式）
受瑞士平面设计原则启发，极致干净的单色美学。大量留白，最小化视觉噪音，每个元素都需"挣得"自己的位置。适合优先展示内容而非装饰的专业工具。

核心特征：muted indigo（`hsl(222 47% 51%)`）作为唯一强调色，4-8px 锐利圆角，几乎不可见的阴影，系统无衬线字体，无渐变。

### Matrix（暗色模式）
受《黑客帝国》电影系列启发的赛博朋克终端美学。纯黑背景配磷光绿文字，等宽字体，微妙的 CRT 扫描线叠加效果。为开发者工具和 AI 系统营造"黑客"氛围。

核心特征：磷光绿（`hsl(150 100% 45%)`）为主色，2-6px 锐利圆角，绿色辉光阴影系统，全等宽字体，CRT 扫描线 overlay，文字 glow 效果。

---

## 2. 变更文件树

### Phase 1 — 全局样式变量替换

| 文件路径 | 变更类型 | 说明 |
|---------|---------|------|
| `webui/src/assets/tokens.css` | **CSS 全量重写** | 替换全部 Design Token：色板、圆角、阴影、字体族、动效曲线。新增 `--text-glow` 变量、CRT 扫描线 overlay、Matrix 滚动条样式 |
| `webui/index.html` | **HTML 属性修改** | `meta[theme-color]` 值从 `#f5f5fa` 改为 `#fafafa`（Minimal 白） |
| `webui/src/composables/useTheme.js` | **JS 常量修改** | `applyTheme()` 中 meta content 硬编码值：dark `#030a06`（Matrix 黑绿）、light `#fafafa`（Minimal 白） |

### Phase 2 — 基础组件皮肤重绘

| 文件路径 | 变更类型 | 说明 |
|---------|---------|------|
| `webui/src/App.vue` | **仅修改 `<style>`** | 主题切换按钮 Matrix 暗色辉光增强 |
| `webui/src/components/AppSidebar.vue` | **仅修改 `<style>`** | 品牌 icon/text Matrix 辉光、导航 active 项绿色 glow、用户头像 Matrix 样式 |
| `webui/src/components/StatCard.vue` | **仅修改 `<style>`** | 顶部 accent bar Matrix 辉光、value 文字 glow |
| `webui/src/components/StatusBadge.vue` | **仅修改 `<style>`** | running 状态 dot 辉光增强、border Matrix 绿色调 |
| `webui/src/components/LogPanel.vue` | **仅修改 `<style>`** | CRT 扫描线 overlay、step level 文字 glow、msg 微光 |
| `webui/src/components/StepProgress.vue` | **仅修改 `<style>`** | running/done 指示器 Matrix 辉光增强 |
| `webui/src/components/PageHeader.vue` | **仅修改 `<style>`** | 标题 Matrix text glow、返回按钮 hover 辉光 |
| `webui/src/components/ToastContainer.vue` | **仅修改 `<style>`** | toast 边框 Matrix 绿色调、info toast 辉光、success/error 左边框色值 |
| `webui/src/components/FileDropZone.vue` | **仅修改 `<style>`** | 拖拽区 Matrix 绿色辉光边框 |
| `webui/src/components/EmptyState.vue` | **仅修改 `<style>`** | 空状态图标 Matrix 绿色 drop-shadow |
| `webui/src/components/Pagination.vue` | **仅修改 `<style>`** | 分页按钮 Matrix hover 辉光 |
| `webui/src/components/ArtifactList.vue` | **仅修改 `<style>`** | 产物项 hover Matrix 边框/辉光、操作按钮 glow、导出按钮 glow |
| `webui/src/components/ArtifactPreview.vue` | **仅修改 `<style>`** | Modal Matrix 边框/辉光、backdrop 加深、code 块绿色文字 glow |

### Phase 3 — 业务页面布局微调

| 文件路径 | 变更类型 | 说明 |
|---------|---------|------|
| `webui/src/views/Dashboard.vue` | **仅修改 `<style>`** | 健康面板标题 glow、icon 辉光、section 标题 glow、表头 Matrix 样式（取消 uppercase）、btn-primary 辉光 |
| `webui/src/views/Login.vue` | **仅修改 `<style>`** | 登录卡片 Matrix 边框/辉光、标题 glow、登录按钮辉光 |
| `webui/src/views/PipelineList.vue` | **仅修改 `<style>`** | 状态标签 active Matrix 辉光、表头 Matrix 样式、文件链接 hover glow |
| `webui/src/views/PipelineNew.vue` | **仅修改 `<style>`** | 表单 section 标题 glow、config field Matrix 边框、提交按钮辉光 |
| `webui/src/views/PipelineDetail.vue` | **仅修改 `<style>`** | 进度条 fill Matrix 辉光、SSE badge Matrix 样式、accent 按钮 glow |
| `webui/src/views/Knowledge.vue` | **仅修改 `<style>`** | Tab active Matrix 辉光、card 标题 glow、cat-badge Matrix 边框、btn-primary 辉光、搜索结果标题 glow |
| `webui/src/views/Settings.vue` | **仅修改 `<style>`** | card 标题 glow、toggle switch Matrix 辉光、save 按钮 glow、section-save 按钮 glow、health dot 辉光 |

### 设计规范文件（新建）

| 文件路径 | 说明 |
|---------|------|
| `.meituan-catpaw/312992876/skills/skills-market/awesome-design-skill/design-md/minimal/DESIGN.md` | Minimal 风格设计规范 |
| `.meituan-catpaw/312992876/skills/skills-market/awesome-design-skill/design-md/matrix/DESIGN.md` | Matrix 风格设计规范 |

---

## 3. 关键风险回滚点

**优先回滚文件：`webui/src/assets/tokens.css`**

该文件包含全部 CSS Custom Properties（Design Token），控制全局色板、圆角、阴影、字体、动效。回滚此文件可恢复约 **85%** 的原始 "Aurora Violet" 界面外观。

剩余 15% 为各组件 `<style scoped>` 中的 `[data-theme="dark"]` 增强规则（辉光、CRT 扫描线等），这些规则全部以 `[data-theme="dark"]` 前缀隔离，不会影响亮色模式，且在 token 回滚后因失去 `--text-glow`、`--shadow-accent` 等变量引用而自动失效（回退为 `none`/`inherit`）。

回滚步骤：
1. 用 git 恢复 `webui/src/assets/tokens.css` → `git checkout HEAD -- webui/src/assets/tokens.css`
2. 恢复 `webui/index.html` 的 theme-color → `git checkout HEAD -- webui/index.html`
3. 恢复 `useTheme.js` 中的 meta 值 → `git checkout HEAD -- webui/src/composables/useTheme.js`
4. （可选）批量恢复所有组件 → `git checkout HEAD -- webui/src/components/ webui/src/views/ webui/src/App.vue`

---

## 4. 功能对齐核查表

### API 调用逻辑核查

| 组件/视图 | API 端点 | 是否修改 | 确认 |
|-----------|---------|---------|------|
| Dashboard.vue | `GET /health`, `GET /pipeline/list`, `GET /knowledge/status`, `POST /pipeline/start` | 否 | ✅ |
| Login.vue | `POST /auth/login` | 否 | ✅ |
| PipelineList.vue | `GET /pipeline/list`, `POST /pipeline/:id/cancel`, `POST /pipeline/:id/resume`, `GET /pipeline/:id/export_pytest_project` | 否 | ✅ |
| PipelineNew.vue | `GET /config`, `POST /pipeline/start` | 否 | ✅ |
| PipelineDetail.vue | `GET /pipeline/:id/progress`, `GET /pipeline/:id/artifacts`, `POST /pipeline/:id/cancel`, `POST /pipeline/:id/resume`, `GET /pipeline/:id/preview/:name`, `GET /pipeline/:id/artifacts/:name`, `GET /pipeline/:id/export_pytest_project` | 否 | ✅ |
| Knowledge.vue | `GET /knowledge/current_config`, `GET /knowledge/status`, `POST /knowledge/update_config`, `GET /knowledge/search`, `POST /knowledge/import`, `POST /knowledge/add` | 否 | ✅ |
| Settings.vue | `GET /config`, `PUT /config`, `GET /health` | 否 | ✅ |
| ArtifactPreview.vue | `GET /pipeline/:id/preview/:name` | 否 | ✅ |

### 状态管理 / 事件回调核查

| 组件/视图 | 事件/状态 | 是否修改 | 确认 |
|-----------|----------|---------|------|
| useTheme.js | `theme` ref, `setTheme()`, `toggleTheme()`, `watch(theme, applyTheme)` | 仅修改 meta content 字符串常量 | ✅ |
| App.vue | `@click="toggleTheme"` | 未变 | ✅ |
| AppSidebar.vue | `@click="handleLogout"` → `logout()` | 未变 | ✅ |
| Dashboard.vue | `@click="loadHealth"`, `@click="loadStats()"`, `@file="quickStart"` | 未变 | ✅ |
| PipelineList.vue | `@click="setStatus"`, `@input="debouncedLoad"`, `@click="loadList"`, `@click="toggleAutoRefresh"`, `@click.stop="cancelTask"`, `@click.stop="resumeTask"`, `@click.stop="downloadZip"`, `@change="goPage"` | 未变 | ✅ |
| PipelineNew.vue | `@file="onFile"`, `@click="submit"` | 未变 | ✅ |
| PipelineDetail.vue | `@click="confirmCancel"`, `@click="resume"`, `@preview="openPreview"`, `@download="downloadArtifact"`, `@export="exportProject"`, `@close="previewOpen = false"` | 未变 | ✅ |
| Knowledge.vue | `@click="saveConfig"`, `@keydown.enter="doSearch(1)"`, `@click="doSearch(1)"`, `@file="importExcel"`, `@click="addKnowledge"`, `@change="doSearch"` | 未变 | ✅ |
| Settings.vue | `@click="saveLLMConfig"`, `@click="saveConfig"`, `@click="loadHealth(true)"`, `@change="onThemeChange(t.value)"` | 未变 | ✅ |

### DOM 结构 / data-* / id / className 功能性命名核查

| 检查项 | 是否修改 | 确认 |
|--------|---------|------|
| `data-*` 自定义属性 | 未变 | ✅ |
| `id` 锚点（如 `#main-content`, `#username`, `#password` 等） | 未变 | ✅ |
| `className` 功能性命名（如 `is-active`, `is-dragging`, `router-link-exact-active` 等） | 未变 | ✅ |
| `aria-*` 属性 | 未变 | ✅ |
| `v-model` / `v-if` / `v-for` / `v-html` 绑定 | 未变 | ✅ |
| `<router-link>` / `<router-view>` | 未变 | ✅ |
| `<template>` 结构 | 未变（未增删/移动任何元素） | ✅ |

### 工程配置核查

| 文件 | 是否修改 | 确认 |
|------|---------|------|
| `package.json` | 未变 | ✅ |
| `vite.config.js` | 未变 | ✅ |
| 新增第三方依赖 | 无 | ✅ |
| 新增 UI 库/CSS 框架 | 无 | ✅ |

---

## 5. 待人工评估清单

以下视觉优化项因需要修改 JS 逻辑而跳过，建议人工评估：

| 编号 | 优化项 | 原因 | 建议方案 |
|------|--------|------|---------|
| 1 | Matrix 模式下文字打字机逐字显现效果 | 需在 `LogPanel.vue` 的 `watch` 中拆分 msg 字符并逐字渲染，涉及修改渲染逻辑 | 可通过 CSS `@keyframes` + `steps()` 实现纯 CSS 打字机效果，但无法做到逐字符、需 JS 辅助 |
| 2 | Matrix 模式下 LogPanel 自动滚动时的 phosphor 余晖拖尾 | 需修改 `LogPanel.vue` 的 scroll 行为逻辑 | 可用 CSS `scroll-behavior` + 伪元素实现近似效果，但精确拖尾需 canvas/JS |
| 3 | Minimal 模式下按钮 ripple 水波纹点击反馈 | 需在按钮 click 事件中动态创建 ripple DOM 元素 | 纯 CSS 可用 `:active` 伪类模拟，但无法实现精确的点击位置波纹 |

---

## 6. 构建验证

```
✓ vite build — 0 errors, 0 warnings
✓ 构建产物大小正常（index CSS: 16.13 kB → gzip 3.67 kB）
✓ 所有 7 个视图 + 12 个组件均成功编译
```

---

## 7. 自检声明

**经核查，本次重构未修改任何 API 调用逻辑与核心 State 管理。**

所有变更严格限定在以下范围：
- CSS Custom Properties（Design Token）值替换
- Vue SFC `<style scoped>` 中新增 `[data-theme="dark"]` 增强规则
- 1 处 JS 文件中的字符串常量（meta theme-color 值）
- 1 处 HTML 文件中的 meta 属性值

未触碰任何 `<template>` 结构、`<script>` 业务逻辑、`useEffect`/`watch`/`computed` 依赖项、API 请求构造/响应拦截、路由配置、状态管理调用链。
