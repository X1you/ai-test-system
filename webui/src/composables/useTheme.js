import { ref, watch } from 'vue'

const STORAGE_KEY = 'ai-test-theme'

/**
 * 主题管理 composable
 * 三态：system / light / dark
 */
export function useTheme() {
  const stored = localStorage.getItem(STORAGE_KEY) || 'system'
  const theme = ref(stored)

  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')

  function applyTheme() {
    const resolved = theme.value === 'system'
      ? (mediaQuery.matches ? 'dark' : 'light')
      : theme.value

    document.documentElement.setAttribute('data-theme', resolved)

    // 同步 <meta name="theme-color">
    let meta = document.querySelector('meta[name="theme-color"]')
    if (!meta) {
      meta = document.createElement('meta')
      meta.name = 'theme-color'
      document.head.appendChild(meta)
    }
    meta.content = resolved === 'dark' ? '#12121a' : '#f5f5fa'
  }

  function setTheme(value) {
    theme.value = value
    localStorage.setItem(STORAGE_KEY, value)
    applyTheme()
  }

  // 监听系统主题变化
  mediaQuery.addEventListener('change', () => {
    if (theme.value === 'system') applyTheme()
  })

  // 初始化
  applyTheme()

  return { theme, setTheme }
}
