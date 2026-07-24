<script setup lang="ts">
/**
 * EmptyState — 空状态占位
 * 居中显示灰色文字，icon 可选
 */
withDefaults(
  defineProps<{
    message: string
    /** 可选：自定义图标节点（slot 优先于此 prop） */
    icon?: string
  }>(),
  {
    icon: '',
  },
)
</script>

<template>
  <div class="empty-state" role="status">
    <div v-if="$slots.icon" class="empty-icon">
      <slot name="icon" />
    </div>
    <div v-else-if="icon" class="empty-icon empty-icon-text">{{ icon }}</div>
    <p class="empty-message">{{ message }}</p>
    <div v-if="$slots.default" class="empty-action">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-md);
  padding: var(--space-3xl) var(--space-xl);
  text-align: center;
}

.empty-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2.5rem;
  height: 2.5rem;
  color: var(--muted-fg);
}
.empty-icon-text {
  font-size: 1.75rem;
  line-height: 1;
}

.empty-message {
  font-size: 0.82rem;
  color: var(--muted-fg);
  max-width: 24rem;
}

.empty-action {
  margin-top: var(--space-sm);
}
</style>
