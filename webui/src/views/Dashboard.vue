<template>
  <div class="dashboard">
    <PageHeader title="仪表盘" subtitle="系统概览与快速操作" />

    <!-- Health bar -->
    <section class="health-bar" aria-label="系统健康状态">
      <div v-for="(val, key) in healthChecks" :key="key" class="health-bar__item">
        <span class="health-bar__dot" :class="dotClass(val)" aria-hidden="true"></span>
        <span class="health-bar__label">{{ key }}</span>
        <span class="health-bar__val">{{ val }}</span>
      </div>
      <div v-if="!healthChecks" class="health-bar__item">
        <span class="health-bar__dot health-bar__dot--unknown" aria-hidden="true"></span>
        <span class="health-bar__label">检测中…</span>
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
      <EmptyState v-else-if="recentTasks.length === 0" message="暂无任务">
        <router-link to="/pipeline/new" class="btn-primary">创建第一个任务</router-link>
      </EmptyState>
      <table v-else class="task-table">
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
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import StatCard from '../components/StatCard.vue'
import StatusBadge from '../components/StatusBadge.vue'
import EmptyState from '../components/EmptyState.vue'
import FileDropZone from '../components/FileDropZone.vue'
import { api } from '../composables/useApi'

const router = useRouter()

const healthChecks = ref(null)
const stats = ref({ running: 0, done: 0, total: 0, other: 0 })
const kbTotal = ref(0)
const recentTasks = ref([])
const recentLoading = ref(true)

function dotClass(val) {
  if (val === 'ok' || val === 'disabled' || val === 'not_configured') return 'health-bar__dot--ok'
  if (val?.startsWith?.('error')) return 'health-bar__dot--error'
  return 'health-bar__dot--warn'
}

function formatTime(t) {
  if (!t) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  }).format(new Date(t))
}

async function loadHealth() {
  try {
    const resp = await fetch('/health')
    const data = await resp.json()
    healthChecks.value = data.checks || {}
  } catch { healthChecks.value = { api: 'error' } }
}

async function loadStats() {
  try {
    const data = await api.get('/pipeline/list?page_size=5')
    stats.value = data.all_stats || stats.value
    recentTasks.value = data.items || data.pipelines || []
  } catch { /* ignore */ }
  recentLoading.value = false
}

async function loadKb() {
  try {
    const data = await api.get('/knowledge/status')
    kbTotal.value = data.total || 0
  } catch { /* ignore */ }
}

async function quickStart(file) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('mode', 'semi')
  formData.append('dimensions', 'functional,api,security')
  formData.append('formats', 'excel,json')
  try {
    const data = await api.upload('/pipeline/start', formData)
    router.push(`/pipeline/${data.pipeline_id}`)
  } catch (e) {
    alert(`启动失败: ${e.message}`)
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

/* Health bar */
.health-bar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-lg);
  padding: var(--space-md) var(--space-lg);
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
}

.health-bar__item {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  font-size: var(--text-sm);
}

.health-bar__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.health-bar__dot--ok { background: var(--status-done); }
.health-bar__dot--warn { background: var(--status-paused); }
.health-bar__dot--error { background: var(--status-error); }
.health-bar__dot--unknown { background: var(--text-tertiary); }

.health-bar__label {
  color: var(--text-secondary);
  text-transform: capitalize;
}
.health-bar__val {
  color: var(--text-tertiary);
  font-size: var(--text-xs);
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
