<template>
  <div
    class="drop-zone"
    :class="{ 'drop-zone--dragging': isDragging, 'drop-zone--compact': compact }"
    role="button"
    tabindex="0"
    :aria-label="label"
    @click="fileInput?.click()"
    @keydown.enter.prevent="fileInput?.click()"
    @keydown.space.prevent="fileInput?.click()"
    @dragover.prevent="isDragging = true"
    @dragleave="isDragging = false"
    @drop.prevent="handleDrop"
  >
    <input
      ref="fileInput"
      type="file"
      :accept="accept"
      class="drop-zone__input"
      :aria-label="label"
      @change="handleSelect"
    />
    <slot v-if="$slots.default" />
    <template v-else>
      <svg class="drop-zone__icon" viewBox="0 0 24 24" width="32" height="32" aria-hidden="true">
        <path fill="currentColor" d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zm-1 2l5 5h-5V4zM6 20V4h5v7h7v9H6z"/>
      </svg>
      <p class="drop-zone__text">拖拽文件到此处，或点击选择</p>
      <p class="drop-zone__hint">{{ hint }}</p>
    </template>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  accept: { type: String, default: '.md,.txt' },
  hint: { type: String, default: '支持 .md / .txt，最大 10 MB' },
  label: { type: String, default: '上传文件' },
  compact: { type: Boolean, default: false },
})

const emit = defineEmits(['file'])

const fileInput = ref(null)
const isDragging = ref(false)

function handleSelect(e) {
  const file = e.target.files?.[0]
  if (file) emit('file', file)
  e.target.value = ''
}

function handleDrop(e) {
  isDragging.value = false
  const file = e.dataTransfer.files?.[0]
  if (file) emit('file', file)
}
</script>

<style scoped>
.drop-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-sm);
  padding: var(--space-2xl) var(--space-xl);
  border: 2px dashed var(--border-strong);
  border-radius: var(--radius-lg);
  cursor: pointer;
  text-align: center;
  background: var(--bg-surface);
  transition: border-color var(--duration-normal) var(--ease-out),
              background var(--duration-normal) var(--ease-out),
              box-shadow var(--duration-normal) var(--ease-out);
}

.drop-zone:hover,
.drop-zone:focus-visible {
  border-color: var(--accent);
  background: var(--accent-subtle);
  box-shadow: inset 0 0 0 1px var(--accent-glow), var(--shadow-sm);
}

.drop-zone--dragging {
  border-color: var(--accent);
  background: var(--accent-subtle);
  box-shadow: inset 0 0 24px var(--accent-glow), var(--shadow-md);
  transform: scale(1.01);
}
[data-theme="dark"] .drop-zone--dragging {
  box-shadow: inset 0 0 24px hsl(150 100% 50% / 0.15), var(--shadow-md), 0 0 12px hsl(150 100% 50% / 0.2);
  border-color: var(--accent);
}
[data-theme="dark"] .drop-zone:hover,
[data-theme="dark"] .drop-zone:focus-visible {
  border-color: var(--accent);
  box-shadow: inset 0 0 0 1px var(--accent-glow), var(--shadow-sm), 0 0 8px hsl(150 100% 50% / 0.12);
}

.drop-zone--compact {
  padding: var(--space-lg) var(--space-md);
}

.drop-zone__input {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
}

.drop-zone__icon {
  color: var(--text-tertiary);
  transition: color var(--duration-normal) var(--ease-out);
}
.drop-zone:hover .drop-zone__icon,
.drop-zone--dragging .drop-zone__icon {
  color: var(--accent);
}

.drop-zone__text {
  font-size: var(--text-base);
  color: var(--text-secondary);
  font-weight: 500;
}

.drop-zone__hint {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}
</style>
