<script setup lang="ts">
/**
 * StepDots — 流水线步骤进度点（占位实现，待工作台 subagent 完善）
 * Props 与 StagePane 用法对齐
 */
defineProps<{
  currentStep?: number | null
  completedSteps?: number[]
  status?: string
}>()
</script>

<template>
  <div class="step-dots" aria-hidden="true">
    <span class="dot" />
    <span class="dot" />
    <span class="dot" />
    <span class="dot" />
    <span class="dot" />
  </div>
</template>

<style scoped>
.step-dots {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  background: var(--border);
}
</style>
