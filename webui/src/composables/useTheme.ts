/**
 * 主题切换 — 全局持久化（localStorage），不做路由级重置
 */
import { ref, watch } from 'vue'

export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'bard-theme'
const currentTheme = ref<Theme>('light')

function applyTheme(theme: Theme) {
  const html = document.documentElement
  if (theme === 'dark') {
    html.classList.add('dark')
  } else {
    html.classList.remove('dark')
  }
}

function initTheme() {
  const saved = localStorage.getItem(STORAGE_KEY) as Theme | null
  if (saved) {
    currentTheme.value = saved
  } else {
    // 首次访问默认 light
    currentTheme.value = 'light'
  }
  applyTheme(currentTheme.value)
}

function setTheme(theme: Theme) {
  currentTheme.value = theme
  localStorage.setItem(STORAGE_KEY, theme)
  applyTheme(theme)
}

function toggleTheme() {
  setTheme(currentTheme.value === 'light' ? 'dark' : 'light')
}

export function useTheme() {
  return { currentTheme, toggleTheme, setTheme, initTheme }
}
