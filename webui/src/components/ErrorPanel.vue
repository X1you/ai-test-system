<script setup lang="ts">
/**
 * ErrorPanel — 流水线出错/取消面板（占位实现，待工作台 subagent 完善）
 */
defineProps<{
  progress?: any
}>()
</script>

<template>
  <div class="error-panel">
    <p class="title">⚠ 执行终止</p>
    <p class="hint">流水线已停止，请查看日志或重新发起。</p>
  </div>
</template>

<style scoped>
.error-panel {
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
