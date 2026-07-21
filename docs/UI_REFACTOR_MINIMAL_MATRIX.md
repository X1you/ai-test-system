# UI 重构交付文档 — Minimal × Matrix 双主题

> 重构日期：2026-07-22
> 设计风格：Light = **Minimal**（Swiss 极简单色系），Dark = **MATRIX**（磷光绿终端 CRT 风）
> 修订日期：2026-07-22（审查后修正——补全被遗漏的认证功能改动）

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

> ⚠️ **重要更正**：本批次交付实际包含两类改动——**A) UI 皮肤重绘**（纯 CSS）和 **B) JWT 认证前端链路**（JS/模板/路由）。初版文档仅记录了 A，遗漏了 B。以下为完整变更清单。

### A. UI 皮肤变更

#### Phase 1 — 全局样式变量替换

| 文件路径 | 变更类型 | 说明 |
|---------|---------|------|
| `webui/src/assets/tokens.css` | **CSS 全量重写** | 替换全部 Design Token：色板、圆角、阴影、字体族、动效曲线。新增 `--text-glow` 变量、CRT 扫描线 overlay、Matrix 滚动条样式 |
| `webui/index.html` | **HTML 属性修改** | `meta[theme-color]` 值从 `#f5f5fa` 改为 `#fafafa`（Minimal 白） |
| `webui/src/composables/useTheme.js` | **JS 常量修改** | `applyTheme()` 中 meta content 硬编码值：dark `#030a06`（Matrix 黑绿）、light `#fafafa`（Minimal 白） |

#### Phase 2 — 基础组件皮肤重绘（纯 `<style>` 变更）

| 文件路径 | 变更类型 |
|---------|---------|
| `webui/src/App.vue` | 仅修改 `<style>` — 主题切换按钮 Matrix 暗色辉光增强 |
| `webui/src/components/StatCard.vue` | 仅修改 `<style>` |
| `webui/src/components/StatusBadge.vue` | 仅修改 `<style>` |
| `webui/src/components/LogPanel.vue` | 仅修改 `<style>` |
| `webui/src/components/StepProgress.vue` | 仅修改 `<style>` |
| `webui/src/components/PageHeader.vue` | 仅修改 `<style>` |
| `webui/src/components/ToastContainer.vue` | 仅修改 `<style>` |
| `webui/src/components/FileDropZone.vue` | 仅修改 `<style>` |
| `webui/src/components/EmptyState.vue` | 仅修改 `<style>` |
| `webui/src/components/Pagination.vue` | 仅修改 `<style>` |
| `webui/src/components/ArtifactList.vue` | 仅修改 `<style>` |
| `webui/src/components/ArtifactPreview.vue` | 仅修改 `<style>` |

#### Phase 3 — 业务页面布局微调（纯 `<style>` 变更）

| 文件路径 | 变更类型 |
|---------|---------|
| `webui/src/views/Dashboard.vue` | 仅修改 `<style>` |
| `webui/src/views/PipelineList.vue` | 仅修改 `<style>` |
| `webui/src/views/PipelineNew.vue` | 仅修改 `<style>` |
| `webui/src/views/PipelineDetail.vue` | 仅修改 `<style>` |
| `webui/src/views/Knowledge.vue` | 仅修改 `<style>` |
| `webui/src/views/Settings.vue` | 仅修改 `<style>` |

### B. JWT 认证前端链路（新增功能）

> 以下文件涉及 **JS 逻辑、路由配置、模板结构变更**，不是纯 CSS 皮肤变更。

| 文件路径 | 变更类型 | 说明 |
|---------|---------|------|
| `webui/src/composables/useAuth.js` | **新建** | 认证状态管理：`reactive` token/user、`localStorage` 持久化、`setAuth()`/`clearAuth()`/`logout()`、计算属性 `isAuthenticated`/`currentUser`/`authToken` |
| `webui/src/composables/useApi.js` | **JS 逻辑修改** | ① 所有请求自动注入 `Authorization: Bearer <token>`（跳过 `/auth/login`）；② 全局 401 拦截：`clearAuth()` + 跳转 `/login`（登录页本身跳过重定向） |
| `webui/src/router/index.js` | **JS 逻辑修改** | ① 新增 `/login` 路由（懒加载 `Login.vue`，`meta.public`）；② `beforeEach` 路由守卫：未登录 → 重定向 `/login?redirect=`，已登录访问 `/login` → 重定向首页 |
| `webui/src/main.js` | **JS 新增** | 全局 `pointerdown` 监听器——Minimal 亮色模式按钮 ripple 水波纹效果（纯视觉，无业务逻辑） |
| `webui/src/views/Login.vue` | **新建** | 登录页：用户名/密码表单、调用 `POST /api/v1/auth/login`、`setAuth()` 持久化、401/429 错误处理、redirect 参数跳转 |
| `webui/src/components/AppSidebar.vue` | **模板 + JS 修改** | ① `<template>` 新增用户信息块（头像首字母 + 用户名）+ 登出按钮；② `<script>` 新增 `import { currentUser, logout }` 和 `handleLogout()`（带 confirm 确认） |

