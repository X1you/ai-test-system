<template>
  <nav v-if="pages > 1" class="pagination" aria-label="分页导航">
    <button
      class="pagination__btn"
      :disabled="page <= 1"
      aria-label="上一页"
      @click="$emit('change', page - 1)"
    >
      <svg viewBox="0 0 20 20" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M12.7 15.3a1 1 0 0 1-1.4 0l-5-5a1 1 0 0 1 0-1.4l5-5a1 1 0 1 1 1.4 1.4L8.4 10l4.3 4.3a1 1 0 0 1 0 1z"/></svg>
    </button>
    <span class="pagination__info tabular-nums">第 {{ page }} / {{ pages }} 页</span>
    <button
      class="pagination__btn"
      :disabled="page >= pages"
      aria-label="下一页"
      @click="$emit('change', page + 1)"
    >
      <svg viewBox="0 0 20 20" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M7.3 4.7a1 1 0 0 1 1.4 0l5 5a1 1 0 0 1 0 1.4l-5 5a1 1 0 1 1-1.4-1.4l4.3-4.3-4.3-4.3a1 1 0 0 1 0-1z"/></svg>
    </button>
  </nav>
</template>

<script setup>
defineProps({
  page: { type: Number, default: 1 },
  pages: { type: Number, default: 1 },
})
defineEmits(['change'])
</script>

<style scoped>
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-md);
  padding-top: var(--space-xl);
}

.pagination__btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-secondary);
  box-shadow: var(--shadow-xs);
  transition: background var(--duration-normal) var(--ease-out),
              color var(--duration-normal) var(--ease-out),
              border-color var(--duration-normal) var(--ease-out),
              transform var(--duration-normal) var(--ease-out);
}
.pagination__btn:hover:not(:disabled) {
  background: var(--accent-subtle);
  color: var(--accent);
  border-color: var(--accent);
  transform: scale(1.08);
}
[data-theme="dark"] .pagination__btn:hover:not(:disabled) {
  box-shadow: var(--shadow-accent);
  text-shadow: var(--text-glow);
}
.pagination__btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
  box-shadow: none;
}

.pagination__info {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  font-weight: 500;
}
</style>
