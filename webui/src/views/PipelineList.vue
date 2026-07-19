<template>
  <div class="pipeline-list">
    <PageHeader title="任务列表" subtitle="所有 Pipeline 任务" />

    <!-- Stats bar -->
    <div class="stats-bar" aria-label="任务统计">
      <button
        v-for="s in statTabs"
        :key="s.value"
        class="stats-bar__tab"
        :class="{ 'stats-bar__tab--active': statusFilter === s.value }"
        @click="setStatus(s.value)"
      >
        {{ s.label }}
        <span class="stats-bar__count tabular-nums">{{ s.count }}</span>
      </button>
    </div>

    <!-- Toolbar -->
    <div class="toolbar">
      <input
        v-model="keyword"
        type="search"
        class="toolbar__search"
        placeholder="搜索文件名或 ID…"
        aria-label="搜索任务"
        spellcheck="false"
        autocomplete="off"
        @input="debouncedLoad"
      />
      <button class="toolbar__refresh" aria-label="刷新列表" @click="loadList">
        <svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M10 3a7 7 0 0 0-6.3 4H1l3.5 4L8 7H5.8A5 5 0 1 1 10 15a5 5 0 0 1-4.5-2.8l-1.8 1A7 7 0 1 0 10 3z"/></svg>
      </button>
    </div>

    <!-- Table -->
    <div v-if="loading" class="loading-state" role="status">加载中…</div>
    <EmptyState v-else-if="items.length === 0" message="暂无匹配任务">
      <router-link to="/pipeline/new" class="link-accent">创建新任务 →</router-link>
    </EmptyState>
    <table v-else class="list-table">
      <thead>
        <tr>
          <th scope="col">状态</th>
          <th scope="col">文件</th>
          <th scope="col">模式</th>
          <th scope="col">进度</th>
          <th scope="col">创建时间</th>
          <th scope="col">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="t in items" :key="t.pipeline_id" class="list-row">
          <td><StatusBadge :status="t.status" /></td>
          <td class="list-row__file">
            <router-link :to="`/pipeline/${t.pipeline_id}`" class="file-link">
              {{ t.requirements || t.pipeline_id }}
            </router-link>
          </td>
          <td>{{ t.mode || '—' }}</td>
          <td class="tabular-nums">{{ t.total_steps ? Math.round((t.completed_steps / t.total_steps) * 100) + '%' : '—' }}</td>
          <td class="tabular-nums">{{ formatTime(t.started_at) }}</td>
          <td class="list-row__actions">
            <button
              v-if="t.status === 'running' || t.status === 'pending'"
              class="btn-sm btn-sm--danger"
              :aria-label="`取消 ${t.pipeline_id}`"
              @click.stop="cancelTask(t.pipeline_id)"
            >取消</button>
            <button
              v-if="t.status === 'paused'"
              class="btn-sm btn-sm--warn"
              :aria-label="`继续 ${t.pipeline_id}`"
              @click.stop="resumeTask(t.pipeline_id)"
            >继续</button>
            <button
              v-if="t.status === 'done'"
              class="btn-sm btn-sm--ok"
              :aria-label="`下载 ${t.pipeline_id}`"
              @click.stop="downloadZip(t.pipeline_id)"
            >下载</button>
          </td>
        </tr>
      </tbody>
    </table>

    <Pagination :page="page" :pages="pages" @change="goPage" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import StatusBadge from '../components/StatusBadge.vue'
import EmptyState from '../components/EmptyState.vue'
import Pagination from '../components/Pagination.vue'
import { api } from '../composables/useApi'
import { usePolling } from '../composables/usePolling'

const route = useRoute()
const router = useRouter()

const items = ref([])
const loading = ref(true)
const keyword = ref(route.query.q || '')
const statusFilter = ref(route.query.status || '')
const page = ref(parseInt(route.query.page) || 1)
const pages = ref(1)
const allStats = ref({ total: 0, running: 0, done: 0, other: 0 })

let debounceTimer = null

const statTabs = computed(() => [
  { label: '全部', value: '', count: allStats.value.total },
  { label: '运行中', value: 'running', count: allStats.value.running },
  { label: '已完成', value: 'done', count: allStats.value.done },
  { label: '其他', value: 'other', count: allStats.value.other },
])

function formatTime(t) {
  if (!t) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  }).format(new Date(t))
}

function syncUrl() {
  const q = {}
  if (keyword.value) q.q = keyword.value
  if (statusFilter.value) q.status = statusFilter.value
  if (page.value > 1) q.page = page.value
  router.replace({ query: q })
}

