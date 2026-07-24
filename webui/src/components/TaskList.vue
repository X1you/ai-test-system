<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { usePipelineStore } from '@/stores/pipeline'
import { useRoute } from 'vue-router'
import TaskRow from './TaskRow.vue'

type TabFilter = 'action' | 'running' | 'done' | 'all'

const store = usePipelineStore()
const route = useRoute()
const activeTab = ref<TabFilter>('action')

const tabs = computed(() => [
  { key: 'action' as TabFilter, label: '⚡ 需我处理', count: store.tasksByStatus.action.length },
  { key: 'running' as TabFilter, label: '运行中', count: store.tasksByStatus.running.length },
  { key: 'done' as TabFilter, label: '已完成', count: store.tasksByStatus.done.length },
  { key: 'all' as TabFilter, label: '全部任务', count: store.list.length },
])

const filteredTasks = computed(() => {
  switch (activeTab.value) {
    case 'action': return store.tasksByStatus.action
    case 'running': return store.tasksByStatus.running
    case 'done': return store.tasksByStatus.done
    case 'all': return store.list
  }
})

onMounted(async () => {
  await store.fetchList()
  // 从 URL query 恢复选中任务
  const taskParam = route.query.task as string
  if (taskParam) {
    store.selectPipeline(taskParam)
  }
})

function switchTab(tab: TabFilter) {
  activeTab.value = tab
}
</script>

<template>
  <div class="task-list-pane">
    <!-- Tab 筛选栏 -->
    <div class="tabs-bar">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-btn"
        :class="{ on: activeTab === tab.key }"
        @click="switchTab(tab.key)"
      >
        {{ tab.label }} ({{ tab.count }})
      </button>
    </div>

    <!-- 加载骨架 -->
    <div v-if="store.loading" class="task-table">
      <div v-for="i in 4" :key="i" class="task-skeleton" />
    </div>

    <!-- 任务列表 -->
    <div v-else-if="filteredTasks.length > 0" class="task-table">
      <TaskRow v-for="task in filteredTasks" :key="task.pipeline_id" :task="task" />
    </div>

    <!-- 空状态 -->
    <div v-else class="task-empty">
      此分类下暂无任务
    </div>
  </div>
</template>

<style scoped>
.task-list-pane {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  border-right: 1px solid var(--border);
  transition: all var(--duration-fast) var(--ease);
}
.tabs-bar {
  display: flex;
  padding: 0 1.25rem;
  border-bottom: 1px solid var(--border);
  background: var(--bg);
  gap: 0.25rem;
}
.tab-btn {
  padding: 0.75rem 0.9rem;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--muted-fg);
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  transition: all var(--duration-fast);
}
.tab-btn:hover {
  color: var(--fg);
}
.tab-btn.on {
  color: var(--fg);
  border-bottom-color: var(--fg);
  font-weight: 800;
}
.task-table {
  flex: 1;
  overflow-y: auto;
}
.task-skeleton {
  height: 48px;
  border-bottom: 1px solid var(--border);
  background: linear-gradient(90deg, var(--muted) 25%, var(--panel-bg) 50%, var(--muted) 75%);
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.5s infinite;
}
@keyframes skeleton-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
.task-empty {
  padding: 3rem;
  text-align: center;
  color: var(--muted-fg);
}
</style>
