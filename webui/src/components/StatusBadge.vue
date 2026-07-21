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
  padding: 3px 12px;
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  font-weight: 600;
  white-space: nowrap;
  letter-spacing: 0.01em;
}

.status-badge__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 0 0 2px hsl(0 0% 100% / 0.3);
}

.status-badge--running {
  background: var(--accent-subtle);
  color: var(--accent);
  border: 1px solid hsl(var(--mono-hue) 60% 85%);
}
[data-theme="dark"] .status-badge--running {
  border-color: hsl(150 60% 25%);
  text-shadow: var(--text-glow);
}
.status-badge--running .status-badge__dot {
  background: var(--status-running);
  animation: pulse 1.5s ease-in-out infinite;
  box-shadow: 0 0 0 2px var(--accent-subtle), 0 0 6px var(--status-running);
}
[data-theme="dark"] .status-badge--running .status-badge__dot {
  box-shadow: 0 0 0 2px var(--accent-subtle), 0 0 8px hsl(150 100% 50% / 0.6);
}

.status-badge--done {
  background: var(--feedback-success-bg);
  color: var(--feedback-success-text);
  border: 1px solid var(--feedback-success-border);
}
.status-badge--done .status-badge__dot { background: var(--status-done); box-shadow: 0 0 0 2px var(--feedback-success-bg); }

.status-badge--paused {
  background: var(--feedback-warn-bg);
  color: var(--feedback-warn-text);
  border: 1px solid var(--feedback-warn-border);
}
.status-badge--paused .status-badge__dot { background: var(--status-paused); box-shadow: 0 0 0 2px var(--feedback-warn-bg); }

.status-badge--error {
  background: var(--feedback-error-bg);
  color: var(--feedback-error-text);
  border: 1px solid var(--feedback-error-border);
}
.status-badge--error .status-badge__dot { background: var(--status-error); box-shadow: 0 0 0 2px var(--feedback-error-bg); }

.status-badge--cancelled,
.status-badge--pending {
  background: var(--bg-inset);
  color: var(--text-tertiary);
  border: 1px solid var(--border-default);
}
.status-badge--cancelled .status-badge__dot,
.status-badge--pending .status-badge__dot { background: var(--status-cancelled); box-shadow: 0 0 0 2px var(--bg-inset); }

.status-badge--interrupted {
  background: var(--feedback-warn-bg);
  color: var(--feedback-warn-text);
  border: 1px solid var(--feedback-warn-border);
}
.status-badge--interrupted .status-badge__dot { background: var(--status-paused); box-shadow: 0 0 0 2px var(--feedback-warn-bg); }

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.85); }
}

@media (prefers-reduced-motion: reduce) {
  .status-badge--running .status-badge__dot { animation: none; }
}
</style>
