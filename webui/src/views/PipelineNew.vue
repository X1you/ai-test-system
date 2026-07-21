<template>
  <div class="pipeline-new">
    <PageHeader title="新建任务" subtitle="上传需求文档，配置生成参数" back-to="/" />

    <div class="form-layout">
      <!-- Upload -->
      <section class="form-section">
        <h2 class="form-section__title">需求文档</h2>
        <FileDropZone
          accept=".md,.txt"
          hint="支持 .md / .txt，最大 10 MB"
          label="上传需求文档"
          @file="onFile"
        />
        <div v-if="selectedFile" class="file-chip">
          <span class="file-chip__name">{{ selectedFile.name }}</span>
          <span class="file-chip__size tabular-nums">{{ (selectedFile.size / 1024).toFixed(1) }} KB</span>
          <button class="file-chip__remove" aria-label="移除文件" @click="selectedFile = null">✕</button>
        </div>
        <p v-if="fileError" class="field-error" role="alert">{{ fileError }}</p>
      </section>

      <!-- Config -->
      <section class="form-section">
        <h2 class="form-section__title">生成配置</h2>
        <div class="config-grid">
          <!-- Mode -->
          <fieldset class="config-field">
            <legend>执行模式</legend>
            <label v-for="m in modes" :key="m.value" class="radio-label">
              <input type="radio" :value="m.value" v-model="form.mode" name="mode" />
              <span>{{ m.label }}</span>
              <span class="radio-desc">{{ m.desc }}</span>
            </label>
          </fieldset>

          <!-- Dimensions -->
          <fieldset class="config-field">
            <legend>测试维度</legend>
            <label v-for="d in dimensions" :key="d.value" class="checkbox-label">
              <input type="checkbox" :value="d.value" v-model="form.dimensions" />
              <span>{{ d.label }}</span>
            </label>
          </fieldset>

          <!-- Formats -->
          <fieldset class="config-field">
            <legend>输出格式</legend>
            <label v-for="f in formats" :key="f.value" class="checkbox-label">
              <input type="checkbox" :value="f.value" v-model="form.formats" />
              <span>{{ f.label }}</span>
            </label>
          </fieldset>
        </div>
      </section>

      <!-- Submit -->
      <section class="form-section">
        <button
          class="btn-submit"
          :disabled="!selectedFile || submitting || form.dimensions.length === 0 || form.formats.length === 0"
          @click="submit"
        >
          <span v-if="submitting" class="btn-spinner" aria-hidden="true"></span>
          {{ submitting ? '提交中…' : '启动生成' }}
        </button>
        <p v-if="submitError" class="field-error" role="alert">{{ submitError }}</p>
        <p class="concurrency-hint">并发上限 2 个任务</p>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import FileDropZone from '../components/FileDropZone.vue'
import { api } from '../composables/useApi'
import { useToast } from '../composables/useToast'

const toast = useToast()

const router = useRouter()

const selectedFile = ref(null)
const fileError = ref('')
const submitting = ref(false)
const submitError = ref('')

const form = ref({
  mode: 'semi',
  dimensions: ['positive', 'negative', 'boundary'],
  formats: ['excel', 'json'],
})

const modes = [
  { value: 'auto', label: '自动', desc: '全自动执行，不暂停' },
  { value: 'semi', label: '半自动', desc: '关键步骤暂停等待确认' },
  { value: 'step', label: '完整', desc: '每步暂停，逐步确认' },
]

const dimensions = [
  { value: 'positive', label: '正向测试' },
  { value: 'negative', label: '负向测试' },
  { value: 'boundary', label: '边界测试' },
  { value: 'exception', label: '异常测试' },
  { value: 'performance', label: '性能测试' },
  { value: 'security', label: '安全测试' },
]

const formats = [
  { value: 'excel', label: 'Excel (.xlsx)' },
  { value: 'json', label: 'JSON' },
  { value: 'xmind', label: 'XMind' },
]

function onFile(file) {
  fileError.value = ''
  if (!/\.(md|txt)$/i.test(file.name)) {
    fileError.value = '仅支持 .md / .txt 格式'
    return
  }
  if (file.size > 10 * 1024 * 1024) {
    fileError.value = '文件超过 10 MB 上限'
    return
  }
  selectedFile.value = file
}

