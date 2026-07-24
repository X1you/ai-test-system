<script setup lang="ts">
import { computed, watch, onUnmounted, ref, onErrorCaptured } from 'vue'
import { usePipelineStore } from '@/stores/pipeline'
import { useSSE } from '@/composables/useSSE'
import { useToastStore } from '@/composables/useToast'
import type { PipelineProgress } from '@/types/pipeline'
import StepDots from './StepDots.vue'
import TakeoverPanel from './TakeoverPanel.vue'
import RunningPanel from './RunningPanel.vue'
import ErrorPanel from './ErrorPanel.vue'
import ArtifactsViewer from './ArtifactsViewer.vue'

const store = usePipelineStore()
const toast = useToastStore()
const sseStatus = ref('disconnected')

let sse: ReturnType<typeof useSSE> | null = null

const progress = computed<PipelineProgress | null>(() => store.progress)
const status = computed(() => progress.value?.status || 'pending')

// SSE 生命周期管理：selectedId 变化时重连
watch(
  () => store.selectedId,
  (newId) => {
    // 关闭旧连接
    if (sse) {
      sse.disconnect()
      sse = null
    }
    if (!newId) return

    // 只有 running 状态才连 SSE
    const currentStatus = store.progress?.status
    if (currentStatus === 'running') {
      connectSSE(newId)
    }
  }
)

function connectSSE(id: string) {
  sse = useSSE(id, {
    onStepDone: (data) => {
      // 更新进度
      if (store.progress) {
        store.progress.status = data.status || store.progress.status
        store.progress.percent = data.percent ?? store.progress.percent
        store.progress.completed_steps = data.completed_steps || store.progress.completed_steps
        store.progress.current_step = data.current_step ?? store.progress.current_step
        store.progress.steps = data.steps || store.progress.steps
        if (data.logs) store.progress.logs = data.logs
      }
    },
    onLog: (data) => {
      if (store.progress && data.msg) {
        store.progress.logs.push(data)
      }
    },
    onPaused: (data) => {
      if (store.progress) {
        store.progress.status = 'paused'
        if (data.step_id) store.progress.current_step = data.step_id
      }
      toast.info('流水线暂停，等待确认')
    },
    onTerminal: (event) => {
      if (store.progress) {
        store.progress.status = event as any
      }
      toast.info(`流水线已${event === 'done' ? '完成' : event === 'error' ? '出错' : '取消'}`)
      if (sse) {
        sse.disconnect()
        sse = null
      }
    },
    onStatusChange: (s) => {
      sseStatus.value = s
    },
  })
  sse.connect()
}

onUnmounted(() => {
  if (sse) sse.disconnect()
})

// 错误边界：子组件崩溃不影响整个工作台
const hasError = ref(false)
const errorMsg = ref('')
onErrorCaptured((err) => {
  hasError.value = true
  errorMsg.value = String(err)
  toast.error('面板渲染异常')
  return false // 阻止继续传播
})
</script>

<template>
  <div class="stage-pane">
    <!-- 无选中任务 -->
    <div v-if="!store.selectedId" class="stage-empty">
      <p>← 从左侧选择一个任务查看详情</p>
    </div>

    <!-- 错误边界降级 -->
    <div v-else-if="hasError" class="stage-error">
      <p>⚠ 渲染异常</p>
      <p class="error-detail">{{ errorMsg }}</p>
    </div>

    <!-- 正常状态分支 -->
    <template v-else-if="progress">
      <!-- 标题栏 + 步骤点 -->
      <div class="pipeline-mini-bar">
        <div class="p-task-title">{{ store.selectedTask?.requirements || progress.pipeline_id }}</div>
        <StepDots :current-step="progress.current_step" :completed-steps="progress.completed_steps" :status="status" />
      </div>

      <!-- 状态分支 -->
      <TakeoverPanel v-if="status === 'paused' || status === 'interrupted'" :progress="progress" />
      <RunningPanel v-else-if="status === 'running'" :progress="progress" :sse-status="sseStatus" />
      <ErrorPanel v-else-if="status === 'error' || status === 'cancelled'" :progress="progress" />
      <ArtifactsViewer v-else-if="status === 'done'" :pipeline-id="progress.pipeline_id" />
      <div v-else class="stage-pending">等待启动...</div>
    </template>
  </div>
</template>

<style scoped>
.stage-pane {
  width: 540px;
  flex-shrink: 0;
  background: var(--bg);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  transition: width var(--duration-normal) var(--ease);
}
.stage-empty,
.stage-pending {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--muted-fg);
  font-size: 0.85rem;
}
.stage-error {
  margin: 1.25rem;
  padding: 1.25rem;
  border: 1px solid var(--border);
  background: var(--panel-bg);
}
.error-detail {
  font-size: 0.75rem;
  font-family: var(--font-mono);
  color: var(--muted-fg);
  margin-top: 0.5rem;
}
.pipeline-mini-bar {
  padding: 0.75rem 1.25rem;
  border-bottom: 1px solid var(--border);
  background: var(--muted);
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.p-task-title {
  font-weight: 800;
  font-size: 0.88rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 280px;
}
</style>
