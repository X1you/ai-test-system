<script setup lang="ts">
/**
 * UsageDashboard — LLM 用量仪表盘
 *
 * 展示：
 *   - 顶部汇总卡片：总调用 / 成功 / 失败 / Token / 成功率 / 运行时长
 *   - Provider 维度表格：calls / success_rate / tokens / avg_latency / max_latency / last_call
 *
 * 交互：
 *   - [刷新] 手动拉取（强制忽略 staleTime）
 *   - [重置] 二次确认后清空统计（防误操作）
 *
 * 规范：
 *   - 复用 usage store 的 staleTime 缓存 + 并发去重
 *   - 重置按钮防重复点击（请求中 disabled）
 *   - 表格 ARIA 语义（role=table + aria-label）
 */

import { computed, onMounted, ref } from 'vue'

import { useToastStore } from '@/composables/useToast'
import { useUsageStore } from '@/stores/usage'

const usageStore = useUsageStore()
const toast = useToastStore()

const snapshot = computed(() => usageStore.snapshot)
const loading = computed(() => usageStore.loading)
const error = computed(() => usageStore.error)

// 二次确认状态（响应式）
const confirmingReset = ref(false)
// 重置按钮防重复点击
const resetting = ref(false)

onMounted(() => {
  // 挂载时拉取（store 内部会判断 staleTime）
  usageStore.fetchUsage().catch(() => {
    // 错误已由 store 暴露给 error，无需额外 toast
  })
})

// ─── 格式化辅助 ───

function fmtNum(n: number | undefined): string {
  if (n == null) return '0'
  return n.toLocaleString('zh-CN')
}

function fmtTokens(n: number | undefined): string {
  if (!n) return '0'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'k'
  return String(n)
}

function fmtRate(r: number | undefined): string {
  if (r == null) return '—'
  return (r * 100).toFixed(1) + '%'
}

function fmtLatency(ms: number | undefined): string {
  if (!ms) return '—'
  if (ms >= 1000) return (ms / 1000).toFixed(2) + 's'
  return Math.round(ms) + 'ms'
}

function fmtUptime(seconds: number | undefined): string {
  if (!seconds) return '—'
  if (seconds < 60) return Math.round(seconds) + 's'
  if (seconds < 3600) return Math.floor(seconds / 60) + 'm'
  if (seconds < 86400) return Math.floor(seconds / 3600) + 'h'
  return Math.floor(seconds / 86400) + 'd'
}

function fmtRelativeTime(ts: number | undefined): string {
  if (!ts) return '—'
  const diff = Date.now() / 1000 - ts
  if (diff < 60) return '刚刚'
  if (diff < 3600) return Math.floor(diff / 60) + '分钟前'
  if (diff < 86400) return Math.floor(diff / 3600) + '小时前'
  return Math.floor(diff / 86400) + '天前'
}

// Provider 列表（按调用次数降序）
const providerRows = computed(() => {
  const p = snapshot.value?.providers
  if (!p) return []
  return Object.entries(p)
    .map(([name, stats]) => ({ name, ...stats }))
    .sort((a, b) => b.calls - a.calls)
})

const totals = computed(() => snapshot.value?.totals)

// ─── 操作 ───

async function handleRefresh() {
  try {
    await usageStore.fetchUsage(true)
    toast.success('已刷新用量数据')
  } catch (e: any) {
    toast.error(e?.message || '刷新失败')
  }
}

function requestReset() {
  confirmingReset.value = true
}

function cancelReset() {
  confirmingReset.value = false
}

async function confirmReset() {
  resetting.value = true
  try {
    await usageStore.resetUsage()
    toast.success('用量统计已清空')
    confirmingReset.value = false
  } catch (e: any) {
    toast.error(e?.message || '清空失败')
  } finally {
    resetting.value = false
  }
}
</script>

