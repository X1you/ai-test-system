<template>
  <div class="pipeline-detail">
    <PageHeader
      :title="filename"
      :subtitle="`Pipeline ${id}`"
      back-to="/pipelines"
    >
      <template #actions>
        <StatusBadge v-if="progress" :status="progress.status" />
        <button
          v-if="progress?.status === 'running' || progress?.status === 'pending'"
          class="btn-action btn-action--danger"
          @click="confirmCancel"
        >取消</button>
        <button
          v-if="progress?.status === 'paused' || progress?.status === 'interrupted'"
          class="btn-action btn-action--accent"
          @click="resume"
        >继续执行</button>
      </template>
    </PageHeader>

    <div v-if="loading" class="loading-state" role="status">加载中…</div>
    <div v-else-if="notFound" class="error-state" role="alert">任务不存在</div>

    <template v-else-if="progress">
      <!-- Step progress -->
      <section class="detail-section" aria-label="步骤进度">
        <StepProgress :steps="progress.steps || []" />
        <div class="progress-bar-row">
          <div class="progress-bar" role="progressbar" :aria-valuenow="progress.percent" aria-valuemin="0" aria-valuemax="100">
            <div class="progress-bar__fill" :style="{ width: progress.percent + '%' }"></div>
          </div>
          <span class="progress-pct tabular-nums">{{ progress.percent }}%</span>
        </div>
      </section>

      <!-- Main content: logs + artifacts -->
      <div class="detail-columns">
        <!-- Logs -->
        <section class="detail-section detail-section--logs" aria-label="执行日志">
          <h2 class="detail-section__title">
            实时日志
            <span v-if="sseConnected" class="sse-badge">SSE</span>
            <span v-else-if="sseFallback" class="sse-badge sse-badge--fallback">轮询</span>
          </h2>
          <LogPanel :logs="progress.logs || []" />
        </section>

        <!-- Artifacts -->
        <section class="detail-section detail-section--artifacts" aria-label="产物">
          <ArtifactList
            :artifacts="artifacts"
            :show-export="progress.status === 'done'"
            @preview="openPreview"
            @download="downloadArtifact"
            @export="exportProject"
          />
        </section>
      </div>

      <!-- LLM stats -->
      <section v-if="progress.llm_stats && Object.keys(progress.llm_stats).length" class="detail-section" aria-label="LLM 统计">
        <h2 class="detail-section__title">LLM 统计</h2>
        <div class="llm-stats">
          <span v-for="(val, key) in progress.llm_stats" :key="key" class="llm-stat">
            <strong>{{ key }}:</strong> {{ val }}
          </span>
        </div>
      </section>

      <!-- Error -->
      <div v-if="progress.error" class="error-banner" role="alert">
        {{ progress.error }}
      </div>
    </template>

    <!-- Preview modal -->
    <ArtifactPreview
      :open="previewOpen"
      :title="previewTitle"
      :pipeline-id="id"
      :artifact-name="previewName"
      @close="previewOpen = false"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import StatusBadge from '../components/StatusBadge.vue'
import StepProgress from '../components/StepProgress.vue'
import LogPanel from '../components/LogPanel.vue'
import ArtifactList from '../components/ArtifactList.vue'
import ArtifactPreview from '../components/ArtifactPreview.vue'
import { useSSE } from '../composables/useSSE'
import { api } from '../composables/useApi'
import { useToast } from '../composables/useToast'

const toast = useToast()

const route = useRoute()
const id = route.params.id

const loading = ref(true)
const notFound = ref(false)
const progress = ref(null)
const artifacts = ref([])

const filename = computed(() =>
  progress.value?.requirements || progress.value?.requirements_filename || id
)

// SSE
const { connected: sseConnected, usingFallback: sseFallback, connect: sseConnect, close: sseClose } = useSSE(id, {
  onStepDone() { refreshProgress(); loadArtifacts() },
  onLog(data) {
    if (progress.value && data.ts && data.msg) {
      progress.value.logs = [...(progress.value.logs || []), data].slice(-200)
    }
  },
  onTerminal(evt, data) {
    refreshProgress()
    loadArtifacts()
  },
  onPoll(data) {
    progress.value = data
  },
})

async function refreshProgress() {
  try {
    const data = await api.get(`/pipeline/${id}/progress`)
    progress.value = data
    notFound.value = false
  } catch (e) {
    if (e.status === 404) notFound.value = true
  }
  loading.value = false
}

async function loadArtifacts() {
  try {
    const data = await api.get(`/pipeline/${id}/artifacts`)
    artifacts.value = data.artifacts || []
  } catch { /* ignore */ }
}

