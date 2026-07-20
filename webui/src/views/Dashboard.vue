<template>
  <div class="dashboard">
    <PageHeader title="仪表盘" subtitle="系统概览与快速操作" />

    <!-- System status panel -->
    <section class="health-panel" aria-label="系统健康状态">
      <div class="health-panel__header">
        <div class="health-panel__heading">
          <h2 class="health-panel__title">系统状态</h2>
          <span class="health-summary" :class="`health-summary--${overallState}`">
            <span class="health-summary__dot" aria-hidden="true"></span>
            {{ overallLabel }}
          </span>
        </div>
        <div class="health-panel__meta">
          <span v-if="healthUpdated" class="health-panel__time tabular-nums">检查于 {{ formatClock(healthUpdated) }}</span>
          <button
            class="health-refresh"
            :disabled="healthLoading"
            :title="healthLoading ? '检查中…' : '刷新健康检查'"
            :aria-label="healthLoading ? '检查中' : '刷新健康检查'"
            @click="loadHealth"
          >
            <svg class="health-refresh__icon" :class="{ 'health-refresh__icon--spin': healthLoading }" viewBox="0 0 20 20" width="14" height="14" aria-hidden="true">
              <path fill="currentColor" d="M10 3a7 7 0 0 1 6.3 4H14a1 1 0 1 0 0 2h4a1 1 0 0 0 1-1V4a1 1 0 1 0-2 0v1.5A9 9 0 1 0 19 10a1 1 0 1 0-2 0 7 7 0 1 1-7-7z"/>
            </svg>
          </button>
        </div>
      </div>

      <div v-if="healthItems.length === 0" class="health-grid">
        <div v-for="i in 4" :key="i" class="health-card health-card--skeleton" aria-hidden="true">
          <div class="health-card__icon"></div>
          <div class="health-card__body">
            <div class="skeleton-line skeleton-line--name"></div>
            <div class="skeleton-line skeleton-line--desc"></div>
          </div>
        </div>
      </div>
      <div v-else class="health-grid">
        <div
          v-for="(c, idx) in healthItems"
          :key="c.key"
          class="health-card"
          :class="`health-card--${c.state}`"
          :style="{ animationDelay: `${idx * 60}ms` }"
        >
          <div class="health-card__icon" :class="`health-card__icon--${c.state}`">
            <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true" v-html="c.icon"></svg>
          </div>
          <div class="health-card__body">
            <div class="health-card__name">{{ c.label }}</div>
            <div class="health-card__desc">{{ c.desc }}</div>
          </div>
          <span class="health-badge" :class="`health-badge--${c.state}`">
            <span class="health-badge__dot" aria-hidden="true"></span>
            {{ c.stateLabel }}
          </span>
        </div>
      </div>
    </section>

    <!-- Stats -->
    <section class="stats-row" aria-label="任务统计">
      <StatCard :value="stats.running" label="运行中" />
      <StatCard :value="stats.done" label="已完成" />
      <StatCard :value="stats.total" label="总任务" />
      <StatCard :value="kbTotal" label="知识库条目" />
    </section>

    <!-- Recent tasks -->
    <section class="recent-section" aria-label="最近任务">
      <div class="section-header">
        <h2 class="section-title">最近任务</h2>
        <router-link to="/pipelines" class="section-link">查看全部 →</router-link>
      </div>
      <div v-if="recentLoading" class="loading-hint" role="status">加载中…</div>
      <div v-else-if="loadError" class="error-hint" role="alert">{{ loadError }} · <button class="link-btn" @click="loadStats()">重试</button></div>
      <EmptyState v-else-if="recentTasks.length === 0" message="暂无任务">
        <router-link to="/pipeline/new" class="btn-primary">创建第一个任务</router-link>
      </EmptyState>
      <table v-else class="task-table" aria-label="最近任务列表">
        <thead>
          <tr>
            <th scope="col">状态</th>
            <th scope="col">文件</th>
            <th scope="col">模式</th>
            <th scope="col">进度</th>
            <th scope="col">创建时间</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="t in recentTasks"
            :key="t.pipeline_id"
            class="task-row"
            @click="$router.push(`/pipeline/${t.pipeline_id}`)"
          >
            <td><StatusBadge :status="t.status" /></td>
            <td class="task-row__file">{{ t.requirements || t.pipeline_id }}</td>
            <td>{{ t.mode || '—' }}</td>
            <td class="tabular-nums">{{ t.total_steps ? Math.round((t.completed_steps / t.total_steps) * 100) + '%' : '—' }}</td>
            <td class="tabular-nums">{{ formatTime(t.started_at) }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- Quick start -->
    <section class="quick-start" aria-label="快速启动">
      <h2 class="section-title">快速启动</h2>
      <FileDropZone
        accept=".md,.txt"
        hint="支持 .md / .txt，最大 10 MB"
        label="上传需求文档快速启动"
        @file="quickStart"
      />
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import StatCard from '../components/StatCard.vue'
import StatusBadge from '../components/StatusBadge.vue'
import EmptyState from '../components/EmptyState.vue'
import FileDropZone from '../components/FileDropZone.vue'
import { api } from '../composables/useApi'
import { useToast } from '../composables/useToast'

const toast = useToast()

const router = useRouter()

const healthChecks = ref(null)
const healthLoading = ref(false)
const healthUpdated = ref(null)
const stats = ref({ running: 0, done: 0, total: 0, other: 0 })
const kbTotal = ref(0)
const recentTasks = ref([])
const recentLoading = ref(true)
const loadError = ref('')

// ─── 健康检查组件元数据 ───
const HEALTH_META = {
  api: {
    label: 'API 服务',
    icon: '<path fill="currentColor" d="M11 3a1 1 0 1 0-2 0v1.06A8 8 0 0 0 2.06 11H1a1 1 0 1 0 0 2h1.06A8 8 0 0 0 9 19.94V21a1 1 0 1 0 2 0v-1.06A8 8 0 0 0 17.94 13H19a1 1 0 1 0 0-2h-1.06A8 8 0 0 0 11 4.06V3zM10 6a6 6 0 0 1 5.92 5H13a1 1 0 0 0-.9.56l-1.4 2.8-1.32-3.97A1 1 0 0 0 8.43 10H4.08A6 6 0 0 1 10 6z"/>',
    desc: { ok: 'FastAPI 运行中', warn: '响应异常', error: '服务异常' },
  },
  database: {
    label: '数据库',
    icon: '<path fill="currentColor" d="M10 2c4.4 0 8 1.1 8 2.5S14.4 7 10 7 2 5.9 2 4.5 5.6 2 10 2zm8 4.5v9c0 1.4-3.6 2.5-8 2.5s-8-1.1-8-2.5v-9C2 7.9 5.6 9 10 9s8-1.1 8-2.5zM4 9.7v4.8c1.2.6 3.4 1 6 1s4.8-.4 6-1V9.7c-1.2.6-3.4 1-6 1s-4.8-.4-6-1z"/>',
    desc: { ok: 'SQLite 连接正常', warn: '连接异常', error: '连接失败' },
  },
  llm: {
    label: 'LLM 模型',
    icon: '<path fill="currentColor" d="M10 2a4 4 0 0 1 4 4v1h1a3 3 0 0 1 3 3v4a3 3 0 0 1-3 3h-1.28A4 4 0 0 1 10 19a4 4 0 0 1-3.72-2H5a3 3 0 0 1-3-3v-4a3 3 0 0 1 3-3h1V6a4 4 0 0 1 4-4zm0 2a2 2 0 0 0-2 2v2h4V6a2 2 0 0 0-2-2zM7 11a1 1 0 1 0 0 2 1 1 0 0 0 0-2zm6 0a1 1 0 1 0 0 2 1 1 0 0 0 0-2z"/>',
    desc: { ok: '模型配置就绪', not_configured: '未配置 API Key', warn: '配置异常', error: '配置读取失败' },
  },
  knowledge_base: {
    label: '知识库',
    icon: '<path fill="currentColor" d="M4 2a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H4zm2 4h8a1 1 0 0 1 0 2H6a1 1 0 0 1 0-2zm0 4h5a1 1 0 0 1 0 2H6a1 1 0 0 1 0-2z"/>',
    desc: { ok: 'Vault 已连接', disabled: '未启用', warn: 'Vault 异常', error: '检测失败' },
  },
}

function stateOf(val) {
  if (val === 'ok' || val === 'disabled' || val === 'not_configured') return 'ok'
  if (typeof val === 'string' && val.startsWith('error')) return 'error'
  return 'warn'
}

const healthItems = computed(() => {
  if (!healthChecks.value) return []
  return Object.entries(healthChecks.value).map(([key, val]) => {
    const meta = HEALTH_META[key] || { label: key, icon: '', desc: {} }
    const state = stateOf(val)
    return {
      key,
      label: meta.label,
      icon: meta.icon,
      state,
      stateLabel: state === 'ok' ? '正常' : state === 'warn' ? '警告' : '异常',
      desc: (state === 'ok' && meta.desc[val]) || meta.desc[state] || String(val),
    }
  })
})

const overallState = computed(() => {
  if (!healthChecks.value) return 'checking'
  const states = healthItems.value.map((c) => c.state)
  if (states.some((s) => s === 'error')) return 'error'
  if (states.some((s) => s === 'warn')) return 'warn'
  return 'ok'
})

const overallLabel = computed(() =>
  ({ ok: '全部正常', warn: '部分降级', error: '存在异常', checking: '检测中…' })[overallState.value]
)

function formatClock(t) {
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  }).format(t)
}

