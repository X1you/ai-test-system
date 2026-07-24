/**
 * LLM Provider 类型定义 — 多协议多 Provider 抽象
 *
 * 对应后端 core.llm_client.py + web/api/config.py
 */

// 支持的协议（与后端 core.llm_client.PROTOCOL_* 一一对应）
export const LLM_PROTOCOLS = [
  'openai_compatible',
  'anthropic',
  'custom_http',
] as const

export type LLMProtocol = (typeof LLM_PROTOCOLS)[number]

/**
 * 单个 LLM Provider 配置
 * name 字段是用户起的别名（唯一），provider 字段是 vendor 标识
 */
export interface LLMProvider {
  name: string
  provider: string
  protocol: LLMProtocol
  base_url: string
  endpoint: string
  /** 完整 API Key（仅编辑模式下存在，列表展示时已脱敏） */
  api_key: string
  /** 脱敏后的 API Key（列表展示用，前 8 后 4 + ...） */
  api_key_masked?: string
  model: string
  temperature: number
  max_tokens: number
  timeout: number
  retry: number
  enabled: boolean
  priority: number
  tags: string[]
  // custom_http 专属字段
  method: string
  headers: Record<string, string>
  body_template: string
  response_path: string
}

/**
 * 测试连接结果
 */
export interface LLMServerCheck {
  ok: boolean
  status: string
  latency_ms: number
  provider: string
  model: string
  protocol: LLMProtocol
}

/**
 * Provider 测试请求体（POST /config/test_provider）
 */
export interface ProviderTestRequest {
  provider: LLMProvider
  timeout?: number
}

/**
 * 协议选项 UI 展示元数据
 */
export const PROTOCOL_META: Record<
  LLMProtocol,
  { label: string; desc: string; icon: string }
> = {
  openai_compatible: {
    label: 'OpenAI 兼容',
    desc: 'DeepSeek / GLM / OpenAI / Moonshot / Qwen 等所有兼容 OpenAI Chat Completions 协议的服务',
    icon: '🔌',
  },
  anthropic: {
    label: 'Anthropic',
    desc: 'Claude 全系列（claude-3-5-sonnet / haiku / opus 等）',
    icon: '🤖',
  },
  custom_http: {
    label: '自定义 HTTP',
    desc: '自建 LLM 网关 / 自定义代理 — 用户填 endpoint + body 模板 + 响应字段路径',
    icon: '🛠',
  },
}

/** 后端返回的 config 顶层结构（GET /api/v1/config） */
export interface ConfigResponse {
  /** 旧 schema 兼容字段（默认 provider 信息） */
  llm: {
    provider: string
    model: string
    base_url: string
    api_key: string
    temperature: number
  }
  /** 新 schema：所有 providers 列表（API Key 已脱敏） */
  llm_providers: LLMProvider[]
  /** 当前默认 provider 名字 */
  llm_default: string | null
  /** 后端支持的协议列表（动态下拉用） */
  llm_protocols: LLMProtocol[]
  knowledge_base: {
    enabled: boolean
    vault_path: string
  }
  pipeline: {
    default_mode: string
    default_dimensions: string
    default_formats: string
    self_check: boolean
  }
  validation: {
    valid: boolean
    errors: string[]
  }
}

/** 空 provider 模板（新增用） */
export const LLM_PROVIDER_EMPTY: LLMProvider = {
  name: '',
  provider: '',
  protocol: 'openai_compatible',
  base_url: '',
  endpoint: '',
  api_key: '',
  api_key_masked: '',
  model: '',
  temperature: 0.3,
  max_tokens: 8192,
  timeout: 120,
  retry: 2,
  enabled: true,
  priority: 0,
  tags: [],
  method: 'POST',
  headers: {},
  body_template: '',
  response_path: 'text',
}

/** 状态点颜色（语义化） */
export type ProviderStatusKind = 'ok' | 'degraded' | 'unknown'

/** 把后端 status 字符串映射为语义化状态 */
export function parseStatus(status: string | undefined): ProviderStatusKind {
  if (!status || status === 'not_configured') return 'unknown'
  if (status === 'ok') return 'ok'
  return 'degraded' // 含 degraded / error / missing: 等
}
