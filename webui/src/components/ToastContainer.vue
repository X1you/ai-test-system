<template>
  <div
    class="toast-region"
    role="region"
    aria-label="通知"
    aria-live="polite"
  >
    <TransitionGroup name="toast" tag="div" class="toast-container">
      <div
        v-for="item in items"
        :key="item.id"
        class="toast"
        :class="`toast--${item.type}`"
        role="alert"
      >
        <svg class="toast__icon" viewBox="0 0 20 20" width="16" height="16" aria-hidden="true">
          <path v-if="item.type === 'success'" fill="currentColor" d="M10 1a9 9 0 1 0 0 18 9 9 0 0 0 0-18zm4.3 7.3-5 5a1 1 0 0 1-1.4 0l-2.5-2.5a1 1 0 1 1 1.4-1.4L8.8 11l4.1-4.1a1 1 0 0 1 1.4 1.4z"/>
          <path v-else-if="item.type === 'error'" fill="currentColor" d="M10 1a9 9 0 1 0 0 18 9 9 0 0 0 0-18zm3.5 11.1-2.4 2.4L10 13.4l-1.1 1.1-2.4-2.4 1.1-1.1L6.6 10l-1.1-1.1 2.4-2.4L10 7.6l1.1-1.1 2.4 2.4-1.1 1.1L13.4 10z"/>
          <path v-else-if="item.type === 'warn'" fill="currentColor" d="M10 1L1 18h18L10 1zm0 5v6a1 1 0 1 1-2 0V6a1 1 0 1 1 2 0zm-1 9a1 1 0 1 1 2 0 1 1 0 0 1-2 0z"/>
          <path v-else fill="currentColor" d="M10 1a9 9 0 1 0 0 18 9 9 0 0 0 0-18zm0 14a1 1 0 1 1 0-2 1 1 0 0 1 0 2zm1-4a1 1 0 1 1-2 0V6a1 1 0 1 1 2 0v5z"/>
        </svg>
        <span class="toast__msg">{{ item.message }}</span>
        <button class="toast__close" aria-label="关闭通知" @click="toast.remove(item.id)">✕</button>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useToast } from '../composables/useToast'

const toast = useToast()

const items = computed(() => toast.items.value)
</script>

<style scoped>
.toast-region {
  pointer-events: none;
}

.toast-container {
  position: fixed;
  top: var(--space-lg);
  right: var(--space-lg);
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
  max-width: 360px;
  pointer-events: none;
}

.toast {
  display: flex;
  align-items: flex-start;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  box-shadow: var(--shadow-lg);
  font-size: var(--text-sm);
  line-height: 1.4;
  pointer-events: auto;
}

.toast__icon {
  flex-shrink: 0;
  margin-top: 1px;
}
.toast--success .toast__icon { color: var(--feedback-success-text); }
.toast--error   .toast__icon { color: var(--feedback-error-text); }
.toast--warn    .toast__icon { color: var(--feedback-warn-text); }
.toast--info    .toast__icon { color: var(--accent); }

.toast--success { border-left: 3px solid var(--feedback-success-text); }
.toast--error   { border-left: 3px solid var(--feedback-error-text); }
.toast--warn    { border-left: 3px solid var(--feedback-warn-text); }
.toast--info    { border-left: 3px solid var(--accent); }

.toast__msg {
  flex: 1;
  color: var(--text-primary);
  word-break: break-word;
}

.toast__close {
  flex-shrink: 0;
  border: none;
  background: none;
  color: var(--text-tertiary);
  font-size: var(--text-xs);
  padding: 0;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  transition: color var(--duration-fast) var(--ease-out),
              background var(--duration-fast) var(--ease-out);
}
.toast__close:hover {
  color: var(--text-primary);
  background: var(--bg-inset);
}

/* Transition */
.toast-enter-active,
.toast-leave-active {
  transition: all var(--duration-normal) var(--ease-out);
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(20px);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
.toast-leave-active {
  position: absolute;
  right: 0;
}

@media (prefers-reduced-motion: reduce) {
  .toast-enter-active,
  .toast-leave-active {
    transition-duration: 0.01ms;
  }
}

@media (max-width: 768px) {
  .toast-container {
    top: auto;
    bottom: 80px;
    left: var(--space-md);
    right: var(--space-md);
    max-width: none;
  }
}
</style>
