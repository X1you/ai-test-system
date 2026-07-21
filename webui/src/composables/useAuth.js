/**
 * 认证状态管理 — 登录 / 登出 / Token 持久化 / 用户信息
 *
 * Token 存储策略：
 *   - localStorage（持久化，刷新页面不丢失）
 *   - 生产环境可改为 httpOnly cookie + CSRF token 方案（更安全）
 */

import { reactive, computed } from 'vue'

const TOKEN_KEY = 'aitest_token'
const USER_KEY = 'aitest_user'

// ─── 响应式状态 ───
const state = reactive({
  token: localStorage.getItem(TOKEN_KEY) || '',
  user: JSON.parse(localStorage.getItem(USER_KEY) || 'null'),
})

// ─── 计算属性 ───
export const isAuthenticated = computed(() => !!state.token)
export const currentUser = computed(() => state.user)
export const authToken = computed(() => state.token)

// ─── 方法 ───

/**
 * 设置认证信息（登录成功后调用）
 */
export function setAuth(token, user) {
  state.token = token
  state.user = user
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

/**
 * 清除认证信息（登出 / 401 时调用）
 */
export function clearAuth() {
  state.token = ''
  state.user = null
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

/**
 * 登出 — 清除本地状态并跳转登录页
 */
export function logout() {
  clearAuth()
  // 直接跳转（与 useApi.js 401 处理一致），避免动态导入 router 造成循环依赖
  window.location.href = '/login'
}
