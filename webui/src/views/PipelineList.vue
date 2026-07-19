<template>
  <div class="pipeline-list-view">
    <h1>📋 任务列表</h1>

    <div class="toolbar">
      <input v-model="search" placeholder="搜索任务..." class="search-input" @input="debouncedLoad" />
      <button class="btn-refresh" @click="loadPipelines">🔄 刷新</button>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <div v-else-if="pipelines.length === 0" class="empty">
      <p>暂无任务</p>
      <router-link to="/">去创建第一个任务 →</router-link>
    </div>

    <div v-else class="pipeline-cards">
      <div v-for="p in pipelines" :key="p.pipeline_id" class="pipeline-card">
        <div class="card-header">
          <span class="status-dot" :class="`status-${p.status}`"></span>
          <span class="card-title">{{ p.requirements_filename || p.pipeline_id }}</span>
          <span class="card-status">{{ statusLabel(p.status) }}</span>
        </div>
        <div class="card-meta">
          <span>模式: {{ p.mode || 'full' }}</span>
          <span>创建: {{ formatTime(p.created_at) }}</span>
          <span v-if="p.progress !== undefined">进度: {{ p.progress }}%</span>
        </div>
        <div class="card-actions">
          <button v-if="p.status === 'running'" class="btn-sm btn-cancel" @click="cancelPipeline(p.pipeline_id)">取消</button>
          <button v-if="p.status === 'paused'" class="btn-sm btn-resume" @click="resumePipeline(p.pipeline_id)">继续</button>
          <button v-if="p.status === 'done'" class="btn-sm btn-download" @click="downloadProject(p.pipeline_id)">📦 下载工程</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const pipelines = ref([])
const loading = ref(true)
const search = ref('')
let debounceTimer = null

function debouncedLoad() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(loadPipelines, 300)
}

async function loadPipelines() {
  loading.value = true
  try {
    const params = new URLSearchParams()
    if (search.value) params.set('q', search.value)
    const resp = await fetch(`/api/v1/pipeline/list?${params}`)
    const data = await resp.json()
    pipelines.value = data.pipelines || data.items || []
  } catch { /* ignore */ }
  loading.value = false
}

function statusLabel(s) {
  const map = { running: '运行中', done: '已完成', paused: '已暂停', error: '出错', cancelled: '已取消' }
  return map[s] || s
}

function formatTime(t) {
  if (!t) return '-'
  return new Date(t).toLocaleString('zh-CN')
}

async function cancelPipeline(id) {
  await fetch(`/api/v1/pipeline/${id}/cancel`, { method: 'POST' })
  loadPipelines()
}

async function resumePipeline(id) {
  await fetch(`/api/v1/pipeline/${id}/resume`, { method: 'POST' })
  loadPipelines()
}

async function downloadProject(id) {
  const resp = await fetch(`/api/v1/pipeline/${id}/export_pytest_project`)
  if (!resp.ok) return alert('下载失败')
  const blob = await resp.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `pytest_project_${id}.zip`
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(loadPipelines)
</script>

<style scoped>
.pipeline-list-view { max-width: 800px; margin: 0 auto; }
h1 { font-size: 24px; margin-bottom: 16px; }
.toolbar { display: flex; gap: 8px; margin-bottom: 16px; }
.search-input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
}
.search-input:focus { outline: none; border-color: #1a73e8; }
.btn-refresh {
  background: #f0f0f0;
  border: none;
  border-radius: 6px;
  padding: 8px 14px;
  cursor: pointer;
  font-size: 13px;
}
.btn-refresh:hover { background: #e0e0e0; }
.loading, .empty { text-align: center; padding: 40px; color: #999; }
.empty a { color: #1a73e8; }
.pipeline-cards { display: flex; flex-direction: column; gap: 12px; }
.pipeline-card {
  background: #fff;
  border-radius: 10px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.card-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; }
.status-running { background: #1a73e8; animation: pulse 1.5s infinite; }
.status-done { background: #188038; }
.status-paused { background: #f9ab00; }
.status-error { background: #d93025; }
.status-cancelled { background: #999; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.card-title { font-weight: 500; font-size: 14px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.card-status { font-size: 12px; color: #666; }
.card-meta { display: flex; gap: 16px; font-size: 12px; color: #888; margin-bottom: 8px; }
.card-actions { display: flex; gap: 8px; }
.btn-sm {
  padding: 4px 12px;
  border: none;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
}
.btn-cancel { background: #fce8e6; color: #d93025; }
.btn-resume { background: #fef7e0; color: #f9ab00; }
.btn-download { background: #e6f4ea; color: #188038; }
</style>