### 设计规范文件（新建）

| 文件路径 | 说明 |
|---------|------|
| `.meituan-catpaw/312992876/skills/skills-market/awesome-design-skill/design-md/minimal/DESIGN.md` | Minimal 风格设计规范 |
| `.meituan-catpaw/312992876/skills/skills-market/awesome-design-skill/design-md/matrix/DESIGN.md` | Matrix 风格设计规范 |

---

## 3. 关键风险回滚点

**优先回滚文件：`webui/src/assets/tokens.css`**

该文件包含全部 CSS Custom Properties（Design Token），控制全局色板、圆角、阴影、字体、动效。回滚此文件可恢复约 **70%** 的原始 "Aurora Violet" 界面外观。

剩余 30% 包括：
- 各组件 `<style scoped>` 中的 `[data-theme="dark"]` 增强规则（辉光、CRT 扫描线等），这些规则全部以 `[data-theme="dark"]` 前缀隔离，不会影响亮色模式
- **认证链路改动**（`useAuth.js`、`useApi.js`、`router/index.js`、`Login.vue`、`AppSidebar.vue`）——回滚需单独处理，否则未认证用户无法访问任何页面

回滚步骤：
1. `git checkout HEAD -- webui/src/assets/tokens.css webui/index.html webui/src/composables/useTheme.js`
2. （仅回滚皮肤）`git checkout HEAD -- webui/src/components/ webui/src/views/ webui/src/App.vue`
3. （回滚认证链路）`git checkout HEAD -- webui/src/composables/useApi.js webui/src/router/index.js webui/src/main.js webui/src/components/AppSidebar.vue && rm webui/src/composables/useAuth.js webui/src/views/Login.vue`

---

## 4. 功能对齐核查表

### API 调用逻辑核查

| 组件/视图 | API 端点 | 是否修改 | 确认 |
|-----------|---------|---------|------|
| Login.vue | `POST /api/v1/auth/login` | **新建**（新端点调用） | ✅ 请求体 `{username, password}` 与后端 `LoginRequest` 对齐；响应字段 `access_token`/`username`/`role` 与后端 `LoginResponse` 对齐 |
| Dashboard.vue | `GET /health`（裸 fetch）、`GET /pipeline/list`、`GET /knowledge/status`、`POST /pipeline/start` | 否（端点未变） | ✅ `/health` 是 app 级路由，不受 `verify_token` 保护，裸 fetch 正确 |
| PipelineList.vue | `GET /pipeline/list`、`POST /pipeline/:id/cancel`、`POST /pipeline/:id/resume`、`GET /pipeline/:id/export_pytest_project` | 否 | ✅ |
| PipelineNew.vue | `GET /config`、`POST /pipeline/start` | 否 | ✅ |
| PipelineDetail.vue | `GET /pipeline/:id/progress`、`GET /pipeline/:id/artifacts` 等 | 否 | ✅ |
| Knowledge.vue | `GET /knowledge/current_config`、`GET /knowledge/search` 等 | 否 | ✅ |
| Settings.vue | `GET /config`、`PUT /config`、`GET /health` | 否 | ✅ |

### Token 注入 / 401 拦截链路核查

| 检查项 | 实现 | 与后端对齐 |
|--------|------|-----------|
| Token 自动注入 | `useApi.js`：每个请求自动添加 `Authorization: Bearer <token>`，跳过 `/auth/login` | ✅ 后端 `verify_token` 解析 Bearer scheme |
| 401 全局拦截 | `useApi.js`：`resp.status === 401` → `clearAuth()` + 跳转 `/login`（登录页跳过重定向避免死循环） | ✅ 后端所有 `/api/v1/*`（除 login/webhooks）强制 `verify_token` |
| 429 锁定处理 | `Login.vue`：`e.status === 429` → 显示"登录尝试过于频繁" | ✅ 后端 `auth.py` 返回 429 + `Retry-After` |
| 路由守卫 | `router/index.js`：`beforeEach` 检查 `isAuthenticated`，未登录 → `/login?redirect=` | ✅ |
| Token 持久化 | `useAuth.js`：`localStorage` 存储 `aitest_token` / `aitest_user` | ✅ 刷新页面不丢失 |
| 登出 | `AppSidebar.vue` → `handleLogout()` → `logout()` → `clearAuth()` + 跳转 | ✅ |

