/**
 * Pipeline Store — 任务列表/详情/进度状态管理
 * 维护 selectedId 驱动右侧 StagePane + URL 持久化
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiGet, apiPost } from '@/composables/useApi'
import { API } from '@/types/api'
import type {
  TaskListItem,
  TaskListResponse,
  PipelineProgress,
  Mode,
  Dimensions,
  Formats,
} from '@/types/pipeline'

export const usePipelineStore = defineStore('pipeline', () => {
  // ─── State ───
  const list = ref<TaskListItem[]>([])
  const selectedId = ref<string | null>(null)
  const progress = ref<PipelineProgress | null>(null)
  const loading = ref(false)
  const stats = ref({ total: 0, running: 0, done: 0, other: 0 })

  // 分页预留
  const page = ref(1)
  const pages = ref(1)
  const hasMore = computed(() => page.value < pages.value)

  // ─── Getters ───
  const selectedTask = computed(() =>
    list.value.find((t) => t.pipeline_id === selectedId.value)
  )

  // 按状态分组（Tab 筛选用）
  const tasksByStatus = computed(() => {
    const groups = {
      action: [] as TaskListItem[],
      running: [] as TaskListItem[],
      done: [] as TaskListItem[],
      all: list.value,
    }
    for (const t of list.value) {
      if (t.status === 'paused' || t.status === 'interrupted')
        groups.action.push(t)
      if (t.status === 'running') groups.running.push(t)
      if (t.status === 'done') groups.done.push(t)
    }
    return groups
  })

  // ─── Actions ───
  async function fetchList(keyword = '', status = '') {
    loading.value = true
    try {
      const params = new URLSearchParams()
      if (keyword) params.set('keyword', keyword)
      if (status) params.set('status', status)
      const query = params.toString() ? `?${params}` : ''
      const data = await apiGet(`${API.PIPELINE.LIST}${query}`) as TaskListResponse
      list.value = data.items
      stats.value = data.all_stats
      pages.value = data.pages
    } finally {
      loading.value = false
    }
  }

  async function fetchProgress(id: string) {
    const data = await apiGet(API.PIPELINE.PROGRESS(id)) as PipelineProgress
    progress.value = data
    return data
  }

  function selectPipeline(id: string) {
    selectedId.value = id
    // URL 持久化由调用方处理（需要 router 实例）
    fetchProgress(id)
  }

  async function startPipeline(
    file: File,
    mode: Mode,
    dimensions: Dimensions,
    formats: Formats
  ) {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('mode', mode)
    formData.append('dimensions', dimensions)
    formData.append('formats', formats)

    const data = await apiPost(API.PIPELINE.START, formData) as { pipeline_id: string; status: string }
    // 启动成功后刷新列表并选中新任务
    await fetchList()
    selectPipeline(data.pipeline_id)
    return data
  }

  async function cancelPipeline(id: string) {
    await apiPost(API.PIPELINE.CANCEL(id))
    await fetchProgress(id)
    // 更新列表中的状态
    const task = list.value.find((t) => t.pipeline_id === id)
    if (task) task.status = 'cancelled'
  }

  async function resumePipeline(id: string, file?: File) {
    if (file) {
      const formData = new FormData()
      formData.append('file', file)
      await apiPost(API.PIPELINE.RESUME(id), formData)
    } else {
      await apiPost(API.PIPELINE.RESUME(id))
    }
    await fetchProgress(id)
    const task = list.value.find((t) => t.pipeline_id === id)
    if (task) task.status = 'running'
  }

  return {
    // state
    list,
    selectedId,
    progress,
    loading,
    stats,
    page,
    pages,
    hasMore,
    // getters
    selectedTask,
    tasksByStatus,
    // actions
    fetchList,
    fetchProgress,
    selectPipeline,
    startPipeline,
    cancelPipeline,
    resumePipeline,
  }
})
