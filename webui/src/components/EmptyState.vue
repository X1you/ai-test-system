<template>
  <div class="empty-state" role="status">
    <svg class="empty-state__icon" viewBox="0 0 48 48" width="48" height="48" aria-hidden="true">
      <path fill="currentColor" d="M8 8h32v28H8V8zm4 4v20h24V12H12zm4 4h16v2H16v-2zm0 5h12v2H16v-2z" opacity="0.4"/>
    </svg>
    <p class="empty-state__text">{{ message }}</p>
    <slot />
  </div>
</template>

<script setup>
defineProps({
  message: { type: String, default: '暂无数据' },
})
</script>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-3xl) var(--space-xl);
  text-align: center;
}

.empty-state__icon {
  color: var(--text-tertiary);
  margin-bottom: var(--space-lg);
  opacity: 0.5;
  filter: drop-shadow(0 2px 8px hsl(var(--mono-hue) 25% 15% / 0.06));
}
[data-theme="dark"] .empty-state__icon {
  color: hsl(150 50% 35%);
  filter: drop-shadow(0 0 8px hsl(150 100% 50% / 0.15));
}

.empty-state__text {
  color: var(--text-secondary);
  font-size: var(--text-base);
  font-weight: 500;
}
</style>
