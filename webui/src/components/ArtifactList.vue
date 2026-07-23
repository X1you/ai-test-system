<template>
  <div class="artifact-list">
    <h3 class="artifact-list__title">产物</h3>
    <div v-if="artifacts.length === 0" class="artifact-list__empty">暂无产物</div>
    <ul v-else class="artifact-list__items">
      <li v-for="a in artifacts" :key="a.name" class="artifact-item">
        <span class="artifact-item__icon" aria-hidden="true">
          <svg v-if="a.type === 'markdown'" viewBox="0 0 16 16" width="14" height="14"><path fill="currentColor" d="M2 2h12v12H2V2zm2 3v2h3V5H4zm0 4v2h8V9H4zm5-4v2h3V5H9z"/></svg>
          <svg v-else-if="a.type === 'excel'" viewBox="0 0 16 16" width="14" height="14"><path fill="currentColor" d="M2 2h12v12H2V2zm2 2v8h8V4H4zm1 1h2v2H5V5zm3 0h3v2H8V5zM5 8h2v2H5V8zm3 0h3v2H8V8z"/></svg>
          <svg v-else viewBox="0 0 16 16" width="14" height="14"><path fill="currentColor" d="M8 1L2 5v6l6 4 6-4V5L8 1zm0 2.2L12 6v4l-4 2.7L4 10V6l4-2.8z"/></svg>
        </span>
        <span class="artifact-item__name">{{ a.display_name }}</span>
        <span class="artifact-item__size tabular-nums">{{ formatSize(a.size) }}</span>
        <div class="artifact-item__actions">
          <button
            v-if="a.type !== 'xmind'"
            class="artifact-item__btn"
            aria-label="预览"
            @click="$emit('preview', a)"
          >预览</button>
          <button
            class="artifact-item__btn"
            :aria-label="`下载 ${a.display_name}`"
            @click="$emit('download', a)"
          >下载</button>
        </div>
      </li>
    </ul>
    <button
      v-if="showExport"
      class="artifact-list__export"
      @click="$emit('export')"
    >
      <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M8 1v8m0 0l-3-3m3 3l3-3M3 12v2h10v-2"/></svg>
      导出 PyTest 工程 (.zip)
    </button>
  </div>
</template>

<script setup>
defineProps({
  artifacts: { type: Array, default: () => [] },
  showExport: { type: Boolean, default: true },
})
defineEmits(['preview', 'download', 'export'])

function formatSize(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
</script>

<style scoped>
.artifact-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.artifact-list__title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-secondary);
}

.artifact-list__empty {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  padding: var(--space-lg);
  text-align: center;
}

.artifact-list__items {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.artifact-item {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-md);
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  box-shadow: var(--shadow-xs);
  transition: transform var(--duration-normal) var(--ease-out),
              border-color var(--duration-normal) var(--ease-out),
              box-shadow var(--duration-normal) var(--ease-out);
}
.artifact-item:hover {
  transform: translateX(2px);
  border-color: var(--border-strong);
  box-shadow: var(--shadow-sm);
}
[data-theme="dark"] .artifact-item:hover {
  border-color: hsl(0 0% 25%);
  box-shadow: var(--shadow-sm), 0 0 6px hsl(0 0% 50% / 0.1);
}

.artifact-item__icon {
  color: var(--text-tertiary);
  flex-shrink: 0;
  display: flex;
}

.artifact-item__name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-primary);
}

.artifact-item__size {
  color: var(--text-tertiary);
  font-size: var(--text-xs);
  flex-shrink: 0;
}

.artifact-item__actions {
  display: flex;
  gap: var(--space-xs);
  flex-shrink: 0;
}

.artifact-item__btn {
  padding: 3px 10px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-weight: 500;
  transition: background var(--duration-fast) var(--ease-out),
              color var(--duration-fast) var(--ease-out),
              border-color var(--duration-fast) var(--ease-out);
}
.artifact-item__btn:hover {
  background: var(--accent-subtle);
  color: var(--accent);
  border-color: var(--accent);
}
[data-theme="dark"] .artifact-item__btn:hover {
  text-shadow: var(--text-glow);
  box-shadow: 0 0 4px hsl(0 0% 50% / 0.15);
}

.artifact-list__export {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-lg);
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: 500;
  transition: background var(--duration-normal) var(--ease-out),
              color var(--duration-normal) var(--ease-out),
              border-color var(--duration-normal) var(--ease-out),
              box-shadow var(--duration-normal) var(--ease-out);
}
.artifact-list__export:hover {
  background: var(--accent-subtle);
  color: var(--accent);
  border-color: var(--accent);
  border-style: solid;
  box-shadow: var(--shadow-sm);
}
[data-theme="dark"] .artifact-list__export:hover {
  box-shadow: var(--shadow-sm), 0 0 8px hsl(0 0% 50% / 0.15);
  text-shadow: var(--text-glow);
}
</style>
