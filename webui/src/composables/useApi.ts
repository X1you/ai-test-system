/**
 * API 请求封装
 * 无鉴权（本地工具模式）+ 自动 Content-Type + 统一错误处理
 */

const BASE = '/api/v1'

export class ApiError extends Error {
  status: number
  data: any
  constructor(status: number, data: any) {
    super(data?.detail || data?.message || `HTTP ${status}`)
    this.status = status
    this.data = data
  }
}

interface ApiOptions {
  body?: any
  headers?: Record<string, string>
  signal?: AbortSignal
  // absolute=true 时，path 视为根路径，不自动拼接 /api/v1 前缀。
  // 用途：后端健康检查端点 /health/* 挂载在根路径（非 /api/v1），
  //       供 k8s liveness/readiness 探针使用，前端调用时需显式声明。
  absolute?: boolean
}

/**
 * 统一请求函数
 * - body 是 FormData → 浏览器自动设 multipart/form-data
 * - body 是普通对象 → 自动 JSON.stringify + Content-Type: application/json
 * - opts.absolute=true → path 不拼接 BASE（用于 /health/* 等根路径端点）
 */
export async function api(method: string, path: string, opts?: ApiOptions): Promise<any> {
  const headers: Record<string, string> = { ...opts?.headers }
  let body = opts?.body

  if (body && !(body instanceof FormData)) {
    headers['Content-Type'] = headers['Content-Type'] || 'application/json'
    body = JSON.stringify(body)
  }

  // 拼接最终 URL：根路径端点（如 /health/ready）不加 /api/v1 前缀
  const url = opts?.absolute ? path : BASE + path

  let resp: Response
  try {
    resp = await fetch(url, { method, headers, body, signal: opts?.signal })
  } catch (err) {
    // 网络异常（后端未启动 / 断网）
    throw new ApiError(0, { detail: '网络连接失败，请检查后端服务是否启动' })
  }

  if (!resp.ok) {
    let data
    try {
      data = await resp.json()
    } catch {
      data = { detail: resp.statusText }
    }
    throw new ApiError(resp.status, data)
  }

  // 某些端点返回非 JSON（如 FileResponse 文件下载）
  const ct = resp.headers.get('content-type') || ''
  if (ct.includes('application/json')) {
    return resp.json()
  }
  return resp
}

/** GET 便捷方法 */
export function apiGet(path: string, opts?: ApiOptions) {
  return api('GET', path, opts)
}

/** POST 便捷方法 */
export function apiPost(path: string, body?: any, opts?: ApiOptions) {
  return api('POST', path, { ...opts, body })
}

/** PUT 便捷方法 */
export function apiPut(path: string, body?: any, opts?: ApiOptions) {
  return api('PUT', path, { ...opts, body })
}
