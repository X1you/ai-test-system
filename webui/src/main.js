import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

// CSS 导入顺序：globals.css 必须在 tokens.css 之前
//   globals 提供 Tailwind v4 原子层（@import "tailwindcss" + @theme）
//   tokens  提供语义变量（--bg-app 等），覆盖/补充 globals 的 base 样式
//   顺序颠倒会导致 tokens 的 body 样式被 globals 的 @theme 默认值覆盖
import './styles/globals.css'
import './styles/tokens.css'

/**
 * ════════════════════════════════════════════════════════════════
 *  应用引导 (V7 — Bard 吟游诗人 · 冷冽星空)
 * ════════════════════════════════════════════════════════════════
 *  设计要点：
 *    1. 必须在 mount() 之前调用 app.use(router) —— 否则 router-view 无法解析
 *    2. 全局错误捕获 → 控制台 + 上报到 console（占位，后续接 Sentry）
 *    3. 路由懒加载失败兜底 → 跳到 404 或刷新
 *    4. 性能埋点 → 仅在 dev 模式输出，生产被 terser 剥离
 * ════════════════════════════════════════════════════════════════
 */
const app = createApp(App)

// ─── 注册路由（必须在 mount 之前） ───
app.use(router)

// ─── 全局错误处理（生产环境会写入日志平台，此处先降级到 console） ───
app.config.errorHandler = (err, instance, info) => {
  console.error('[Vue Error]', err, info)
  // TODO: 接入 Sentry / 阿里云日志服务
}

// ─── 路由懒加载失败兜底 ───
router.onError((err) => {
  console.error('[Router Error] 路由懒加载失败:', err)
  if (err.message?.includes('Failed to fetch dynamically imported module')) {
    console.warn('检测到 chunk 加载失败，可能是部署后浏览器缓存了旧版本，请强制刷新 (Ctrl+Shift+R)')
  }
})

// ─── 性能埋点（仅 dev 模式输出） ───
if (import.meta.env.DEV) {
  const t0 = performance.now()
  app.mount('#app')
  requestAnimationFrame(() => {
    console.info(`[Perf] App mounted in ${(performance.now() - t0).toFixed(1)}ms`)
  })
} else {
  app.mount('#app')
}
