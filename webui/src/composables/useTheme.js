import { ref, watch } from 'vue'

const STORAGE_KEY = 'ai-test-theme'

/**
 * 主题管理 composable
 * 双态：light / dark（localStorage 持久化）
 * 暴露：theme、setTheme、toggleTheme
 */
export function useTheme() {
  const stored = localStorage.getItem(STORAGE_KEY)
  // 旧版存储值可能为 'system'，一律回落为 light
  const theme = ref(stored === 'dark' ? 'dark' : 'light')

  function applyTheme() {
    document.documentElement.setAttribute('data-theme', theme.value)

    // 同步 <meta name="theme-color">
    let meta = document.querySelector('meta[name="theme-color"]')
    if (!meta) {
      meta = document.createElement('meta')
      meta.name = 'theme-color'
      document.head.appendChild(meta)
    }
    meta.content = theme.value === 'dark' ? '#030a06' : '#fafafa'
  }

  function setTheme(value) {
    theme.value = value === 'dark' ? 'dark' : 'light'
    localStorage.setItem(STORAGE_KEY, theme.value)
    applyTheme()
  }

  function toggleTheme() {
    setTheme(theme.value === 'dark' ? 'light' : 'dark')
  }

  // theme 变化时自动重新应用
  watch(theme, applyTheme)

  // 初始化
  applyTheme()

  return { theme, setTheme, toggleTheme }
}