async function submit() {
  if (!selectedFile.value) return
  submitting.value = true
  submitError.value = ''

  const formData = new FormData()
  formData.append('file', selectedFile.value)
  formData.append('mode', form.value.mode)
  formData.append('dimensions', form.value.dimensions.join(','))
  formData.append('formats', form.value.formats.join(','))

  try {
    const data = await api.upload('/pipeline/start', formData)
    toast.success('任务已启动')
    router.push(`/pipeline/${data.pipeline_id}`)
  } catch (e) {
    submitError.value = e.message || '启动失败'
    toast.error(`启动失败: ${e.message}`)
  } finally {
    submitting.value = false
  }
}

// 从后端加载 Pipeline 默认配置（与设置页同步）
onMounted(async () => {
  try {
    const c = await api.get('/config')
    if (c.pipeline) {
      const pipe = c.pipeline
      if (pipe.default_mode) form.value.mode = pipe.default_mode
      // 解析维度：可能是 "basic"/"all" 或逗号分隔的具体维度
      const dims = pipe.default_dimensions || 'basic'
      if (dims === 'basic') {
        form.value.dimensions = ['positive', 'negative', 'boundary', 'exception']
      } else if (dims === 'all') {
        form.value.dimensions = ['positive', 'negative', 'boundary', 'exception', 'performance', 'security']
      } else {
        form.value.dimensions = dims.split(',').map(s => s.trim()).filter(Boolean)
      }
      // 解析格式
      if (pipe.default_formats) {
        form.value.formats = pipe.default_formats.split(',').map(s => s.trim()).filter(Boolean)
      }
    }
  } catch { /* 静默降级使用内置默认值 */ }
})
</script>

<style scoped>
.pipeline-new {
  max-width: 720px;
  margin: 0 auto;
}

.form-layout {
  display: flex;
  flex-direction: column;
  gap: var(--space-xl);
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.form-section__title {
  font-size: var(--text-lg);
  font-weight: 600;
}
[data-theme="dark"] .form-section__title {
  text-shadow: var(--text-glow);
}

.file-chip {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-md);
  background: var(--bg-inset);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
}
.file-chip__name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-chip__size { color: var(--text-tertiary); font-size: var(--text-xs); }
.file-chip__remove {
  border: none;
  background: none;
  color: var(--text-tertiary);
  font-size: var(--text-base);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  transition: color var(--duration-fast) var(--ease-out);
}
.file-chip__remove:hover { color: var(--status-error); }

.field-error {
  color: var(--feedback-error-text);
  font-size: var(--text-sm);
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--space-lg);
}

.config-field {
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: var(--space-lg);
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}
[data-theme="dark"] .config-field {
  border-color: hsl(150 30% 12%);
}
[data-theme="dark"] .config-field legend {
  text-shadow: var(--text-glow);
}
.config-field legend {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-secondary);
  padding: 0 var(--space-xs);
}

.radio-label,
.checkbox-label {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  font-size: var(--text-sm);
  cursor: pointer;
  padding: var(--space-xs) 0;
}

.radio-desc {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  margin-left: auto;
}

.btn-submit {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-sm);
  width: 100%;
  padding: var(--space-md) var(--space-xl);
  background: var(--accent);
  color: var(--accent-text);
  border: none;
  border-radius: var(--radius-md);
  font-size: var(--text-lg);
  font-weight: 600;
  transition: background var(--duration-fast) var(--ease-out);
}
.btn-submit:hover:not(:disabled) { background: var(--accent-hover); }
[data-theme="dark"] .btn-submit:not(:disabled) {
  box-shadow: var(--shadow-accent);
}
[data-theme="dark"] .btn-submit:hover:not(:disabled) {
  box-shadow: var(--shadow-accent-lg);
}
.btn-submit:disabled {
  background: var(--border-default);
  color: var(--text-tertiary);
  cursor: not-allowed;
}

.btn-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid transparent;
  border-top-color: currentColor;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) {
  .btn-spinner { animation: none; }
}

.concurrency-hint {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  text-align: center;
}
</style>
