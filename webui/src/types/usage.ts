/**
 * LLM 用量统计类型定义 — 对应后端 core.llm_usage + web/api/usage.py
 *
 * 数据语义：
 *   - 进程级内存聚合，重启后清空（无持久化）
 *   - success_rate = success / calls（0~1）
 *   - latency_ms_avg / latency_ms_max 仅统计真实 LLM 调用（不含缓存命中）
 */

/** 单个 Provider 的累计统计 */
export interface ProviderUsageStats {
  calls: number
  success: number
  errors: number
  tokens: number
  /** 平均延迟（毫秒） */
  latency_ms_avg: number
  /** 历史最大延迟（毫秒） */
  latency_ms_max: number
  /** 成功率（0~1） */
  success_rate: number
  /** 最近一次调用时间（unix timestamp） */
  last_call_at: number
  /** 最近一次错误信息（空字符串表示无错误或最近调用成功） */
  last_error: string
  /** 按 model 维度细分 */
  by_model: Record<
    string,
    { calls: number; success: number; errors: number; tokens: number }
  >
}

/** 顶层汇总 */
export interface UsageTotals {
  calls: number
  success: number
  errors: number
  tokens: number
  success_rate: number
}

/** GET /api/v1/usage/llm 响应体 */
export interface LLMUsageSnapshot {
  /** 统计开始时间（unix timestamp） */
  started_at: number
  /** 已运行时长（秒） */
  uptime_seconds: number
  totals: UsageTotals
  /** key = provider name */
  providers: Record<string, ProviderUsageStats>
}

/** POST /api/v1/usage/reset 响应体 */
export interface UsageResetResponse {
  ok: boolean
  message: string
  /** 清空前的快照（便于审计） */
  before: LLMUsageSnapshot
}
