/**
 * Config Store — 多 LLM Provider 配置管理
 *
 * 提供：
 *   - fetchConfig()      拉取全部配置（含 providers 列表）
 *   - updateConfig()     部分更新（pipeline/output/llm.providers）
 *   - testProvider()     测试单个 provider（不入库）
 *   - setDefaultProvider() 切换默认 provider
 *   - parseStatus()      状态字符串 → 语义化
 *
 * UI 状态机（reactive）：
 *   - providers, defaultName, protocols, validation
 *   - lastCheckResults  缓存最近一次测试结果（key=provider.name）
 */

import { computed, reactive, ref } from 'vue'
import { defineStore } from 'pinia'

import { apiGet, apiPost, apiPut } from '@/composables/useApi'
import { API } from '@/types/api'
import {
  LLM_PROVIDER_EMPTY,
  type ConfigResponse,
  type LLMServerCheck,
  LLMProvider,
  LLMProtocol,
  parseStatus,
} from '@/types/config'

export const useConfigStore = defineStore('config', () => {
  // ─── State ───
  const loading = ref(false)
  const saving = ref(false)
  const error = ref<string | null>(null)

  const providers = ref<LLMProvider[]>([])
  const defaultName = ref<string | null>(null)
  const protocols = ref<LLMProtocol[]>([])
  const validation = reactive<{ valid: boolean; errors: string[] }>({
    valid: true,
    errors: [],
  })
  const pipeline = ref<ConfigResponse['pipeline']>({
    default_mode: 'semi',
    default_dimensions: 'basic',
    default_formats: 'excel',
    self_check: false,
  })
  const knowledgeBase = ref<ConfigResponse['knowledge_base']>({
    enabled: false,
    vault_path: 'N/A',
  })

  // 测试结果缓存（key=provider.name）
  const lastCheckResults = reactive<Record<string, LLMServerCheck | null>>({})

  // P2-3：系统健康检查 per-provider 状态（key=provider.name，value=ok/degraded/error）
  const healthStatus = reactive<Record<string, string>>({})

  // ─── Getters ───
  const defaultProvider = computed<LLMProvider | null>(() => {
    if (!defaultName.value) return providers.value[0] || null
    return providers.value.find((p) => p.name === defaultName.value) || null
  })

  const enabledProviders = computed(() =>
    providers.value.filter((p) => p.enabled),
  )

  // ─── Actions ───

  async function fetchConfig(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const resp: ConfigResponse = await apiGet(API.CONFIG.GET)
      providers.value = resp.llm_providers || []
      defaultName.value = resp.llm_default
      protocols.value = resp.llm_protocols || []
      validation.valid = resp.validation?.valid ?? true
      validation.errors = resp.validation?.errors ?? []
      pipeline.value = resp.pipeline
      knowledgeBase.value = resp.knowledge_base
    } catch (e: any) {
      error.value = e?.message || '加载配置失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function updateConfig(body: {
    pipeline?: Partial<ConfigResponse['pipeline']>
    output?: Record<string, unknown>
    llm?: { providers?: LLMProvider[]; default?: string }
  }): Promise<void> {
    saving.value = true
    error.value = null
    try {
      const resp = await apiPut(API.CONFIG.PUT, body)
      validation.valid = resp?.validation?.valid ?? true
      validation.errors = resp?.validation?.errors ?? []
      // 重新拉取以获取最新列表（保证脱敏后字段同步）
      await fetchConfig()
    } catch (e: any) {
      error.value = e?.message || '保存配置失败'
      throw e
    } finally {
      saving.value = false
    }
  }

  /**
   * 测试单个 provider 连接（不入库）。
   * 入参可以是已存在的 provider 对象（用 name 查缓存），也可以是临时未保存的 form draft。
   * 返回测试结果（同时写入 lastCheckResults[name]）。
   */
  async function testProvider(
    provider: LLMProvider,
    timeout = 10,
  ): Promise<LLMServerCheck> {
    const result = await apiPost(API.CONFIG.TEST_PROVIDER, {
      provider,
      timeout,
    })
    const check: LLMServerCheck = {
      ok: !!result?.ok,
      status: result?.status || 'unknown',
      latency_ms: result?.latency_ms || 0,
      provider: result?.provider || provider.name,
      model: result?.model || provider.model,
      protocol: result?.protocol || provider.protocol,
    }
    lastCheckResults[provider.name] = check
    return check
  }

  async function setDefaultProvider(name: string): Promise<void> {
    await apiPost(API.CONFIG.SET_DEFAULT, { name })
    defaultName.value = name
    await fetchConfig()
  }

  /**
   * V1：拖拽排序。names 为按新顺序排列的 provider name 列表。
   * 后端会按列表顺序回写 priority（index 即 priority），无需前端计算。
   * 失败时抛出异常。
   */
  async function reorderProviders(names: string[]): Promise<void> {
    if (!Array.isArray(names) || names.length === 0) return
    // 乐观更新本地顺序，提升 UX 流畅度（保存失败时由后端再次 fetch 校正）
    const byName = new Map(providers.value.map((p) => [p.name, p]))
    const reordered = names
      .map((n) => byName.get(n))
      .filter((p): p is LLMProvider => Boolean(p))
    // 保留未在 names 中的尾部 provider（防御性）
    const rest = providers.value.filter((p) => !names.includes(p.name))
    providers.value = [...reordered, ...rest]
    saving.value = true
    try {
      await apiPost(API.CONFIG.REORDER_PROVIDERS, { names })
    } catch (e: any) {
      // 失败时回拉后端真实状态
      await fetchConfig().catch(() => {})
      error.value = e?.message || '重排 Provider 失败'
      throw e
    } finally {
      saving.value = false
    }
  }

  /**
   * V2：批量启用/禁用。
   * 乐观更新本地 enabled 字段，失败时回拉后端状态。
   * 后端会处理「默认被禁用时自动切默认」的逻辑。
   */
  async function batchToggleEnabled(
    names: string[],
    enabled: boolean,
  ): Promise<void> {
    if (!Array.isArray(names) || names.length === 0) return
    const target = new Set(names)
    const prev = new Map(providers.value.map((p) => [p.name, p.enabled]))
    // 乐观更新
    providers.value = providers.value.map((p) =>
      target.has(p.name) ? { ...p, enabled } : p,
    )
    saving.value = true
    try {
      const resp = await apiPost(API.CONFIG.BATCH_TOGGLE, {
        names,
        enabled,
      })
      // 后端若切换了 default，同步本地 defaultName
      if (resp?.default && resp.default !== defaultName.value) {
        defaultName.value = resp.default
      }
    } catch (e: any) {
      // 回滚
      providers.value = providers.value.map((p) =>
        target.has(p.name) && prev.has(p.name)
          ? { ...p, enabled: prev.get(p.name)! }
          : p,
      )
      await fetchConfig().catch(() => {})
      error.value = e?.message || '批量操作失败'
      throw e
    } finally {
      saving.value = false
    }
  }

  /**
   * V2：批量删除。
   * 乐观移除本地项，失败时回拉后端状态。
   * 后端会拒绝：删除默认 provider / 清空列表。
   */
  async function batchDeleteProviders(names: string[]): Promise<void> {
    if (!Array.isArray(names) || names.length === 0) return
    const target = new Set(names)
    const snapshot = providers.value.slice()
    // 乐观删除
    providers.value = providers.value.filter((p) => !target.has(p.name))
    saving.value = true
    try {
      await apiPost(API.CONFIG.BATCH_DELETE, { names })
    } catch (e: any) {
      providers.value = snapshot
      await fetchConfig().catch(() => {})
      error.value = e?.message || '批量删除失败'
      throw e
    } finally {
      saving.value = false
    }
  }

  /** 工具：构造一个空的 provider（新增用） */
  function blankProvider(protocol: LLMProtocol = 'openai_compatible'): LLMProvider {
    return { ...LLM_PROVIDER_EMPTY, protocol }
  }

  // P2-3：拉取系统健康检查 per-provider 状态（GET /health/ready，无鉴权，根路径）
  async function fetchHealthStatus(): Promise<void> {
    try {
      const resp = await apiGet(API.HEALTH.READY, { absolute: true })
      const llmChecks = resp?.checks?.llm
      if (llmChecks && typeof llmChecks === 'object') {
        for (const [name, status] of Object.entries(llmChecks)) {
          healthStatus[name] = String(status)
        }
      }
    } catch {
      // 静默失败：健康检查不可用时不影响主流程
    }
  }

  return {
    // state
    loading,
    saving,
    error,
    providers,
    defaultName,
    protocols,
    validation,
    pipeline,
    knowledgeBase,
    lastCheckResults,
    healthStatus,
    // getters
    defaultProvider,
    enabledProviders,
    // actions
    fetchConfig,
    updateConfig,
    testProvider,
    setDefaultProvider,
    reorderProviders,
    batchToggleEnabled,
    batchDeleteProviders,
    blankProvider,
    fetchHealthStatus,
    // utils
    parseStatus,
  }
})