function formatTime(t) {
  if (!t) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  }).format(new Date(t))
}

async function loadHealth() {
  healthLoading.value = true
  try {
    const resp = await fetch('/health')
    const data = await resp.json()
    healthChecks.value = data.checks || {}
    healthUpdated.value = new Date()
  } catch {
    healthChecks.value = { api: 'error' }
    healthUpdated.value = new Date()
  } finally {
    healthLoading.value = false
  }
}

async function loadStats() {
  try {
    const data = await api.get('/pipeline/list?page_size=5')
    stats.value = data.all_stats || stats.value
    recentTasks.value = data.items || data.pipelines || []
  } catch (e) { loadError.value = '任务数据加载失败' }
  recentLoading.value = false
}

async function loadKb() {
  try {
    const data = await api.get('/knowledge/status')
    kbTotal.value = data.total || 0
  } catch { /* KB 非关键，静默降级 */ }
}

async function quickStart(file) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('mode', 'semi')
  formData.append('dimensions', 'positive,negative,boundary,exception')
  formData.append('formats', 'excel,json')
  try {
    const data = await api.upload('/pipeline/start', formData)
    toast.success('任务已启动')
    router.push(`/pipeline/${data.pipeline_id}`)
  } catch (e) {
    toast.error(`启动失败: ${e.message}`)
  }
}

