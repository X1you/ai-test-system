<template>
  <ol class="step-progress" aria-label="Pipeline 步骤进度">
    <li
      v-for="step in steps"
      :key="step.id"
      class="step-progress__item"
      :class="`step-progress__item--${step.status}`"
      :aria-current="step.status === 'running' ? 'step' : undefined"
    >
      <span class="step-progress__indicator" aria-hidden="true">
        <svg v-if="step.status === 'done'" viewBox="0 0 16 16" width="12" height="12">
          <path fill="currentColor" d="M13.5 4.5l-7 7L3 8l1-1 2.5 2.5 6-6z"/>
        </svg>
        <span v-else-if="step.status === 'running'" class="step-progress__spinner"></span>
        <span v-else class="step-progress__num">{{ step.id }}</span>
      </span>
      <span class="step-progress__name">{{ step.name }}</span>
      <span v-if="step.detail" class="step-progress__detail">{{ step.detail }}</span>
    </li>
  </ol>
</template>

<script setup>
defineProps({
  steps: { type: Array, default: () => [] },
})
</script>

<style scoped>
.step-progress {
  display: flex;
  gap: var(--space-xs);
  list-style: none;
  overflow-x: auto;
  padding-bottom: var(--space-sm);
}

.step-progress__item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-xs);
  min-width: 72px;
  flex: 1;
  position: relative;
  padding: var(--space-sm) var(--space-xs);
}

/* Connector line */
.step-progress__item:not(:last-child)::after {
  content: '';
  position: absolute;
  top: 22px;
  right: -2px;
  width: calc(100% - 32px);
  height: 2px;
  background: var(--border-default);
  transform: translateX(50%);
}
.step-progress__item--done:not(:last-child)::after {
  background: var(--status-done);
}

.step-progress__indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 2px solid var(--border-default);
  background: var(--bg-surface);
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  z-index: 1;
  flex-shrink: 0;
}

.step-progress__item--done .step-progress__indicator {
  border-color: var(--status-done);
  background: var(--status-done);
  color: var(--accent-text);
}

.step-progress__item--running .step-progress__indicator {
  border-color: var(--status-running);
  color: var(--status-running);
}

.step-progress__spinner {
  width: 12px;
  height: 12px;
  border: 2px solid var(--accent-subtle);
  border-top-color: var(--status-running);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (prefers-reduced-motion: reduce) {
  .step-progress__spinner { animation: none; border-top-color: var(--status-running); }
}

.step-progress__name {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  text-align: center;
  white-space: nowrap;
}

.step-progress__item--done .step-progress__name {
  color: var(--text-primary);
}
.step-progress__item--running .step-progress__name {
  color: var(--accent);
  font-weight: 500;
}

.step-progress__detail {
  font-size: 10px;
  color: var(--text-tertiary);
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 80px;
}
</style>
