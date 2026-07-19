<template>
  <dialog ref="dialogRef" class="preview-modal" @close="$emit('close')" @click.self="$emit('close')">
    <div class="preview-modal__header">
      <h2 class="preview-modal__title">{{ title }}</h2>
      <button class="preview-modal__close" aria-label="关闭预览" @click="dialogRef?.close()">
        <svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M6.3 6.3a1 1 0 0 1 1.4 0L10 8.6l2.3-2.3a1 1 0 1 1 1.4 1.4L11.4 10l2.3 2.3a1 1 0 0 1-1.4 1.4L10 11.4l-2.3 2.3a1 1 0 0 1-1.4-1.4L8.6 10 6.3 7.7a1 1 0 0 1 0-1.4z"/></svg>
      </button>
    </div>
    <div class="preview-modal__body">
      <div v-if="loading" class="preview-modal__loading" role="status">加载中…</div>
      <div v-else-if="error" class="preview-modal__error" role="alert">{{ error }}</div>
      <!-- Markdown -->
      <div v-else-if="data?.type === 'markdown'" class="preview-md" v-html="data.html"></div>
      <!-- Excel -->
      <div v-else-if="data?.type === 'excel'" class="preview-excel">
        <table>
          <tbody>
            <tr v-for="(row, ri) in data.rows" :key="ri">
              <td
                v-for="(cell, ci) in row"
                :key="ci"
                :class="{ 'preview-excel__header': ri === 0 }"
              >{{ cell }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </dialog>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  title: { type: String, default: '预览' },
  pipelineId: { type: String, default: '' },
  artifactName: { type: String, default: '' },
  open: { type: Boolean, default: false },
})

const emit = defineEmits(['close'])

const dialogRef = ref(null)
const data = ref(null)
const loading = ref(false)
const error = ref('')

watch(() => props.open, async (val) => {
  if (val) {
    dialogRef.value?.showModal()
    await loadPreview()
  } else {
    dialogRef.value?.close()
  }
})

async function loadPreview() {
  if (!props.pipelineId || !props.artifactName) return
  loading.value = true
  error.value = ''
  data.value = null
  try {
    const resp = await fetch(`/api/v1/pipeline/${props.pipelineId}/preview/${props.artifactName}`)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    data.value = await resp.json()
  } catch (e) {
    error.value = `预览加载失败: ${e.message}`
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.preview-modal {
  width: min(90vw, 800px);
  max-height: 80vh;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  background: var(--bg-surface);
  color: var(--text-primary);
  padding: 0;
  overscroll-behavior: contain;
}

.preview-modal::backdrop {
  background: hsl(0 0% 0% / 0.5);
}

.preview-modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-lg) var(--space-xl);
  border-bottom: 1px solid var(--border-default);
}

.preview-modal__title {
  font-size: var(--text-lg);
  font-weight: 600;
}

.preview-modal__close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-secondary);
  transition: background var(--duration-fast) var(--ease-out);
}
.preview-modal__close:hover {
  background: var(--bg-inset);
}

.preview-modal__body {
  padding: var(--space-xl);
  overflow-y: auto;
  max-height: calc(80vh - 64px);
}

.preview-modal__loading,
.preview-modal__error {
  text-align: center;
  padding: var(--space-xl);
  color: var(--text-secondary);
}
.preview-modal__error {
  color: var(--feedback-error-text);
}

/* Markdown rendering */
.preview-md {
  font-size: var(--text-base);
  line-height: 1.7;
}
.preview-md :deep(h1),
.preview-md :deep(h2),
.preview-md :deep(h3) {
  margin: var(--space-lg) 0 var(--space-sm);
  font-weight: 600;
}
.preview-md :deep(p) { margin: var(--space-sm) 0; }
.preview-md :deep(table) {
  border: 1px solid var(--border-default);
  margin: var(--space-md) 0;
}
.preview-md :deep(th),
.preview-md :deep(td) {
  border: 1px solid var(--border-default);
  padding: var(--space-xs) var(--space-sm);
  font-size: var(--text-sm);
}
.preview-md :deep(code) {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  background: var(--bg-inset);
  padding: 1px 4px;
  border-radius: var(--radius-sm);
}
.preview-md :deep(pre) {
  background: var(--bg-inset);
  padding: var(--space-md);
  border-radius: var(--radius-md);
  overflow-x: auto;
}

/* Excel table */
.preview-excel {
  overflow-x: auto;
}
.preview-excel table {
  font-size: var(--text-xs);
  font-family: var(--font-mono);
}
.preview-excel td {
  border: 1px solid var(--border-default);
  padding: var(--space-xs) var(--space-sm);
  white-space: nowrap;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.preview-excel__header {
  background: var(--bg-inset);
  font-weight: 600;
}
</style>
