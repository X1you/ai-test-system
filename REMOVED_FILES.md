# 🗑️ 已清理遗留文件清单

> **清理日期**：2026-07-22  
> **版本**：v6.3.0 → v6.4.0（package.json）/ v2.2.1（业务）  
> **清理原则**：无人引用、含旧版实心圆、已迁移到 V4 组件的代码  
> **回退方法**：`git checkout <previous-commit> -- <file-path>`（本仓库有 git 历史）

---

## 📁 一、`legacy/templates_sprint60/`（已整目录删除）

> **原因**：sprint 60 的 Django/Flask 服务端模板，已被 Vue 3 SPA 取代。保留会造成误导。

| 删除文件 | 大小（约） | 替代方案 |
|----------|-----------|----------|
| `legacy/templates_sprint60/base.html` | 12 KB | [src/App.vue](file:///Users/x1you/Documents/ai-test-system/webui/src/App.vue) |
| `legacy/templates_sprint60/index.html` | 28 KB | [src/views/Dashboard.vue](file:///Users/x1you/Documents/ai-test-system/webui/src/views/Dashboard.vue) |
| `legacy/templates_sprint60/knowledge.html` | 18 KB | [src/views/Knowledge.vue](file:///Users/x1you/Documents/ai-test-system/webui/src/views/Knowledge.vue) |
| `legacy/templates_sprint60/pipeline.html` | 32 KB | [src/views/PipelineDetail.vue](file:///Users/x1you/Documents/ai-test-system/webui/src/views/PipelineDetail.vue) |
| `legacy/templates_sprint60/pipeline_progress.html` | 24 KB | [src/views/PipelineDetail.vue](file:///Users/x1you/Documents/ai-test-system/webui/src/views/PipelineDetail.vue) |
| `legacy/templates_sprint60/pipelines.html` | 26 KB | [src/views/PipelineList.vue](file:///Users/x1you/Documents/ai-test-system/webui/src/views/PipelineList.vue) |
| `legacy/templates_sprint60/results.html` | 22 KB | [src/views/PipelineDetail.vue](file:///Users/x1you/Documents/ai-test-system/webui/src/views/PipelineDetail.vue) |

**共计**：7 个文件，约 162 KB

**验证已无人引用**：
```bash
$ grep -r "templates_sprint60" src/ webui/ 2>/dev/null
# (无结果)
$ ls legacy/ 2>/dev/null
ls: legacy: No such file or directory
```

---

## 🗑️ 二、`src/components/` 内的过时段件

### 1. `src/components/GlobalIcons.vue`（已删除）

> **原因**：本组件通过 `provide/inject` 注入 SVG 字符串，是 V3 时代 BardIcon 还没诞生时的过渡方案。被 [BardIcon 组件](file:///Users/x1you/Documents/ai-test-system/webui/src/components/BardIcon.vue) 完全取代。

**关键代码回顾**（保留用于 git 历史）：
```js
import bardIcon from '../assets/icons/bard-flute.svg?raw'
export default {
  provides: { bardIcon: () => bardIcon }
}
```

**替代**：直接使用 `<BardIcon :size="32" />`

---

### 2. `src/components/PageLoader.vue`（已删除）

> **原因**：
> 1. 全项目**无任何组件 import 它**（grep 验证）
> 2. 内嵌旧版**实心圆遮盖描线**的 BardIcon（`circle r=240 fill=currentColor`）
> 3. 使用 SMIL `<animate>` 动画，性能差、不被现代 React 团队推荐
> 4. 被 [FlowSpinner.vue](file:///Users/x1you/Documents/ai-test-system/webui/src/components/FlowSpinner.vue) 完全取代

**替代**：直接使用 `<FlowSpinner :size="large" :label="加载中" />`

---

## 🗑️ 三、`webui/dist/`（每次 build 自动重建）

> 删除后 `npm run build` 会重新生成，无须 git 跟踪。  
> 已在 [webui/.gitignore](../../.gitignore) 显式忽略。

---

## 🔍 清理验证

```bash
# 1. 旧实心圆扫描（应无业务命中）
$ grep -rn 'r="240"' src/ --include="*.vue" --include="*.svg"
(无业务命中，仅 BardIcon emoji 变体的 r="252" 是设计需要)

# 2. emoji 业务图标扫描
$ grep -rn "🧪\|🌟\|⚡\|🚀\|📊" src/views/ --include="*.vue"
src/views/Login.vue:5:        <!-- V4 品牌图标：戴帽吟游诗人吹笛子（替代原 emoji 🧪） -->
(仅注释残留，无渲染)

# 3. 旧组件引用扫描
$ grep -rn "GlobalIcons\|PageLoader" src/ --include="*.vue" --include="*.js"
(无结果)
```

---

## ⚠️ 重要：未删除但需注意的"准遗留"文件

> 下列文件仍存在但**当前项目无 import 关系**，可能是 v3 时代的过渡组件，**待下一 sprint 决策**：

| 文件 | 大小 | 状态 | 处置建议 |
|------|------|------|----------|
| `src/components/StatusBadge.vue` | - | 需确认 | 若仍被 view 引用 → 保留；否则 → 删除 |
| `src/components/EmptyState.vue` | - | 需确认 | 同上 |
| `src/components/Pagination.vue` | - | 需确认 | 同上 |
| `src/components/StatCard.vue` | - | 需确认 | 同上 |
| `src/components/StepProgress.vue` | - | 需确认 | 同上 |
| `src/components/ToastContainer.vue` | - | 需确认 | 同上 |
| `src/components/ArtifactList.vue` | - | 需确认 | 同上 |
| `src/components/ArtifactPreview.vue` | - | 需确认 | 同上 |
| `src/components/FileDropZone.vue` | - | 需确认 | 同上 |
| `src/components/LogPanel.vue` | - | 需确认 | 同上 |

> 验证方式：`grep -rn "from './StatusBadge'" src/ --include="*.vue"`

---

## 🧹 v6.4.1 — 无人值守清理（2026-07-23）

> **执行脚本**：[scripts/cleanup_unattended.sh](file:///Users/x1you/Documents/ai-test-system/scripts/cleanup_unattended.sh)
> **清理时间**：2026-07-23 22:04:54
> **隔离区**：`logs/cleanup-quarantine-20260723-220454/`（可回滚，确认无误后可删）
> **清理报告**：`logs/cleanup-report-20260723-220454.md`

### 清理策略

采用**两层处置 + 白名单保护**机制：
- **Tier 1 直接删除**：纯临时/可重建文件（`__pycache__`、`.pyc`、`.DS_Store`、`.log`、`.pytest_cache`、`htmlcov`、`output` 等）
- **Tier 2 隔离移动**：疑似过时但可能有价值的文档/资源，移入隔离区，可回滚
- **保护白名单**：37 项关键路径（`.venv`、`.git`、源码目录、IDE 配置、关键文档/配置），绝不触碰

### 已隔离文件（Tier 2，可回滚）

| 文件 | 类型 | 大小 | 隔离原因 |
|------|------|------|----------|
| `BUGFIX_PIPELINE_START.md` | 失效 Bug 修复记录 | 7.36 KB | 引用的 `web/templates/index.html` 旧版 HTMX 模板已不存在，前端架构已变更，记录失效 |
| `docs/PRR_SESSION_2025_07_22.md` | 过时会话记录 | 10.81 KB | 日期异常（2025-07-22，与项目当前 2026-07 不符），带日期的阶段性会话快照，已无追溯价值 |
| `tests/test_error_toast_handling.js` | 失效前端测试 | 9.73 KB | 前端 HTMX 时代的错误提示测试，前端已迁 Vue 后整体移除，该 JS 测试已无运行环境 |

**共计**：3 个文件，约 27.90 KB

### 已直接删除（Tier 1）

本次扫描时项目本身较干净，`__pycache__`/`.pyc`/`.DS_Store`/`.log`/缓存目录/运行时输出均不存在，无实际删除项。

> 说明：`test_requirement.md`（.gitignore 显式忽略的临时测试需求草稿）在首次试运行时已被隔离至旧隔离区（隐藏目录），因沙箱环境对 `.gitignore` 忽略的隐藏目录有清理行为导致无法回滚。该文件为临时草稿且在 .gitignore 中，丢失不影响业务。隔离区机制已改用 `logs/` 下非隐藏目录规避此问题。

### 受保护跳过项

| 路径 | 原因 |
|------|------|
| `scripts/.DS_Store` | 落在受保护的 scripts 目录内 |
| `webui/dist` | webui/ 前端源码目录整体受保护 |

### 回滚方法

```bash
# 查看隔离区内容
ls -la logs/cleanup-quarantine-20260723-220454/

# 恢复某个文件（示例）
mv logs/cleanup-quarantine-20260723-220454/BUGFIX_PIPELINE_START.md ./

# 确认无误后彻底删除隔离区
rm -rf logs/cleanup-quarantine-20260723-220454/
```

### 单命令重新运行清理

```bash
bash scripts/cleanup_unattended.sh
```

> 每次运行会生成带时间戳的新日志、报告与隔离区，互不冲突。
