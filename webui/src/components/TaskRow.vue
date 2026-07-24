<script setup lang="ts">
import type { TaskListItem } from '@/types/pipeline'
import { usePipelineStore } from '@/stores/pipeline'

defineProps<{ task: TaskListItem }>()
const store = usePipelineStore()
</script>

<template>
  <div
    class="task-row"
    :class="{ active: store.selectedId === task.pipeline_id }"
    @click="store.selectPipeline(task.pipeline_id)"
  >
    <span class="task-id">{{ task.pipeline_id }}</span>
    <span class="task-name">{{ task.requirements || '未命名' }}</span>
    <span class="task-status" :class="`badge badge-${task.status === 'interrupted' ? 'paused' : task.status === 'cancelled' ? 'cancelled' : task.status}`">
      <template v-if="task.status === 'paused' || task.status === 'interrupted'">⚡ 待确认</template>
      <template v-else-if="task.status === 'running'">⚡ 运行中</template>
      <template v-else-if="task.status === 'done'">✓ 已完成</template>
      <template v-else-if="task.status === 'error'">✕ 中断</template>
      <template v-else-if="task.status === 'cancelled'">已取消</template>
      <template v-else>等待中</template>
    </span>
    <span class="task-step">Step {{ task.completed_steps }}/{{ task.total_steps }}</span>
  </div>
</template>

<style scoped>
.task-row {
  display: flex;
  align-items: center;
  padding: 0.75rem 1.25rem;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  gap: 0.8rem;
  transition: background var(--duration-fast);
  font-size: 0.85rem;
}
.task-row:hover {
  background: var(--hover-bg);
}
.task-row.active {
  background: var(--accent-dim);
  border-left: 3px solid var(--fg);
  padding-left: calc(1.25rem - 3px);
}
.task-id {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  width: 90px;
  color: var(--muted-fg);
  flex-shrink: 0;
}
.task-name {
  flex: 1;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.task-status {
  width: 100px;
  flex-shrink: 0;
}
.task-step {
  width: 70px;
  color: var(--muted-fg);
  font-size: 0.75rem;
  font-family: var(--font-mono);
  flex-shrink: 0;
  text-align: right;
}
</style>
