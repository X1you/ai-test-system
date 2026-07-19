<template>
  <div class="home-view">
    <h1>🚀 启动测试用例生成</h1>
    <p class="subtitle">上传需求文档，AI 自动生成结构化测试用例</p>

    <div class="upload-card">
      <div
        class="drop-zone"
        :class="{ dragging: isDragging }"
        @dragover.prevent="isDragging = true"
        @dragleave="isDragging = false"
        @drop.prevent="handleDrop"
      >
        <input
          ref="fileInput"
          type="file"
          accept=".md,.txt"
          style="display: none"
          @change="handleFileSelect"
        />
        <div class="drop-content">
          <span class="drop-icon">📄</span>
          <p>拖拽需求文档到此处，或 <a href="#" @click.prevent="fileInput?.click()">点击选择</a></p>
          <p class="hint">支持 .md / .txt 格式，最大 10MB</p>
        </div>
      </div>

      <div v-if="selectedFile" class="file-info">
        <span>📎 {{ selectedFile.name }} ({{ (selectedFile.size / 1024).toFixed(1) }} KB)</span>
        <button class="btn-remove" @click="selectedFile = null">✕</button>
      </div>

      <button
        class="btn-start"
        :disabled="!selectedFile || submitting"
        @click="startPipeline"
      >
        {{ submitting ? '提交中...' : '🚀 启动生成' }}
      </button>

      <div v-if="error" class="error-msg">{{ error }}</div>
      <div v-if="pipelineId" class="success-msg">
        ✅ 任务已启动！
        <router-link :to="`/pipelines`">查看任务列表 →</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const fileInput = ref(null)
const selectedFile = ref(null)
const isDragging = ref(false)
const submitting = ref(false)
const error = ref('')
const pipelineId = ref('')

function handleFileSelect(e) {
  const file = e.target.files?.[0]
  if (file) selectedFile.value = file
}

function handleDrop(e) {
  isDragging.value = false
  const file = e.dataTransfer.files?.[0]
  if (file && /\.(md|txt)$/i.test(file.name)) {
    selectedFile.value = file
  } else {
    error.value = '仅支持 .md / .txt 格式'
  }
}

async function startPipeline() {
  if (!selectedFile.value) return
  submitting.value = true
  error.value = ''
  pipelineId.value = ''

  const formData = new FormData()
  formData.append('file', selectedFile.value)
  formData.append('mode', 'full')
  formData.append('dimensions', 'functional,api,security,performance')
  formData.append('formats', 'excel,json')

  try {
    const resp = await fetch('/api/v1/pipeline/start', {
      method: 'POST',
      body: formData,
    })
    const data = await resp.json()
    if (resp.ok) {
      pipelineId.value = data.pipeline_id
    } else {
      error.value = data.detail || data.message || '启动失败'
    }
  } catch (e) {
    error.value = `网络错误: ${e.message}`
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.home-view { max-width: 640px; margin: 40px auto; }
h1 { font-size: 24px; margin-bottom: 8px; }
.subtitle { color: #666; margin-bottom: 24px; }
.upload-card {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}
.drop-zone {
  border: 2px dashed #ccc;
  border-radius: 8px;
  padding: 40px 20px;
  text-align: center;
  transition: all 0.2s;
  cursor: pointer;
}
.drop-zone.dragging { border-color: #1a73e8; background: #e8f0fe; }
.drop-icon { font-size: 32px; display: block; margin-bottom: 8px; }
.hint { font-size: 12px; color: #999; margin-top: 4px; }
.file-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12px;
  padding: 8px 12px;
  background: #f8f9fa;
  border-radius: 6px;
  font-size: 14px;
}
.btn-remove { background: none; border: none; cursor: pointer; font-size: 16px; color: #999; }
.btn-start {
  width: 100%;
  margin-top: 16px;
  padding: 12px;
  background: #1a73e8;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  cursor: pointer;
  transition: background 0.2s;
}
.btn-start:hover:not(:disabled) { background: #1557b0; }
.btn-start:disabled { background: #ccc; cursor: not-allowed; }
.error-msg { margin-top: 12px; color: #d93025; font-size: 14px; }
.success-msg { margin-top: 12px; color: #188038; font-size: 14px; }
.success-msg a { color: #1a73e8; }
</style>
