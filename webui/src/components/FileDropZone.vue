<script setup lang="ts">
import { ref } from 'vue'
import { useFileUpload } from '@/composables/useFileUpload'
import { useToastStore } from '@/composables/useToast'

const emit = defineEmits<{ (e: 'file-selected', file: File): void }>()
const toast = useToastStore()

const hiddenInput = ref<HTMLInputElement | null>(null)
const { isDragging, error, onDrop, onDragOver, onDragLeave, onInputChange, handleFile } =
  useFileUpload({
    extensions: ['md', 'txt'],
    mimeTypes: ['text/plain', 'text/markdown'],
    maxSize: 10 * 1024 * 1024,
  })

function onFileSelected(file: File) {
  if (handleFile(file)) {
    emit('file-selected', file)
  } else {
    toast.error(error.value || '文件校验失败')
  }
}

function onDropWrapper(e: DragEvent) {
  onDrop(e)
  // useFileUpload 内部已校验，这里需要检查是否成功
}

function openFilePicker() {
  hiddenInput.value?.click()
}

function onChangeWrapper(e: Event) {
  const target = e.target as HTMLInputElement
  if (target.files?.length) {
    onFileSelected(target.files[0])
  }
  // 重置 input 值以允许重复选同一文件
  target.value = ''
}
</script>

<template>
  <section
    class="hero-dropzone"
    :class="{ dragover: isDragging }"
    @click="openFilePicker"
    @dragover.prevent="onDragOver"
    @dragleave="onDragLeave"
    @drop.prevent="onDropWrapper"
  >
    <div class="hero-left">
      <div class="hero-icon">📄 ➔ ⚡</div>
      <div class="hero-text">
        <div class="hero-title">开启一次 AI 测试流水线</div>
        <div class="hero-desc">
          拖拽需求文档 (<code>.md</code> / <code>.txt</code>) 到此处，或点击配置启动
        </div>
        <div v-if="error" class="hero-error">{{ error }}</div>
      </div>
    </div>
    <button class="btn-primary" @click.stop="openFilePicker">+ 选择需求文件</button>
    <input
      ref="hiddenInput"
      type="file"
      accept=".md,.txt"
      style="display: none"
      @change="onChangeWrapper"
    />
  </section>
</template>

<style scoped>
.hero-dropzone {
  margin: 1rem 1.25rem 0;
  border: 1px dashed var(--border);
  background: var(--panel-bg);
  padding: 1.1rem 1.5rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease);
}
.hero-dropzone:hover,
.hero-dropzone.dragover {
  border-color: var(--fg);
  background: var(--accent-dim);
}
.hero-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.hero-icon {
  font-size: 1.4rem;
}
.hero-title {
  font-size: 1.15rem;
  font-weight: 800;
  letter-spacing: -0.02em;
}
.hero-desc {
  font-size: 0.82rem;
  color: var(--muted-fg);
}
.hero-desc code {
  font-family: var(--font-mono);
}
.hero-error {
  font-size: 0.75rem;
  color: var(--fg);
  font-weight: 600;
  margin-top: 0.2rem;
}
</style>
