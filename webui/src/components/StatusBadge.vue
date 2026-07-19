<template>
  <span class="status-badge" :class="`status-badge--${status}`">
    <span class="status-badge__dot" aria-hidden="true"></span>
    {{ label }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: { type: String, default: 'pending' },
})

const labelMap = {
  pending: '等待中',
  running: '运行中',
  done: '已完成',
  paused: '已暂停',
  error: '出错',
  cancelled: '已取消',
  interrupted: '已中断',
}

const label = computed(() => labelMap[props.status] || props.status)
</script>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: var(--text-xs);
  font-weight: 500;
  white-space: nowrap;
}

.status-badge__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-badge--running {
  background: var(--accent-subtle);
  color: var(--accent);
}
.status-badge--running .status-badge__dot {
  background: var(--status-running);
  animation: pulse 1.5s ease-in-out infinite;
}

.status-badge--done {
  background: var(--feedback-success-bg);
  color: var(--feedback-success-text);
}
.status-badge--done .status-badge__dot { background: var(--status-done); }

.status-badge--paused {
  background: var(--feedback-warn-bg);
  color: var(--feedback-warn-text);
}
.status-badge--paused .status-badge__dot { background: var(--status-paused); }

.status-badge--error {
  background: var(--feedback-error-bg);
  color: var(--feedback-error-text);
}
.status-badge--error .status-badge__dot { background: var(--status-error); }

.status-badge--cancelled,
.status-badge--pending {
  background: var(--bg-inset);
  color: var(--text-tertiary);
}
.status-badge--cancelled .status-badge__dot,
.status-badge--pending .status-badge__dot { background: var(--status-cancelled); }

.status-badge--interrupted {
  background: var(--feedback-warn-bg, rgba(234,179,8,0.1));
  color: var(--feedback-warn-text, #b45309);
}
.status-badge--interrupted .status-badge__dot { background: var(--status-paused, #eab308); }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

@media (prefers-reduced-motion: reduce) {
  .status-badge--running .status-badge__dot { animation: none; }
}
</style>
