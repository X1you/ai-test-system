<script setup lang="ts">
/**
 * TakeoverPanel — 流水线暂停/中断人工接管面板（占位实现，待工作台 subagent 完善）
 */
defineProps<{
  progress?: any
}>()
</script>

<template>
  <div class="takeover-panel">
    <p class="title">⏸ 等待人工确认</p>
    <p class="hint">流水线已暂停，请在工作台中处理。</p>
  </div>
</template>

<style scoped>
.takeover-panel {
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