async function loadList() {
  loading.value = true
  try {
    const params = new URLSearchParams()
    params.set('page', page.value)
    params.set('page_size', '20')
    if (keyword.value) params.set('keyword', keyword.value)
    if (statusFilter.value && statusFilter.value !== 'other') params.set('status', statusFilter.value)
    const data = await api.get(`/pipeline/list?${params}`)
    items.value = data.items || data.pipelines || []
    pages.value = data.pages || 1
    allStats.value = data.all_stats || allStats.value

    // "其他" 筛选在前端做
    if (statusFilter.value === 'other') {
      items.value = items.value.filter(t => !['running', 'pending', 'done'].includes(t.status))
    }
  } catch { /* ignore */ }
  loading.value = false
}

function debouncedLoad() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    page.value = 1
    syncUrl()
    loadList()
  }, 300)
}

function setStatus(val) {
  statusFilter.value = val
  page.value = 1
  syncUrl()
  loadList()
}

function goPage(p) {
  page.value = p
  syncUrl()
  loadList()
}

async function cancelTask(id) {
  if (!confirm('确定取消？')) return
  try {
    await api.post(`/pipeline/${id}/cancel`)
    loadList()
  } catch (e) { alert(`取消失败: ${e.message}`) }
}

async function resumeTask(id) {
  try {
    await api.post(`/pipeline/${id}/resume`)
    loadList()
  } catch (e) { alert(`继续失败: ${e.message}`) }
}

async function downloadZip(id) {
  try {
    const blob = await api.download(`/pipeline/${id}/export_pytest_project`)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `pytest_project_${id}.zip`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) { alert(`下载失败: ${e.message}`) }
}

// Auto-refresh when running tasks exist
const { start: startPolling, stop: stopPolling } = usePolling(
  loadList,
  5000,
  { immediate: false, stopWhen: () => allStats.value.running === 0 }
)

onMounted(async () => {
  await loadList()
  if (allStats.value.running > 0) startPolling()
})

onUnmounted(() => stopPolling())
</script>

<style scoped>
.pipeline-list {
  max-width: var(--content-max-width);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
}

/* Stats bar */
.stats-bar {
  display: flex;
  gap: var(--space-xs);
  flex-wrap: wrap;
}
.stats-bar__tab {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  padding: var(--space-xs) var(--space-md);
  border: 1px solid var(--border-default);
  border-radius: 999px;
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  transition: background var(--duration-fast) var(--ease-out),
              color var(--duration-fast) var(--ease-out);
}
.stats-bar__tab:hover { background: var(--bg-inset); }
.stats-bar__tab--active {
  background: var(--accent-subtle);
  color: var(--accent);
  border-color: var(--accent);
}
.stats-bar__count {
  font-size: var(--text-xs);
  opacity: 0.7;
}

/* Toolbar */
.toolbar {
  display: flex;
  gap: var(--space-sm);
}
.toolbar__search {
  flex: 1;
  padding: var(--space-sm) var(--space-md);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: var(--text-base);
  transition: border-color var(--duration-fast) var(--ease-out);
}
.toolbar__search:focus {
  border-color: var(--accent);
  outline: none;
}
.toolbar__search::placeholder { color: var(--text-tertiary); }

.toolbar__refresh {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-secondary);
  transition: background var(--duration-fast) var(--ease-out);
}
.toolbar__refresh:hover { background: var(--bg-inset); }

.loading-state {
  text-align: center;
  padding: var(--space-2xl);
  color: var(--text-tertiary);
}

.link-accent { color: var(--accent); font-size: var(--text-sm); }

/* Table */
.list-table {
  font-size: var(--text-sm);
}
.list-table th {
  text-align: left;
  padding: var(--space-sm) var(--space-md);
  color: var(--text-tertiary);
  font-weight: 500;
  font-size: var(--text-xs);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--border-default);
}
.list-table td {
  padding: var(--space-sm) var(--space-md);
  border-bottom: 1px solid var(--border-default);
  vertical-align: middle;
}

.list-row__file {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-link {
  color: var(--text-primary);
  text-decoration: none;
}
.file-link:hover { color: var(--accent); text-decoration: underline; }

.list-row__actions {
  display: flex;
  gap: var(--space-xs);
}

.btn-sm {
  padding: 2px 10px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  background: transparent;
  font-size: var(--text-xs);
  color: var(--text-secondary);
  transition: background var(--duration-fast) var(--ease-out),
              color var(--duration-fast) var(--ease-out);
}
.btn-sm:hover { background: var(--bg-inset); }
.btn-sm--danger:hover { background: var(--feedback-error-bg); color: var(--feedback-error-text); }
.btn-sm--warn:hover { background: var(--feedback-warn-bg); color: var(--feedback-warn-text); }
.btn-sm--ok:hover { background: var(--feedback-success-bg); color: var(--feedback-success-text); }
</style>
