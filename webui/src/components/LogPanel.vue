<template>
  <div class="log-panel" ref="panelRef" aria-label="执行日志" role="log" aria-live="polite">
    <div v-if="logs.length === 0" class="log-panel__empty">等待日志…</div>
    <div
      v-for="(log, i) in logs"
      :key="i"
      class="log-panel__line"
      :class="`log-panel__line--${log.level?.toLowerCase()}`"
    >
      <span class="log-panel__ts tabular-nums">{{ log.ts }}</span>
      <span class="log-panel__level">[{{ log.level }}]</span>
      <span class="log-panel__msg">{{ log.msg }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  logs: { type: Array, default: () => [] },
})

const panelRef = ref(null)
let userScrolledUp = false

function onScroll() {
  const el = panelRef.value
  if (!el) return
  userScrolledUp = el.scrollTop + el.clientHeight < el.scrollHeight - 40
}

watch(() => props.logs.length, async () => {
  if (userScrolledUp) return
  await nextTick()
  const el = panelRef.value
  if (el) el.scrollTop = el.scrollHeight
})
</script>

<style scoped>
.log-panel {
  background: var(--bg-inset);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: var(--space-md);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  line-height: 1.7;
  max-height: 400px;
  overflow-y: auto;
  overscroll-behavior: contain;
}
[data-theme="dark"] .log-panel {
  position: relative;
  border-color: hsl(0 0% 15%);
}
/* 装饰性网格线已移除 — 遵循「背景要干净纯色」红线 */

.log-panel__empty {
  color: var(--text-tertiary);
  text-align: center;
  padding: var(--space-xl);
}

.log-panel__line {
  display: flex;
  gap: var(--space-sm);
  padding: 1px 0;
  min-width: 0;
}

.log-panel__ts {
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.log-panel__level {
  flex-shrink: 0;
  font-weight: 600;
}

.log-panel__line--ok .log-panel__level { color: var(--feedback-success-text); }
.log-panel__line--err .log-panel__level { color: var(--feedback-error-text); }
.log-panel__line--warn .log-panel__level { color: var(--feedback-warn-text); }
.log-panel__line--step .log-panel__level { color: var(--accent); }
[data-theme="dark"] .log-panel__line--step .log-panel__level { text-shadow: var(--text-glow); }
[data-theme="dark"] .log-panel__msg { text-shadow: 0 0 4px hsl(0 0% 50% / 0.15); }
.log-panel__line--human .log-panel__level { color: var(--status-paused); }

.log-panel__msg {
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ─── Neon: Typewriter reveal for new log lines ─── */
[data-theme="dark"] .log-panel__msg {
  animation: matrix-type 0.25s steps(10) both;
}
@keyframes matrix-type {
  from { clip-path: inset(0 100% 0 0); }
  to   { clip-path: inset(0 0 0 0); }
}

/* ─── Neon: flash on new log line ─── */
[data-theme="dark"] .log-panel__line {
  animation: phosphor-flash 0.4s ease-out;
}
@keyframes phosphor-flash {
  0%   { background: hsl(0 0% 50% / 0.06); }
  100% { background: transparent; }
}

@media (prefers-reduced-motion: reduce) {
  [data-theme="dark"] .log-panel__msg { animation: none; }
  [data-theme="dark"] .log-panel__line { animation: none; }
}
</style>
