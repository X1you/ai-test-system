import { ref, watch } from 'vue'

const STORAGE_KEY = 'ai-test-theme'

/**
 * 主题管理 composable（模块级单例）
 *
 * 设计要点：
 *   - theme 为模块级 ref，所有组件共享同一份状态，避免多处 useTheme() 调用
 *     产生独立 ref 导致切换按钮 UI 不同步（修正点：原实现每次调用新建 ref）。
 *   - 默认 dark（方案 6.3「默认dark」）：仅当用户显式选过 'light' 才用 light，
 *     其余（含首次访问、旧版 'system' 值）一律回落为 dark，保证后台奥术调性。
 *   - 模块加载即 applyTheme()，避免主题闪烁（FOUC）。
 */
const stored = localStorage.getItem(STORAGE_KEY)
const theme = ref(stored === 'light' ? 'light' : 'dark')

function applyTheme() {
  document.documentElement.setAttribute('data-theme', theme.value)

  // 同步 <meta name="theme-color">（移动端地址栏配色）
  let meta = document.querySelector('meta[name="theme-color"]')
  if (!meta) {
    meta = document.createElement('meta')
    meta.name = 'theme-color'
    document.head.appendChild(meta)
  }
  meta.content = theme.value === 'dark' ? '#0b0e14' : '#ffffff'
}

function setTheme(value) {
  theme.value = value === 'dark' ? 'dark' : 'light'
  localStorage.setItem(STORAGE_KEY, theme.value)
  applyTheme()
}

function toggleTheme() {
  setTheme(theme.value === 'dark' ? 'light' : 'dark')
}

// 首次加载立即应用主题
applyTheme()
// 后续 theme 变化自动同步到 <html data-theme>
watch(theme, applyTheme)

export function useTheme() {
  return { theme, setTheme, toggleTheme }
}
