/**
 * API 请求封装
 * 统一 base URL / JSON 解析 / 错误处理 / Token 自动注入 / 401 自动跳转
 */

import { authToken, clearAuth } from './useAuth'

const BASE = '/api/v1'

export class ApiError extends Error {
  constructor(status, data) {
    super(data?.detail || data?.message || `HTTP ${status}`)
    this.status = status
    this.data = data
  }
}

async function request(method, path, options = {}) {
  const url = path.startsWith('http') ? path : `${BASE}${path}`
  const config = {
    method,
    headers: {},
    ...options,
  }

  // 自动注入 Authorization header（跳过登录接口自身）
  const token = authToken.value
  if (token && !path.includes('/auth/login')) {
    config.headers['Authorization'] = `Bearer ${token}`
  }

  // JSON body（非 FormData）
  if (options.json !== undefined) {
    config.headers['Content-Type'] = 'application/json'
    config.body = JSON.stringify(options.json)
    delete config.json
  }

  const resp = await fetch(url, config)

  // 401 未授权 — 清除 token 并跳转登录页
  if (resp.status === 401) {
    clearAuth()
    // 避免在登录页触发重复跳转
    if (!window.location.pathname.includes('/login')) {
      window.location.href = '/login'
    }
    throw new ApiError(401, { detail: '登录已过期，请重新登录' })
  }

  // Blob 响应（文件下载）
  if (options.responseType === 'blob') {
    if (!resp.ok) throw new ApiError(resp.status, { detail: '下载失败' })
    return resp.blob()
  }

  const data = await resp.json().catch(() => ({}))
  if (!resp.ok) throw new ApiError(resp.status, data)
  return data
}

export const api = {
  get: (path, opts) => request('GET', path, opts),
  post: (path, opts) => request('POST', path, opts),
  put: (path, opts) => request('PUT', path, opts),
  delete: (path, opts) => request('DELETE', path, opts),

  /** 上传文件（FormData） */
  upload(path, formData) {
    return request('POST', path, { body: formData })
  },

  /** 下载 blob */
  download(path) {
    return request('GET', path, { responseType: 'blob' })
  },

  /** 非 v1 前缀请求（如 /health） */
  raw(path, opts) {
    return request('GET', path, opts)
  },
}