<template>
  <div class="usage-dashboard" role="region" aria-label="LLM 用量仪表盘">
    <!-- 顶部操作栏 -->
    <div class="ud-toolbar">
      <div class="ud-title">
        <h3 class="ud-h3">LLM 用量仪表盘</h3>
        <span v-if="snapshot" class="ud-uptime" aria-label="统计已运行时长">
          运行 {{ fmtUptime(snapshot.uptime_seconds) }}
        </span>
      </div>
      <div class="ud-actions">
        <button
          type="button"
          class="btn-secondary"
          :disabled="loading"
          :aria-busy="loading"
          aria-label="刷新用量数据"
          @click="handleRefresh"
        >
          {{ loading ? '刷新中…' : '↻ 刷新' }}
        </button>
        <button
          type="button"
          class="btn-secondary"
          :disabled="resetting"
          aria-label="清空用量统计"
          @click="requestReset"
        >
          清空统计
        </button>
      </div>
    </div>

    <!-- 错误提示 -->
    <p v-if="error" class="ud-error" role="alert">{{ error }}</p>

    <!-- 空状态 -->
    <div v-if="!loading && (!totals || totals.calls === 0)" class="ud-empty">
      暂无调用数据。LLM 调用后会在此展示统计。
    </div>

    <!-- 汇总卡片 -->
    <div v-else-if="totals" class="ud-totals" role="list" aria-label="汇总统计">
      <div class="ud-stat" role="listitem">
        <span class="ud-stat-label">总调用</span>
        <span class="ud-stat-value">{{ fmtNum(totals.calls) }}</span>
      </div>
      <div class="ud-stat ud-stat-ok" role="listitem">
        <span class="ud-stat-label">成功</span>
        <span class="ud-stat-value">{{ fmtNum(totals.success) }}</span>
      </div>
      <div class="ud-stat ud-stat-err" role="listitem">
        <span class="ud-stat-label">失败</span>
        <span class="ud-stat-value">{{ fmtNum(totals.errors) }}</span>
      </div>
      <div class="ud-stat" role="listitem">
        <span class="ud-stat-label">Token 总量</span>
        <span class="ud-stat-value">{{ fmtTokens(totals.tokens) }}</span>
      </div>
      <div class="ud-stat" role="listitem">
        <span class="ud-stat-label">成功率</span>
        <span class="ud-stat-value">{{ fmtRate(totals.success_rate) }}</span>
      </div>
    </div>

    <!-- Provider 维度表格 -->
    <div v-if="providerRows.length > 0" class="ud-table-wrap" role="table" aria-label="按 Provider 维度的调用统计">
      <div class="ud-row ud-row-head" role="row">
        <span class="ud-cell ud-c-name" role="columnheader">Provider</span>
        <span class="ud-cell ud-c-num" role="columnheader">调用</span>
        <span class="ud-cell ud-c-num" role="columnheader">成功率</span>
        <span class="ud-cell ud-c-num" role="columnheader">Token</span>
        <span class="ud-cell ud-c-num" role="columnheader">平均延迟</span>
        <span class="ud-cell ud-c-num" role="columnheader">最大延迟</span>
        <span class="ud-cell ud-c-name" role="columnheader">最近调用</span>
      </div>
      <div
        v-for="row in providerRows"
        :key="row.name"
        class="ud-row"
        role="row"
        :aria-label="`${row.name} 调用统计`"
      >
        <span class="ud-cell ud-c-name" role="rowheader" scope="row">{{ row.name }}</span>
        <span class="ud-cell ud-c-num" role="cell">{{ fmtNum(row.calls) }}</span>
        <span
          class="ud-cell ud-c-num"
          role="cell"
          :class="{
            'ud-rate-ok': row.success_rate >= 0.95,
            'ud-rate-warn': row.success_rate < 0.95 && row.success_rate >= 0.5,
            'ud-rate-bad': row.success_rate < 0.5,
          }"
        >{{ fmtRate(row.success_rate) }}</span>
        <span class="ud-cell ud-c-num" role="cell">{{ fmtTokens(row.tokens) }}</span>
        <span class="ud-cell ud-c-num" role="cell">{{ fmtLatency(row.latency_ms_avg) }}</span>
        <span class="ud-cell ud-c-num" role="cell">{{ fmtLatency(row.latency_ms_max) }}</span>
        <span
          class="ud-cell ud-c-name ud-c-last"
          role="cell"
          :title="row.last_error || '最近调用成功'"
        >{{ fmtRelativeTime(row.last_call_at) }}</span>
      </div>
    </div>

    <!-- 重置二次确认 -->
    <Transition name="modal">
      <div
        v-if="confirmingReset"
        class="ud-modal-mask"
        role="presentation"
        @click.self="cancelReset"
      >
        <div class="ud-modal" role="alertdialog" aria-modal="true" aria-label="清空用量统计">
          <h3 class="ud-modal-title">清空用量统计？</h3>
          <p class="ud-modal-desc">
            此操作将清空所有 Provider 的累计调用统计（调用次数 / Token / 延迟 / 错误记录）。
            进程级数据，不可恢复。
          </p>
          <div class="ud-modal-actions">
            <button type="button" class="btn-secondary" :disabled="resetting" @click="cancelReset">取消</button>
            <button type="button" class="btn-danger" :disabled="resetting" @click="confirmReset">
              {{ resetting ? '清空中…' : '确认清空' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.usage-dashboard {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}
.ud-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}
.ud-title {
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
}
.ud-h3 {
  font-size: 1rem;
  font-weight: 700;
  margin: 0;
}
.ud-uptime {
  font-size: 0.72rem;
  color: var(--muted-fg);
}
.ud-actions {
  display: flex;
  gap: 0.5rem;
}
.ud-error {
  margin: 0;
  padding: 0.5rem 0.75rem;
  font-size: 0.78rem;
  color: #dc2626;
  background: rgba(220, 38, 38, 0.08);
  border: 1px solid rgba(220, 38, 38, 0.3);
  border-radius: var(--radius-sm, 4px);
}
.ud-empty {
  padding: 1.25rem;
  text-align: center;
  font-size: 0.82rem;
  color: var(--muted-fg);
  border: 1px dashed var(--border);
  border-radius: var(--radius-md, 6px);
}

/* 汇总卡片 */
.ud-totals {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 0.6rem;
}
.ud-stat {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  padding: 0.6rem 0.75rem;
  background: var(--hover-bg, var(--bg));
  border: 1px solid var(--border);
  border-radius: var(--radius-sm, 4px);
}
.ud-stat-label {
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--muted-fg);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.ud-stat-value {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--fg);
  font-variant-numeric: tabular-nums;
}
.ud-stat-ok .ud-stat-value {
  color: #16a34a;
}
.ud-stat-err .ud-stat-value {
  color: #dc2626;
}