async function confirmCancel() {
  if (!confirm('确定要取消此任务？')) return
  try {
    await api.post(`/pipeline/${id}/cancel`)
    toast.success('任务已取消')
    refreshProgress()
  } catch (e) {
    toast.error(`取消失败: ${e.message}`)
  }
}

async function resume() {
  try {
    await api.post(`/pipeline/${id}/resume`)
    toast.success('任务已继续')
    refreshProgress()
    sseConnect()
  } catch (e) {
    toast.error(`继续失败: ${e.message}`)
  }
}

// Preview
const previewOpen = ref(false)
const previewName = ref('')
const previewTitle = ref('')

function openPreview(a) {
  previewName.value = a.name
  previewTitle.value = a.display_name
  previewOpen.value = true
}

async function downloadArtifact(a) {
  try {
    const blob = await api.download(`/pipeline/${id}/artifacts/${a.name}`)
    triggerDownload(blob, a.name)
    toast.success('下载已开始')
  } catch (e) {
    toast.error(`下载失败: ${e.message}`)
  }
}

async function exportProject() {
  try {
    const blob = await api.download(`/pipeline/${id}/export_pytest_project`)
    triggerDownload(blob, `pytest_project_${id}.zip`)
    toast.success('导出已开始')
  } catch (e) {
    toast.error(`导出失败: ${e.message}`)
  }
}

function triggerDownload(blob, name) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(async () => {
  await refreshProgress()
  await loadArtifacts()
  // 非终态时启动 SSE
  if (progress.value && !['done', 'error', 'cancelled'].includes(progress.value.status)) {
    sseConnect()
  }
})

onUnmounted(() => sseClose())
</script>

<style scoped>
.pipeline-detail {
  max-width: var(--content-max-width);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-xl);
}

.loading-state,
.error-state {
  text-align: center;
  padding: var(--space-3xl);
  color: var(--text-tertiary);
}
.error-state { color: var(--feedback-error-text); }

.detail-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.detail-section__title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.sse-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 999px;
  background: var(--feedback-success-bg);
  color: var(--feedback-success-text);
  font-weight: 500;
}
[data-theme="dark"] .sse-badge {
  background: hsl(150 50% 10%);
  color: hsl(150 80% 55%);
  box-shadow: 0 0 4px hsl(150 100% 50% / 0.2);
}
.sse-badge--fallback {
  background: var(--feedback-warn-bg);
  color: var(--feedback-warn-text);
}

/* Progress bar */
.progress-bar-row {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}
.progress-bar {
  flex: 1;
  height: 6px;
  background: var(--bg-inset);
  border-radius: 3px;
  overflow: hidden;
}
.progress-bar__fill {
  height: 100%;
  background: var(--accent);
  border-radius: 3px;
  transition: width var(--duration-slow) var(--ease-out);
}
[data-theme="dark"] .progress-bar__fill {
  box-shadow: 0 0 6px hsl(150 100% 50% / 0.5);
}
[data-theme="dark"] .progress-pct {
  text-shadow: var(--text-glow);
}
.progress-pct {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  min-width: 36px;
  text-align: right;
}

/* Two columns */
.detail-columns {
  display: grid;
  grid-template-columns: 3fr 2fr;
  gap: var(--space-xl);
  align-items: start;
}

@media (max-width: 900px) {
  .detail-columns {
    grid-template-columns: 1fr;
  }
}

/* LLM stats */
.llm-stats {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-lg);
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

/* Error banner */
.error-banner {
  padding: var(--space-md) var(--space-lg);
  background: var(--feedback-error-bg);
  color: var(--feedback-error-text);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
}

/* Action buttons */
.btn-action {
  padding: var(--space-xs) var(--space-lg);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  transition: background var(--duration-fast) var(--ease-out),
              color var(--duration-fast) var(--ease-out);
}
.btn-action:hover { background: var(--bg-inset); }
.btn-action--danger:hover {
  background: var(--feedback-error-bg);
  color: var(--feedback-error-text);
  border-color: var(--feedback-error-text);
}
.btn-action--accent {
  background: var(--accent);
  color: var(--accent-text);
  border-color: var(--accent);
}
[data-theme="dark"] .btn-action--accent {
  box-shadow: var(--shadow-accent);
}
.btn-action--accent:hover {
  background: var(--accent-hover);
}
[data-theme="dark"] .btn-action--accent:hover {
  box-shadow: var(--shadow-accent-lg);
}
</style>
