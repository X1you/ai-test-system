<script setup lang="ts">
/**
 * ArtifactsViewer — 流水线完成产物查看器（占位实现，待工作台 subagent 完善）
 */
defineProps<{
  pipelineId?: string
}>()
</script>

<template>
  <div class="artifacts-viewer">
    <p class="title">✓ 执行完成</p>
    <p class="hint">产物已就绪，请在工作台查看下载。</p>
  </div>
</template>

<style scoped>
.artifacts-viewer {
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