/* 表格 */
.ud-table-wrap {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm, 4px);
  overflow: hidden;
  font-size: 0.78rem;
}
.ud-row {
  display: grid;
  grid-template-columns: 1.5fr 0.8fr 0.9fr 1fr 1fr 1fr 1.2fr;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--border-light, var(--border));
  align-items: center;
}
.ud-row:last-child {
  border-bottom: none;
}
.ud-row-head {
  background: var(--hover-bg, var(--bg));
  font-weight: 600;
  color: var(--muted-fg);
  font-size: 0.72rem;
}
.ud-cell {
  font-variant-numeric: tabular-nums;
}
.ud-c-name {
  font-weight: 600;
}
.ud-c-num {
  text-align: right;
}
.ud-c-last {
  font-size: 0.72rem;
  color: var(--muted-fg);
  font-weight: 400;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ud-rate-ok { color: #16a34a; font-weight: 600; }
.ud-rate-warn { color: #d97706; font-weight: 600; }
.ud-rate-bad { color: #dc2626; font-weight: 600; }

/* 二次确认弹窗 */
.ud-modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}
.ud-modal {
  width: 420px;
  max-width: 92vw;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg, 8px);
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.ud-modal-title { margin: 0; font-size: 1rem; font-weight: 700; }
.ud-modal-desc { margin: 0; font-size: 0.82rem; color: var(--muted-fg); }
.ud-modal-actions { display: flex; justify-content: flex-end; gap: 0.5rem; }

.modal-enter-active,
.modal-leave-active { transition: opacity var(--duration-fast, 0.15s) var(--ease, ease); }
.modal-enter-from,
.modal-leave-to { opacity: 0; }

/* 通用按钮（与 SettingsView 一致） */
.btn-primary {
  padding: 0.4rem 0.8rem;
  font-size: 0.78rem;
  font-weight: 600;
  background: var(--fg);
  color: var(--bg);
  border: 1px solid var(--fg);
  border-radius: var(--radius-sm, 4px);
  cursor: pointer;
}
.btn-secondary {
  padding: 0.4rem 0.8rem;
  font-size: 0.78rem;
  font-weight: 600;
  background: transparent;
  color: var(--fg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm, 4px);
  cursor: pointer;
}
.btn-secondary:hover:not(:disabled) { border-color: var(--fg); }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-danger {
  padding: 0.4rem 0.8rem;
  font-size: 0.78rem;
  font-weight: 600;
  background: #dc2626;
  color: white;
  border: 1px solid #dc2626;
  border-radius: var(--radius-sm, 4px);
  cursor: pointer;
}
.btn-danger:hover:not(:disabled) { background: #b91c1c; }
.btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }

/* 小屏自适应：表格横向滚动 */
@media (max-width: 640px) {
  .ud-row {
    grid-template-columns: 1fr 0.7fr 0.8fr;
    font-size: 0.72rem;
  }
  .ud-row .ud-c-num:nth-child(4),
  .ud-row .ud-c-num:nth-child(5),
  .ud-row .ud-c-num:nth-child(6),
  .ud-row .ud-c-last {
    display: none;
  }
}
</style>
