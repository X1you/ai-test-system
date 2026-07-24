<script setup lang="ts">
/**
 * RunningPanel — 流水线运行中实时面板（占位实现，待工作台 subagent 完善）
 */
defineProps<{
  progress?: any
  sseStatus?: string
}>()
</script>

<template>
  <div class="running-panel">
    <p class="title">▶ 执行中</p>
    <p class="hint">流水线正在运行，请稍候。</p>
  </div>
</template>

<style scoped>
.running-panel {
  padding: 1.5rem;
}
.title {
  font-weight: 600;
  margin-bottom: 0.5rem;
}
.hint {
  font-size: 0.85rem;
  color: var(--muted-fg);
}
</style>
