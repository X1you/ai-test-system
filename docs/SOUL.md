# SOUL.md — 前端工程硬性规范

> 本文档为 ai-test-system 前端工程的强制规范，所有前端开发工作必须严格遵守。
> 违反任一红线即视为不合规，必须修复后方可合入。

---

## 1. 构建性能预算

- **单入口 Chunk（Gzip 后）≤ 200KB**
- **dist 目录总大小 ≤ 5MB**
- **必须配置 Tree Shaking**（Vite 生产构建默认开启，禁止关闭）
- **大图片必须压缩 + WebP 转换**（单图 ≤ 200KB，禁止未压缩 PNG/JPG 进 dist）
- **禁止引入新 UI 库**（复用既有基础组件，lucide-vue-next 为唯一图标库）
- **package.json 必须锁定绝对版本**（禁止 `^` / `~` 范围）

## 2. 状态管理

- **服务端状态必须使用 Pinia**，强制配置 `staleTime`（默认 5s）
- **GET 请求必须 inflight 去重**（同一 key 并发请求复用 Promise）
- **服务端状态与客户端状态物理隔离**（不同 store 文件，禁止混用）
- **本地缓存必须设置过期时间戳 + 版本号**（localStorage / sessionStorage 项须含 `expiresAt` + `version`）
- **页面切换必须取消未完成请求**（AbortController 或路由守卫清理）

## 3. 网络请求

- **GET 请求去重**（同 key inflight 复用）
- **接口异常分层处理**：
  - 网络错误 → toast + 重试按钮
  - 4xx → inline 字段错误或 toast
  - 5xx → toast + 上报
  - 401 → 跳登录
- **提交按钮必须防重复点击**（disabled + loading + aria-busy 三保障）

## 4. 错误处理

- **ErrorBoundary 必须包裹独立功能模块**（每个视图 / 每个独立交互区）
- **第三方资源必须有降级方案**（CDN 失败回退本地，字体回退系统栈）
- **必须清理定时器和事件监听器**（onBeforeUnmount 清理 setInterval / setTimeout / addEventListener，防内存泄漏）

## 5. 无障碍

- **所有交互控件必须有 ARIA 语义标签**（role / aria-label / aria-describedby）
- **正确 tabindex**（交互控件 0，非交互 -1，顺序与视觉一致）
- **焦点管理**（弹框打开聚焦首元素，关闭归还触发器，Tab 循环）
- **`prefers-reduced-motion` 降级强制**（动效降到 0.01ms 或瞬时）
- **最小点击区域 44×44px**（WCAG 2.5.8 Level AA）
- **对比度 ≥ 4.5:1**（正文）/ 3:1（大字，WCAG 1.4.3）

## 6. 交付规范

- **热修复必须有规范注释**（文件头标注 `[HOTFIX yyyy-mm-dd] 原因`）
- **多阶段构建 Dockerfile**（builder → nginx，禁止单阶段）
- **nginx.conf 配置正确**（gzip on / 缓存 hash 资源 / SPA fallback）
- **dist 目录 ≤ 5MB**

## 7. 技术栈要求

- **TypeScript Strict Mode**（tsconfig `strict: true`）
- **Vue 3 + Vite**（不切换框架）
- **Tailwind v4 + CSS 变量 token 双轨**（tokens.css 为单一真相源，@theme 映射）
- **package.json 锁定绝对版本**

---

## 参照实现

- 服务端状态规范参照 [stores/config.ts](../webui/src/stores/config.ts)
- 动效降级参照 [globals.css](../webui/src/styles/globals.css) `@media (prefers-reduced-motion: reduce)`
- 焦点环参照 [globals.css](../webui/src/styles/globals.css) `:focus-visible`
- 色彩 token 参照 [tokens.css](../webui/src/styles/tokens.css)
- 基础组件参照 [components/ui/](../webui/src/components/ui/)