onMounted(() => {
  loadHealth()
  loadStats()
  loadKb()
})
</script>

<style scoped>
.dashboard {
  max-width: var(--content-max-width);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-xl);
}

/* ─── System status panel ─── */
.health-panel {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: var(--space-lg);
  margin-bottom: var(--space-xl);
  box-shadow: var(--shadow-sm);
}

.health-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
  margin-bottom: var(--space-lg);
}

.health-panel__heading {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.health-panel__title {
  font-size: var(--text-lg);
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.01em;
}

.health-panel__meta {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.health-panel__time {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}

/* Overall status pill */
.health-summary {
  display: inline-flex;
  align-items: center;
  gap: var(--space-xs);
  padding: 3px var(--space-md);
  border-radius: var(--radius-full, 999px);
  font-size: var(--text-xs);
  font-weight: 600;
  line-height: 1.6;
}
.health-summary__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}
.health-summary--ok {
  color: var(--feedback-success-text);
  background: var(--feedback-success-bg);
}
.health-summary--warn {
  color: var(--feedback-warn-text);
  background: var(--feedback-warn-bg);
}
.health-summary--error {
  color: var(--feedback-error-text);
  background: var(--feedback-error-bg);
}
.health-summary--checking {
  color: var(--text-tertiary);
  background: var(--bg-inset);
}
.health-summary--ok .health-summary__dot { animation: health-pulse 2s var(--ease-out) infinite; }

/* Refresh button */
.health-refresh {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out),
              color var(--duration-fast) var(--ease-out),
              border-color var(--duration-fast) var(--ease-out);
}
.health-refresh:hover:not(:disabled) {
  background: var(--bg-inset);
  color: var(--accent);
  border-color: var(--border-strong);
}
.health-refresh:disabled {
  cursor: wait;
  opacity: 0.6;
}
.health-refresh__icon--spin {
  animation: health-spin 0.9s linear infinite;
}

/* Component cards grid */
.health-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-md);
}