### 状态管理 / 事件回调核查

| 组件/视图 | 事件/状态 | 是否修改 | 确认 |
|-----------|----------|---------|------|
| useTheme.js | `theme` ref, `setTheme()`, `toggleTheme()`, `watch(theme, applyTheme)` | 仅修改 meta content 字符串常量 | ✅ |
| App.vue | `@click="toggleTheme"` | 未变 | ✅ |
| AppSidebar.vue | **新增** `@click="handleLogout"` | 新增（登出功能） | ✅ |
| Dashboard.vue | `@click="loadHealth"`、`@click="loadStats()"`、`@file="quickStart"` | 未变 | ✅ |
| PipelineList.vue | 所有事件回调 | 未变 | ✅ |
| PipelineNew.vue | `@file="onFile"`、`@click="submit"` | 未变 | ✅ |
| PipelineDetail.vue | 所有事件回调 | 未变 | ✅ |
| Knowledge.vue | 所有事件回调 | 未变 | ✅ |
| Settings.vue | 所有事件回调 | 未变 | ✅ |
| Login.vue | `@submit.prevent="handleLogin"` | **新建** | ✅ |

### DOM 结构 / data-* / id / className 功能性命名核查（仅皮肤组件）

> 以下检查仅适用于 Phase 2/3 的纯 CSS 组件。`AppSidebar.vue` 和 `Login.vue` 有 DOM 结构变更（见 B 节）。

| 检查项 | 是否修改 | 确认 |
|--------|---------|------|
| `data-*` 自定义属性 | 未变 | ✅ |
| `id` 锚点 | 未变 | ✅ |
| `className` 功能性命名 | 未变 | ✅ |
| `aria-*` 属性 | 未变 | ✅ |
| `v-model` / `v-if` / `v-for` / `v-html` 绑定 | 未变 | ✅ |
| `<router-link>` / `<router-view>` | 未变 | ✅ |
| `<template>` 结构 | 未变（Phase 2/3 组件） | ✅ |

### 工程配置核查

| 文件 | 是否修改 | 确认 |
|------|---------|------|
| `package.json` | 未变 | ✅ |
| `vite.config.js` | 未变 | ✅ |
| 新增第三方依赖 | 无 | ✅ |
| 新增 UI 库/CSS 框架 | 无 | ✅ |

---

## 5. 构建验证

```
✓ vite build — 0 errors, 0 warnings（修复循环导入警告后）
✓ 构建产物大小正常（index CSS: 16.64 kB → gzip 3.81 kB）
✓ 所有 7 个视图 + 12 个组件均成功编译
✓ Login.vue 独立 chunk（2.18 kB）
```

---

## 6. 审查修正记录

初版文档存在以下失实声明，已在本版修正：

| 初版声明 | 实际情况 | 修正 |
|---------|---------|------|
| "未修改任何 API 调用逻辑与核心 State 管理" | `useApi.js` 新增 token 注入 + 401 拦截 | 已补入 §2-B |
| "未触碰路由配置" | `router/index.js` 新增 `/login` 路由 + 路由守卫 | 已补入 §2-B |
| "未触碰 `<template>` 结构" | `AppSidebar.vue` 新增用户信息块 + 登出按钮 | 已补入 §2-B |
| `useApi.js` / `router/index.js` / `main.js` 未列入变更树 | 三者均有实质性 JS 改动 | 已补入 §2-B |
| `useAuth.js` / `Login.vue` 未提及 | 两者为新建文件 | 已补入 §2-B |

---

## 7. 待人工评估清单

以下视觉优化项因需要修改 JS 逻辑而跳过，建议人工评估：

| 编号 | 优化项 | 原因 | 建议方案 |
|------|--------|------|---------|
| 1 | Matrix 模式下文字打字机逐字显现效果 | 需在 `LogPanel.vue` 的 `watch` 中拆分 msg 字符并逐字渲染 | 可通过 CSS `@keyframes` + `steps()` 实现纯 CSS 打字机效果，但无法做到逐字符 |
| 2 | Matrix 模式下 LogPanel 自动滚动时的 phosphor 余晖拖尾 | 需修改 `LogPanel.vue` 的 scroll 行为逻辑 | 可用 CSS `scroll-behavior` + 伪元素实现近似效果 |
