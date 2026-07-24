/**
 * 集中式 API Mock — 前端 e2e 测试用
 *
 * 设计：
 *  - 通过 page.route() 拦截 /api/v1/* 与 /health/* 请求，返回确定性 JSON，
 *    使前端测试不依赖后端运行状态（CI 稳定、快速、可重复）。
 *  - 后端行为由独立后端 e2e 套件（tests/e2e/）覆盖。
 *  - 每个测试可在 installMocks 时覆盖默认响应（如模拟空列表 / 错误）。
 */
import { type Page, type Route } from '@playwright/test'

// ─── 测试数据 ───

export const MOCK_PROVIDERS = [
  {
    name: 'glm',
    provider: 'bigmodel',
    protocol: 'openai_compatible',
    base_url: 'https://open.bigmodel.cn/api/paas/v4',
    endpoint: '',
    api_key: 'sk-abcdefgh1234567890wxyz',
    api_key_masked: 'sk-abcdef...wxyz',
    model: 'glm-4.7-flash',
    temperature: 0.3,
    max_tokens: 8192,
    timeout: 120,
    retry: 2,
    enabled: true,
    priority: 0,
    tags: ['production', '便宜'],
    method: 'POST',
    headers: {},
    body_template: '',
    response_path: 'text',
  },
  {
    name: 'deepseek',
    provider: 'deepseek',
    protocol: 'openai_compatible',
    base_url: 'https://api.deepseek.com/v1',
    endpoint: '',
    api_key: 'sk-deepseek1234567890abcd',
    api_key_masked: 'sk-deepse...abcd',
    model: 'deepseek-chat',
    temperature: 0.3,
    max_tokens: 8192,
    timeout: 120,
    retry: 2,
    enabled: true,
    priority: 1,
    tags: ['备用'],
    method: 'POST',
    headers: {},
    body_template: '',
    response_path: 'text',
  },
  {
    name: 'claude',
    provider: 'anthropic',
    protocol: 'anthropic',
    base_url: 'https://api.anthropic.com',
    endpoint: '',
    api_key: 'sk-ant-claude1234567890efgh',
    api_key_masked: 'sk-ant-cl...efgh',
    model: 'claude-3-5-sonnet',
    temperature: 0.3,
    max_tokens: 8192,
    timeout: 120,
    retry: 2,
    enabled: false,
    priority: 2,
    tags: ['production'],
    method: 'POST',
    headers: {},
    body_template: '',
    response_path: 'text',
  },
]

// 默认配置响应（GET /api/v1/config）
export const MOCK_CONFIG = {
  llm: {
    provider: 'glm',
    model: 'glm-4.7-flash',
    base_url: 'https://open.bigmodel.cn/api/paas/v4',
    api_key: 'sk-abcdef...wxyz',
    temperature: 0.3,
  },
  llm_providers: MOCK_PROVIDERS,
  llm_default: 'glm',
  llm_protocols: ['anthropic', 'custom_http', 'openai_compatible'],
  knowledge_base: { enabled: false, vault_path: 'N/A' },
  pipeline: {
    default_mode: 'semi',
    default_dimensions: 'basic',
    default_formats: 'excel',
    self_check: false,
  },
  validation: { valid: true, errors: [] },
}

// 默认用量统计（GET /api/v1/usage/llm）
export const MOCK_USAGE = {
  started_at: 1753372800,
  uptime_seconds: 3600,
  totals: { calls: 42, success: 40, errors: 2, tokens: 12345, success_rate: 0.952 },
  providers: {
    glm: {
      calls: 30, success: 29, errors: 1, tokens: 9000,
      latency_ms_avg: 850, latency_ms_max: 2100, success_rate: 0.967,
      last_call_at: 1753376400, last_error: '',
      by_model: { 'glm-4.7-flash': { calls: 30, success: 29, errors: 1, tokens: 9000 } },
    },
    deepseek: {
      calls: 12, success: 11, errors: 1, tokens: 3345,
      latency_ms_avg: 720, latency_ms_max: 1500, success_rate: 0.917,
      last_call_at: 1753376300, last_error: 'timeout',
      by_model: { 'deepseek-chat': { calls: 12, success: 11, errors: 1, tokens: 3345 } },
    },
  },
}

// 默认任务列表（GET /api/v1/pipeline/list）
export const MOCK_TASKS = [
  {
    pipeline_id: 'task-001',
    status: 'done',
    mode: 'semi',
    created_at: '2026-07-24T10:00:00Z',
    completed_steps: [1, 2, 3, 4, 5, 6, 7],
    requirements_name: 'order_requirements.md',
  },
  {
    pipeline_id: 'task-002',
    status: 'running',
    mode: 'auto',
    created_at: '2026-07-24T11:00:00Z',
    completed_steps: [1, 2, 3],
    requirements_name: 'ecommerce_order.md',
  },
]

