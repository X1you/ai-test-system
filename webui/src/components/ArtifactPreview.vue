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
      <!-- Markdown（safeHtml 已净化，防御 XSS） -->
      <div v-else-if="data?.type === 'markdown'" class="preview-md" v-html="safeHtml"></div>
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
import { ref, watch, computed } from 'vue'
import { api } from '../composables/useApi'

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

// ─── XSS 防护：对后端返回的 Markdown HTML 做客户端净化 ───
// 使用 DOMParser（浏览器原生，零依赖）剥离危险节点和属性：
//   <script> / <iframe> / <object> / <embed> → 整体删除
//   on* 事件属性（onclick, onerror...）→ 删除
//   href/src 中的 javascript: 协议 → 重写为 #
//   style 属性中的 expression()/url(javascript:..) → 删除整个 style
// 注意：v-html 渲染的 data.html 来自后端 markdown→html，无法假设后端已净化，
//       客户端必须做防御性净化（纵深防御原则）。
const SANITIZE_TAGS = ['script', 'iframe', 'object', 'embed', 'link', 'meta', 'base', 'form', 'input', 'button', 'textarea', 'select']
const SANITIZE_ATTR_RE = /^on/i
const DANGER_URL_RE = /^\s*javascript:/i
const DANGER_CSS_RE = /expression\s*\(|url\s*\(\s*['"]?\s*javascript:/i

function sanitizeHtml(html) {
  if (!html || typeof html !== 'string') return ''
  if (typeof window === 'undefined' || typeof DOMParser === 'undefined') return html
  const doc = new DOMParser().parseFromString(html, 'text/html')
  // 删除危险标签（含子节点）
  doc.querySelectorAll(SANITIZE_TAGS.join(',')).forEach((el) => el.remove())
  // 清理危险属性
  doc.querySelectorAll('*').forEach((el) => {
    const attrs = [...el.attributes]
    for (const attr of attrs) {
      const name = attr.name
      const val = attr.value
      // on* 事件属性
      if (SANITIZE_ATTR_RE.test(name)) { el.removeAttribute(name); continue }
      // javascript: 协议
      if ((name === 'href' || name === 'src') && DANGER_URL_RE.test(val)) {
        el.setAttribute(name, '#'); continue
      }
      // style 中的 expression / url(javascript:)
      if (name === 'style' && DANGER_CSS_RE.test(val)) { el.removeAttribute(name); continue }
    }
  })
  return doc.body ? doc.body.innerHTML : ''
}

// 净化后的 HTML（computed，data 变化时自动重算）
const safeHtml = computed(() => {
  if (data.value?.type === 'markdown' && data.value.html) {
    return sanitizeHtml(data.value.html)
  }
  return ''
})

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
    // 使用 api 封装（自动注入 JWT Authorization header + 401 处理），
    // 原裸 fetch 不带认证头，会导致预览接口 401。
    data.value = await api.get(`/pipeline/${props.pipelineId}/preview/${props.artifactName}`)
  } catch (e) {
    error.value = `预览加载失败: ${e.message}`
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.preview-modal {
  width: min(90vw, 840px);
  max-height: 80vh;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-xl);
  background: var(--bg-surface);
  color: var(--text-primary);
  padding: 0;
  overscroll-behavior: contain;
  box-shadow: var(--shadow-xl);
}
[data-theme="dark"] .preview-modal {
  border-color: hsl(0 0% 18%);
  box-shadow: var(--shadow-xl), 0 0 16px hsl(0 0% 50% / 0.1);
}
[data-theme="dark"] .preview-modal__title {
  text-shadow: var(--text-glow);
}

.preview-modal::backdrop {
  background: hsl(0 0% 0% / 0.45);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}
[data-theme="dark"] .preview-modal::backdrop {
  background: hsl(0 0% 0% / 0.7);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
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
  font-weight: 700;
  letter-spacing: -0.01em;
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
  transition: background var(--duration-normal) var(--ease-out),
              color var(--duration-normal) var(--ease-out),
              transform var(--duration-normal) var(--ease-out);
}
.preview-modal__close:hover {
  background: var(--bg-inset);
  color: var(--text-primary);
  transform: rotate(90deg);
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
  font-weight: 700;
}
.preview-md :deep(p) { margin: var(--space-sm) 0; }
.preview-md :deep(table) {
  border: 1px solid var(--border-default);
  margin: var(--space-md) 0;
  border-radius: var(--radius-sm);
  overflow: hidden;
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
  padding: 1px 5px;
  border-radius: var(--radius-sm);
}
.preview-md :deep(pre) {
  background: var(--bg-inset);
  padding: var(--space-md);
  border-radius: var(--radius-md);
  overflow-x: auto;
}
[data-theme="dark"] .preview-md :deep(pre) {
  border: 1px solid hsl(0 0% 12%);
}
[data-theme="dark"] .preview-md :deep(code) {
  color: hsl(0 0% 65%);
  text-shadow: 0 0 4px hsl(0 0% 50% / 0.2);
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
  font-weight: 700;
}
</style>
