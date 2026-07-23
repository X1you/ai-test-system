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