// 默认健康检查（GET /health/ready）
export const MOCK_HEALTH_READY = {
  status: 'ok',
  version: '2.3.0',
  checks: { db: 'ok', llm: 'ok', kb: 'ok' },
}

// ─── Mock 装配 ───

export interface MockOverrides {
  config?: any
  configStatus?: number
  usage?: any
  tasks?: any[]
  health?: any
  healthStatus?: number
  /** test_provider 自定义响应（按 provider.name 路由） */
  testProvider?: (body: any) => any
  /** PUT /config 自定义处理（用于校验保存载荷） */
  putConfig?: (body: any) => any
}

/**
 * 安装 API mock。返回卸载函数（一般不需手动调，page 关闭即清理）。
 */
export async function installMocks(page: Page, overrides: MockOverrides = {}) {
  const configResp = overrides.config ?? MOCK_CONFIG
  const configStatus = overrides.configStatus ?? 200

  await page.route('**/api/v1/config', async (route: Route) => {
    const req = route.request()
    if (req.method() === 'GET') {
      await route.fulfill({ status: configStatus, contentType: 'application/json', body: JSON.stringify(configResp) })
    } else if (req.method() === 'PUT') {
      if (overrides.putConfig) {
        const r = overrides.putConfig(JSON.parse(req.postData() || '{}'))
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(r) })
      } else {
        // 默认：返回更新后的 config（PUT 后前端会重新 fetch，这里回 200 即可）
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
      }
    } else {
      await route.continue()
    }
  })

  await page.route('**/api/v1/config/test_provider', async (route: Route) => {
    if (route.request().method() !== 'POST') return route.continue()
    const body = JSON.parse(route.request().postData() || '{}')
    if (overrides.testProvider) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(overrides.testProvider(body)) })
    }
    // 默认：连接成功
    const name = body?.provider?.name || 'unknown'
    const ok = name !== 'claude' // 模拟 claude（disabled）连接失败
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok,
        status: ok ? 'ok' : 'error: connection refused',
        latency_ms: ok ? 320 : 0,
        provider: name,
        model: body?.provider?.model || '',
        protocol: body?.provider?.protocol || 'openai_compatible',
      }),
    })
  })

  await page.route('**/api/v1/config/set_default', async (route: Route) => {
    if (route.request().method() !== 'POST') return route.continue()
    const body = JSON.parse(route.request().postData() || '{}')
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, default: body.name }) })
  })

  await page.route('**/api/v1/config/batch_toggle', async (route: Route) => {
    if (route.request().method() !== 'POST') return route.continue()
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, updated: 2 }) })
  })

  await page.route('**/api/v1/config/batch_delete', async (route: Route) => {
    if (route.request().method() !== 'POST') return route.continue()
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, deleted: 1 }) })
  })

  await page.route('**/api/v1/config/reorder_providers', async (route: Route) => {
    if (route.request().method() !== 'POST') return route.continue()
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
  })

  await page.route('**/api/v1/config/providers', async (route: Route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PROVIDERS) })
  })

  await page.route('**/api/v1/usage/llm', async (route: Route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(overrides.usage ?? MOCK_USAGE) })
  })

  await page.route('**/api/v1/usage/reset', async (route: Route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, message: '用量统计已清空', before: overrides.usage ?? MOCK_USAGE }) })
  })

  await page.route('**/api/v1/pipeline/list', async (route) => {
    const tasks = overrides.tasks ?? MOCK_TASKS
    // store.fetchList 期望 { items, all_stats, pages } 结构（非裸数组）
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: tasks, all_stats: {}, pages: 1 }),
    })
  })

  // 知识库端点兜底
  await page.route('**/api/v1/knowledge/**', async (route: Route) => {
    if (route.request().url().includes('current_config')) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ provider_type: 'mcp_filesystem', connection_url: '', auth_token: '', vault_path: '' }) })
    }
    if (route.request().url().includes('status')) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ enabled: false, total: 0 }) })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
  })

  // 健康检查（根路径，非 /api/v1）
  await page.route('**/health/ready', async (route: Route) => {
    return route.fulfill({
      status: overrides.healthStatus ?? 200,
      contentType: 'application/json',
      body: JSON.stringify(overrides.health ?? MOCK_HEALTH_READY),
    })
  })

  await page.route('**/health/live', async (route: Route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'alive' }) })
  })
}