.health-card {
  display: flex;
  align-items: flex-start;
  gap: var(--space-md);
  padding: var(--space-md);
  background: var(--bg-surface-raised);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  animation: health-rise 0.4s var(--ease-out) both;
  transition: transform var(--duration-fast) var(--ease-out),
              border-color var(--duration-fast) var(--ease-out),
              box-shadow var(--duration-fast) var(--ease-out);
}
.health-card:hover {
  transform: translateY(-2px);
  border-color: var(--border-strong);
  box-shadow: var(--shadow-md);
}

.health-card__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  border-radius: var(--radius-md);
}
.health-card__icon--ok {
  color: var(--accent);
  background: var(--accent-subtle);
}
.health-card__icon--warn {
  color: var(--feedback-warn-text);
  background: var(--feedback-warn-bg);
}
.health-card__icon--error {
  color: var(--feedback-error-text);
  background: var(--feedback-error-bg);
}

.health-card__body {
  flex: 1;
  min-width: 0;
}

.health-card__name {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 2px;
}

.health-card__desc {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Status badge */
.health-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  flex-shrink: 0;
  padding: 2px var(--space-sm);
  border-radius: var(--radius-full, 999px);
  font-size: 11px;
  font-weight: 600;
  line-height: 1.6;
}
.health-badge__dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}
.health-badge--ok {
  color: var(--feedback-success-text);
  background: var(--feedback-success-bg);
}
.health-badge--ok .health-badge__dot { animation: health-pulse 2s var(--ease-out) infinite; }
.health-badge--warn {
  color: var(--feedback-warn-text);
  background: var(--feedback-warn-bg);
}
.health-badge--error {
  color: var(--feedback-error-text);
  background: var(--feedback-error-bg);
}
.health-badge--error .health-badge__dot { animation: health-pulse 1s var(--ease-out) infinite; }

/* Skeleton loading */
.health-card--skeleton {
  animation: none;
  pointer-events: none;
}
.health-card--skeleton .health-card__icon {
  background: var(--bg-inset);
}
.skeleton-line {
  border-radius: var(--radius-sm);
  background: linear-gradient(90deg, var(--bg-inset) 25%, var(--border-default) 50%, var(--bg-inset) 75%);
  background-size: 200% 100%;
  animation: health-shimmer 1.4s linear infinite;
}
.skeleton-line--name { height: 12px; width: 60%; margin-bottom: 6px; }
.skeleton-line--desc { height: 10px; width: 85%; }

@keyframes health-rise {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes health-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}
@keyframes health-spin {
  to { transform: rotate(360deg); }
}
@keyframes health-shimmer {
  to { background-position: -200% 0; }
}

@media (max-width: 1100px) {
  .health-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 640px) {
  .health-grid { grid-template-columns: 1fr; }
  .health-panel__header { flex-direction: column; align-items: flex-start; }
}

/* Stats */
.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: var(--space-md);
}

/* Section */
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-md);
}
.section-title {
  font-size: var(--text-lg);
  font-weight: 600;
}
.section-link {
  font-size: var(--text-sm);
  color: var(--accent);
}

.loading-hint {
  text-align: center;
  padding: var(--space-xl);
  color: var(--text-tertiary);
}
.error-hint {
  text-align: center;
  padding: var(--space-xl);
  color: var(--feedback-error-text);
  background: var(--feedback-error-bg);
  border-radius: var(--radius-md);
}
.link-btn {
  background: none;
  border: none;
  color: var(--accent);
  cursor: pointer;
  font: inherit;
  text-decoration: underline;
  padding: 0;
}
.link-btn:hover { opacity: 0.8; }

/* Task table */
.task-table {
  font-size: var(--text-sm);
}
.task-table th {
  text-align: left;
  padding: var(--space-sm) var(--space-md);
  color: var(--text-tertiary);
  font-weight: 500;
  font-size: var(--text-xs);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--border-default);
}
.task-table td {
  padding: var(--space-sm) var(--space-md);
  border-bottom: 1px solid var(--border-default);
}
.task-row {
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out);
}
.task-row:hover {
  background: var(--bg-inset);
}
.task-row__file {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Quick start */
.quick-start {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.btn-primary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-sm) var(--space-xl);
  background: var(--accent);
  color: var(--accent-text);
  border: none;
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  font-weight: 500;
  text-decoration: none;
  margin-top: var(--space-md);
  transition: background var(--duration-fast) var(--ease-out);
}
.btn-primary:hover {
  background: var(--accent-hover);
  text-decoration: none;
}
</style>
