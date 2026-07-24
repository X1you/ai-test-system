/**
 * Usage Store — LLM 用量统计
 *
 * 服务端状态规范（遵循 SOUL.md）：
 *   - staleTime 缓存：未过期直接返回，避免高频请求后端
 *   - GET 请求去重：inflight Promise 复用，并发调用只发一次
 *   - 错误分层：网络异常 / 服务端 5xx / 业务 4xx 分层处理
 *
 * 数据特性：
 *   - 进程级内存聚合，重启清空（无持久化）
 *   - 调用频率低（仪表盘查看时拉取），staleTime 设 5s
 */

import { ref } from 'vue'
import { defineStore } from 'pinia'

import { apiGet, apiPost, ApiError } from '@/composables/useApi'
import { API } from '@/types/api'
import type { LLMUsageSnapshot, UsageResetResponse } from '@/types/usage'

/** staleTime：5s 内重复 fetch 直接复用缓存（避免高频请求后端） */
const STALE_MS = 5000

export const useUsageStore = defineStore('usage', () => {
  // ─── State ───
  const snapshot = ref<LLMUsageSnapshot | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const lastFetchedAt = ref(0)

  // inflight 去重：并发 GET 复用同一个 Promise
  let _inflight: Promise<LLMUsageSnapshot> | null = null

  /** 是否过期（超过 staleTime） */
  function _isStale(): boolean {
    if (!snapshot.value) return true
    return Date.now() - lastFetchedAt.value > STALE_MS
  }

  /**
   * 拉取用量快照。
   * @param force 强制刷新（忽略 staleTime）
   *
   * 并发去重：同一时刻多个组件调用 fetchUsage() 只发一次网络请求。
   */
  async function fetchUsage(force = false): Promise<LLMUsageSnapshot> {
    // 未过期且非强制 → 直接返回缓存
    if (!force && snapshot.value && !_isStale()) {
      return snapshot.value
    }
    // 并发去重：已有 inflight 请求 → 复用
    if (_inflight) return _inflight

    loading.value = true
    error.value = null
    _inflight = apiGet(API.USAGE.LLM)
      .then((data: LLMUsageSnapshot) => {
        snapshot.value = data
        lastFetchedAt.value = Date.now()
        return data
      })
      .catch((e: any) => {
        // 错误分层：网络异常 / HTTP 错误 / 其他
        if (e instanceof ApiError) {
          if (e.status === 0) {
            error.value = '网络连接失败，请检查后端服务'
          } else if (e.status >= 500) {
            error.value = `服务端错误: ${e.message}`
          } else {
            error.value = e.message
          }
        } else {
          error.value = e?.message || '获取用量统计失败'
        }
        throw e
      })
      .finally(() => {
        loading.value = false
        _inflight = null
      })
    return _inflight
  }

  /**
   * 清空统计（管理员操作）。
   * 成功后重新拉取（此时为空快照）。
   */
  async function resetUsage(): Promise<void> {
    // POST 不去重（用户主动操作，允许重复点击防护由组件层处理）
    const resp: UsageResetResponse = await apiPost(API.USAGE.RESET)
    // 重置成功后，本地直接置空（无需再请求一次）
    if (resp?.ok) {
      // 立即拉取最新（空）快照，刷新 UI
      await fetchUsage(true).catch(() => {})
    }
  }

  return {
    // state
    snapshot,
    loading,
    error,
    lastFetchedAt,
    // actions
    fetchUsage,
    resetUsage,
  }
})
