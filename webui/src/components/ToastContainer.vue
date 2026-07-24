<script setup lang="ts">
import { useToastStore } from '@/composables/useToast'

const toast = useToastStore()
</script>

<template>
  <Teleport to="body">
    <div class="toast-container">
      <TransitionGroup name="toast">
        <div
          v-for="item in toast.items"
          :key="item.id"
          class="toast-item"
          :class="`toast-${item.type}`"
          @click="toast.dismiss(item.id)"
        >
          {{ item.message }}
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-container {
  position: fixed;
  bottom: 24px;
  right: 20px;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  pointer-events: none;
}

.toast-item {
  padding: 0.6rem 1.2rem;
  font-weight: 700;
  font-size: 0.8rem;
  font-family: var(--font-mono);
  background: var(--fg);
  color: var(--bg);
  border: 1px solid var(--border);
  cursor: pointer;
  pointer-events: auto;
  transition: opacity var(--duration-fast) var(--ease);
}

.toast-success {
  border-left: 3px solid #2e7d32;
}
.toast-error {
  border-left: 3px solid #e8747c;
}
.toast-warn {
  border-left: 3px solid #f57f17;
}

.toast-enter-active,
.toast-leave-active {
  transition: all var(--duration-normal) var(--ease);
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
</style>
