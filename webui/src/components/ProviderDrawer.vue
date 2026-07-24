<script setup lang="ts">
/**
 * ProviderDrawer — 抽屉式 Provider 编辑表单
 *
 * 字段分 3 步（一个表单内分段）：
 *   1. 基础信息：name / provider
 *   2. 协议选择：ProtocolSelector（3 大卡片单选）
 *   3. 连接信息（按协议动态展示字段）：
 *      - openai_compatible: base_url / api_key / model / temperature / max_tokens
 *      - anthropic:         base_url / api_key / model / temperature / max_tokens
 *      - custom_http:       endpoint / method / headers / body_template / response_path / api_key(可选) / model
 *
 * 关键交互：
 *   - 协议切换保留已填字段（不重置表单）
 *   - [测试连接] 按钮：调 /config/test_provider，结果以三色 toast 就地反馈
 *   - [保存] 按钮：调 /config PUT，成功后关闭抽屉
 *   - 必填校验：name / model 必填；OpenAI/Anthropic 必填 api_key
 */

import { computed, onUnmounted, reactive, ref, watch } from 'vue'

import { useToastStore } from '@/composables/useToast'
import {
  LLM_PROVIDER_EMPTY,
  type LLMProvider,
  type LLMProtocol,
  type LLMServerCheck,
} from '@/types/config'
import ProtocolSelector from './ProtocolSelector.vue'

const props = defineProps<{
  /** 编辑模式传入的 provider；新增模式传 null */
  provider: LLMProvider | null
  open: boolean
  saving?: boolean
  /** 复用 config store 的 testProvider（不依赖 store 本身） */
  onTest: (p: LLMProvider, timeout?: number) => Promise<LLMServerCheck>
  onSave: (p: LLMProvider) => Promise<void>
}>()

const emit = defineEmits<{
  (e: 'update:open', v: boolean): void
  (e: 'tested', result: LLMServerCheck): void
}>()

const toastStore = useToastStore()
const toast = {
  success: (m: string) => toastStore.success(m),
  error: (m: string) => toastStore.error(m),
}

// ─── 表单状态 ───
const form = reactive<LLMProvider>({ ...LLM_PROVIDER_EMPTY })
const isEdit = ref(false)
const testing = ref(false)
const lastResult = ref<LLMServerCheck | null>(null)
const headersText = ref('{}')
const tagInput = ref('')
const tagInputEl = ref<HTMLInputElement | null>(null)

// 当 drawer 打开 + provider 变化时，同步表单
watch(
  () => [props.open, props.provider] as const,
  ([open, p]) => {
    if (open) {
      if (p) {
        Object.assign(form, { ...LLM_PROVIDER_EMPTY, ...p })
        isEdit.value = true
      } else {
        Object.assign(form, { ...LLM_PROVIDER_EMPTY })
        isEdit.value = false
      }
      headersText.value = JSON.stringify(form.headers || {}, null, 2)
      lastResult.value = null
    }
  },
  { immediate: true },
)

// 协议切换 → 保留已填字段（仅刷新默认值）
watch(
  () => form.protocol,
  (newP, oldP) => {
    if (!oldP) return
    // 协议切换时仅重置"协议特有字段"
    if (newP === 'custom_http' && oldP !== 'custom_http') {
      form.body_template = form.body_template || '{"prompt":"{{prompt}}"}'
      form.response_path = form.response_path || 'text'
    }
  },
)

// ─── 校验 ───
const errors = computed(() => {
  const e: Record<string, string> = {}
  if (!form.name.trim()) e.name = '请输入 Provider 名称'
  if (form.protocol !== 'custom_http' && !form.api_key.trim()) {
    e.api_key = 'OpenAI / Anthropic 协议需要 API Key'
  }
  if (!form.model.trim()) e.model = '请输入模型名'
  if (form.protocol === 'custom_http' && !form.endpoint.trim() && !form.base_url.trim()) {
    e.endpoint = '请输入 endpoint（或 base_url）'
  }
  return e
})

const canSave = computed(() => Object.keys(errors.value).length === 0)

// ─── 操作 ───

function close() {
  emit('update:open', false)
}

// ESC 关闭抽屉（a11y：模态/抽屉必须支持 ESC 关闭）
function onEsc(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.open) close()
}
watch(
  () => props.open,
  (open) => {
    if (open) window.addEventListener('keydown', onEsc)
    else window.removeEventListener('keydown', onEsc)
  },
)
onUnmounted(() => window.removeEventListener('keydown', onEsc))

function parseHeaders() {
  try {
    const obj = JSON.parse(headersText.value || '{}')
    if (typeof obj !== 'object' || Array.isArray(obj)) {
      toast.error('Headers 必须是 JSON 对象')
      return false
    }
    form.headers = obj
    return true
  } catch (e: any) {
    toast.error(`Headers JSON 解析失败: ${e.message}`)
    return false
  }
}

// ─── V3: Tags 编辑 ───
function addTag() {
  const raw = tagInput.value.trim()
  if (!raw) return
  // 支持逗号/空格分隔批量输入
  const parts = raw.split(/[,\s]+/).map((s) => s.trim()).filter(Boolean)
  const existing = new Set(form.tags.map((t) => t.toLowerCase()))
  for (const p of parts) {
    if (!existing.has(p.toLowerCase()) && form.tags.length < 16) {
      form.tags.push(p)
      existing.add(p.toLowerCase())
    }
  }
  tagInput.value = ''
}

function removeTag(idx: number) {
  form.tags.splice(idx, 1)
}

function onTagKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault()
    addTag()
  } else if (e.key === 'Backspace' && !tagInput.value && form.tags.length > 0) {
    // Backspace 删除最后一个
    form.tags.pop()
  }
}

function focusTagInput() {
  tagInputEl.value?.focus()
}

async function handleTest() {
  if (!parseHeaders()) return
  testing.value = true
  lastResult.value = null
  try {
    const r = await props.onTest({ ...form }, 10)
    lastResult.value = r
    emit('tested', r)
    if (r.ok) {
      toast.success(`连接成功（${r.latency_ms}ms）— ${r.provider} / ${r.model}`)
    } else {
      toast.error(`连接失败：${r.status}`)
    }
  } catch (e: any) {
    toast.error(`测试请求失败：${e?.message || '未知错误'}`)
  } finally {
    testing.value = false
  }
}

async function handleSave() {
  if (!canSave.value) {
    Object.values(errors.value).forEach((m) => toast.error(m))
    return
  }
  if (!parseHeaders()) return
  try {
    await props.onSave({ ...form })
    close()
  } catch {
    // 错误已由 store 暴露给 toast，无需再 toast
  }
}
</script>

<template>
  <Transition name="drawer">
    <div v-if="open" class="drawer-mask" @click.self="close" role="presentation">
      <aside
        class="drawer"
        role="dialog"
        aria-modal="true"
        :aria-label="isEdit ? `编辑 ${form.name}` : '新增 Provider'"
      >
        <!-- Header -->
        <header class="dr-header">
          <h2 class="dr-title">{{ isEdit ? '编辑 Provider' : '新增 Provider' }}</h2>
          <button type="button" class="dr-close" aria-label="关闭" @click="close">×</button>
        </header>

        <!-- Body -->
        <div class="dr-body">
          <!-- 步骤 1：基础信息 -->
          <section class="dr-section">
            <h3 class="dr-section-title">1. 基础信息</h3>
            <div class="dr-field">
              <label for="pd-name" class="dr-label">
                名称（别名）
                <span class="dr-required">*</span>
              </label>
              <input
                id="pd-name"
                v-model="form.name"
                type="text"
                class="dr-input"
                placeholder="如 glm / deepseek / claude"
                :aria-invalid="!!errors.name"
                maxlength="64"
              />
              <p v-if="errors.name" class="dr-error">{{ errors.name }}</p>
              <p v-else class="dr-hint">唯一标识，用于在列表中显示</p>
            </div>
            <div class="dr-field">
              <label for="pd-provider" class="dr-label">Vendor</label>
              <input
                id="pd-provider"
                v-model="form.provider"
                type="text"
                class="dr-input"
                placeholder="如 bigmodel / anthropic（可与名称相同）"
                maxlength="64"
              />
              <p class="dr-hint">统计维度（默认与名称一致）</p>
            </div>
            <div class="dr-field">
              <label for="pd-tags" class="dr-label">标签 (Tags)</label>
              <div class="dr-tags-input" @click="focusTagInput">
                <span
                  v-for="(t, i) in form.tags"
                  :key="`${t}-${i}`"
                  class="dr-tag-chip"
                >
                  {{ t }}
                  <button
                    type="button"
                    class="dr-tag-remove"
                    :aria-label="`移除标签 ${t}`"
                    @click.stop="removeTag(i)"
                  >
                    ×
                  </button>
                </span>
                <input
                  id="pd-tags"
                  ref="tagInputEl"
                  v-model="tagInput"
                  type="text"
                  class="dr-tag-field"
                  :placeholder="form.tags.length ? '' : '输入标签后回车（如 production / 便宜 / 备用）'"
                  :maxlength="32"
                  @keydown="onTagKeydown"
                  @blur="addTag"
                />
              </div>
              <p class="dr-hint">回车 / 逗号添加；Backspace 删除末尾；最多 16 个</p>
            </div>
          </section>

          <!-- 步骤 2：协议选择 -->
          <section class="dr-section">
            <h3 class="dr-section-title">2. 协议</h3>
            <ProtocolSelector v-model="form.protocol" />
          </section>

          <!-- 步骤 3：连接信息（按协议动态字段） -->
          <section class="dr-section">
            <h3 class="dr-section-title">3. 连接信息</h3>

            <!-- OpenAI 兼容 / Anthropic：base_url + api_key + model -->
            <template v-if="form.protocol === 'openai_compatible' || form.protocol === 'anthropic'">
              <div class="dr-field">
                <label for="pd-base-url" class="dr-label">Base URL</label>
                <input
                  id="pd-base-url"
                  v-model="form.base_url"
                  type="text"
                  class="dr-input"
                  :placeholder="
                    form.protocol === 'anthropic'
                      ? 'https://api.anthropic.com'
                      : 'https://api.openai.com/v1'
                  "
                />
                <p class="dr-hint">不含 <code>/chat/completions</code> 尾巴（会自动剥离）</p>
              </div>
              <div class="dr-field">
                <label for="pd-api-key" class="dr-label">
                  API Key
                  <span class="dr-required">*</span>
                </label>
                <input
                  id="pd-api-key"
                  v-model="form.api_key"
                  type="password"
                  class="dr-input"
                  :placeholder="isEdit && form.api_key?.includes('...') ? '留空保留原 Key，输入则覆盖' : '请输入 API Key'"
                  :aria-invalid="!!errors.api_key"
                  autocomplete="off"
                />
                <p v-if="errors.api_key" class="dr-error">{{ errors.api_key }}</p>
                <p v-else-if="isEdit && form.api_key?.includes('...')" class="dr-hint">
                  留空将保留原 Key；输入新值会覆盖
                </p>
              </div>
              <div class="dr-row">
                <div class="dr-field" style="flex: 2">
                  <label for="pd-model" class="dr-label">
                    模型
                    <span class="dr-required">*</span>
                  </label>
                  <input
                    id="pd-model"
                    v-model="form.model"
                    type="text"
                    class="dr-input"
                    placeholder="如 glm-4.7-flash / deepseek-chat / gpt-4o"
                    :aria-invalid="!!errors.model"
                  />
                  <p v-if="errors.model" class="dr-error">{{ errors.model }}</p>
                </div>
                <div class="dr-field" style="flex: 1">
                  <label for="pd-temp" class="dr-label">Temperature</label>
                  <input
                    id="pd-temp"
                    v-model.number="form.temperature"
                    type="number"
                    step="0.05"
                    min="0"
                    max="2"
                    class="dr-input"
                  />
                </div>
              </div>
              <div class="dr-row">
                <div class="dr-field" style="flex: 1">
                  <label for="pd-max" class="dr-label">Max Tokens</label>
                  <input
                    id="pd-max"
                    v-model.number="form.max_tokens"
                    type="number"
                    step="256"
                    min="1"
                    class="dr-input"
                  />
                </div>
                <div class="dr-field" style="flex: 1">
                  <label for="pd-timeout" class="dr-label">Timeout (s)</label>
                  <input
                    id="pd-timeout"
                    v-model.number="form.timeout"
                    type="number"
                    step="10"
                    min="1"
                    class="dr-input"
                  />
                </div>
              </div>
            </template>

            <!-- Custom HTTP：endpoint + method + body_template + response_path -->
            <template v-else>
              <div class="dr-field">
                <label for="pd-endpoint" class="dr-label">
                  Endpoint
                  <span class="dr-required">*</span>
                </label>
                <input
                  id="pd-endpoint"
                  v-model="form.endpoint"
                  type="text"
                  class="dr-input"
                  placeholder="https://your-gateway.local/v1/infer"
                  :aria-invalid="!!errors.endpoint"
                />
                <p v-if="errors.endpoint" class="dr-error">{{ errors.endpoint }}</p>
              </div>
              <div class="dr-row">
                <div class="dr-field" style="flex: 1">
                  <label for="pd-method" class="dr-label">HTTP Method</label>
                  <select id="pd-method" v-model="form.method" class="dr-input">
                    <option value="POST">POST</option>
                    <option value="PUT">PUT</option>
                    <option value="GET">GET</option>
                  </select>
                </div>
                <div class="dr-field" style="flex: 1">
                  <label for="pd-model-2" class="dr-label">模型名（可空）</label>
                  <input
                    id="pd-model-2"
                    v-model="form.model"
                    type="text"
                    class="dr-input"
                    placeholder="custom-model"
                  />
                </div>
              </div>
              <div class="dr-field">
                <label for="pd-headers" class="dr-label">Headers (JSON)</label>
                <textarea
                  id="pd-headers"
                  v-model="headersText"
                  class="dr-textarea"
                  rows="3"
                  placeholder='{"X-Custom-Header": "value"}'
                />
                <p class="dr-hint">JSON 对象，会与 content-type / authorization 合并</p>
              </div>
              <div class="dr-field">
                <label for="pd-body" class="dr-label">Body Template (JSON)</label>
                <textarea
                  id="pd-body"
                  v-model="form.body_template"
                  class="dr-textarea"
                  rows="6"
                  placeholder='{"model":"{{model}}","messages":{{messages}}}'
                />
                <p class="dr-hint">
                  支持占位符：<code v-pre>{{prompt}}</code> / <code v-pre>{{system}}</code> /
                  <code v-pre>{{model}}</code> / <code v-pre>{{messages}}</code>
                </p>
              </div>
              <div class="dr-field">
                <label for="pd-path" class="dr-label">Response Path</label>
                <input
                  id="pd-path"
                  v-model="form.response_path"
                  type="text"
                  class="dr-input"
                  placeholder="data.choices[0].message.content"
                />
                <p class="dr-hint">从响应 JSON 取文本的路径（点号 / [index]）</p>
              </div>
            </template>

            <!-- 测试结果内嵌提示 -->
            <div v-if="lastResult" class="dr-test-result" :class="lastResult.ok ? 'is-ok' : 'is-degraded'">
              <span class="dr-test-icon">{{ lastResult.ok ? '✓' : '✗' }}</span>
              <div>
                <div class="dr-test-title">
                  {{ lastResult.ok ? '连接成功' : '连接失败' }}
                  <span class="dr-test-latency">{{ lastResult.latency_ms }}ms</span>
                </div>
                <div class="dr-test-detail">
                  <code>{{ lastResult.status }}</code>
                </div>
              </div>
            </div>
          </section>
        </div>

        <!-- Footer -->
        <footer class="dr-footer">
          <button type="button" class="dr-btn dr-btn-secondary" @click="close">取消</button>
          <button
            type="button"
            class="dr-btn dr-btn-test"
            :disabled="testing"
            @click="handleTest"
          >
            {{ testing ? '测试中…' : '测试连接' }}
          </button>
          <button
            type="button"
            class="dr-btn dr-btn-primary"
            :disabled="!canSave || saving"
            @click="handleSave"
          >
            {{ saving ? '保存中…' : '保存' }}
          </button>
        </footer>
      </aside>
    </div>
  </Transition>
</template>

<style scoped>
.drawer-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 100;
  display: flex;
  justify-content: flex-end;
}
.drawer {
  width: 600px;
  max-width: 100vw;
  height: 100%;
  background: var(--bg);
  display: flex;
  flex-direction: column;
  border-left: 1px solid var(--border);
  box-shadow: -8px 0 24px rgba(0, 0, 0, 0.12);
}
.dr-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border);
}
.dr-title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 700;
}
.dr-close {
  width: 1.8rem;
  height: 1.8rem;
  font-size: 1.4rem;
  line-height: 1;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--muted-fg);
  cursor: pointer;
}
.dr-close:hover { color: var(--fg); border-color: var(--fg); }

.dr-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.dr-section { display: flex; flex-direction: column; gap: 0.85rem; }
.dr-section-title {
  margin: 0;
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--muted-fg);
}

.dr-row { display: flex; gap: 0.85rem; }

.dr-field { display: flex; flex-direction: column; gap: 0.35rem; }
.dr-label {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--fg);
  display: flex;
  align-items: center;
  gap: 0.25rem;
}
.dr-required { color: #dc2626; }
.dr-input,
.dr-textarea {
  padding: 0.55rem 0.7rem;
  font-size: 0.85rem;
  font-family: inherit;
  color: var(--fg);
  background: var(--panel-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  outline: none;
  transition: border-color var(--duration-fast) var(--ease);
}
.dr-input:focus,
.dr-textarea:focus { border-color: var(--fg); }
.dr-input[aria-invalid="true"] { border-color: #dc2626; }
.dr-textarea {
  font-family: var(--font-mono, monospace);
  resize: vertical;
  min-height: 4rem;
}
.dr-hint {
  margin: 0;
  font-size: 0.7rem;
  color: var(--muted-fg);
}
.dr-hint code,
.dr-error code {
  font-family: var(--font-mono, monospace);
  font-size: 0.7rem;
  background: var(--hover-bg);
  padding: 0 0.25rem;
  border-radius: 2px;
}
.dr-error { margin: 0; font-size: 0.7rem; color: #dc2626; }

/* V3: Tags 编辑器 */
.dr-tags-input {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
  padding: 0.4rem 0.55rem;
  min-height: 2.6rem;
  background: var(--panel-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  cursor: text;
  transition: border-color var(--duration-fast) var(--ease);
}
.dr-tags-input:focus-within { border-color: var(--fg); }
.dr-tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.15rem 0.45rem;
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--fg);
  background: var(--hover-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-full);
  user-select: none;
}
.dr-tag-remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 0.9rem;
  height: 0.9rem;
  font-size: 0.8rem;
  line-height: 1;
  background: transparent;
  border: none;
  color: var(--muted-fg);
  cursor: pointer;
  border-radius: var(--radius-full);
  padding: 0;
}
.dr-tag-remove:hover { color: #dc2626; background: var(--bg); }
.dr-tag-field {
  flex: 1;
  min-width: 8rem;
  padding: 0.15rem 0;
  font-size: 0.82rem;
  font-family: inherit;
  color: var(--fg);
  background: transparent;
  border: none;
  outline: none;
}
.dr-tag-field::placeholder { color: var(--muted-fg); }

.dr-test-result {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  margin-top: 0.5rem;
  padding: 0.75rem 1rem;
  border-radius: var(--radius-sm);
}
.dr-test-result.is-ok {
  background: #d1fae5;
  border: 1px solid #10b981;
  color: #065f46;
}
.dr-test-result.is-degraded {
  background: #fef3c7;
  border: 1px solid #f59e0b;
  color: #92400e;
}
.dr-test-icon {
  font-size: 1.2rem;
  font-weight: 700;
  line-height: 1;
}
.dr-test-title {
  font-size: 0.85rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.dr-test-latency {
  font-size: 0.7rem;
  font-weight: 500;
  opacity: 0.85;
}
.dr-test-detail {
  font-size: 0.72rem;
  margin-top: 0.2rem;
}
.dr-test-detail code {
  font-family: var(--font-mono, monospace);
  font-size: 0.7rem;
  word-break: break-all;
}

.dr-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
  padding: 0.9rem 1.25rem;
  border-top: 1px solid var(--border);
  background: var(--panel-bg);
}
.dr-btn {
  padding: 0.5rem 1rem;
  font-size: 0.82rem;
  font-weight: 600;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  background: var(--bg);
  color: var(--fg);
  transition: all var(--duration-fast) var(--ease);
}
.dr-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.dr-btn-secondary { background: transparent; }
.dr-btn-test { border-color: var(--muted-fg); }
.dr-btn-test:hover:not(:disabled) { border-color: var(--fg); }
.dr-btn-primary {
  background: var(--fg);
  color: var(--bg);
  border-color: var(--fg);
}
.dr-btn-primary:hover:not(:disabled) { opacity: 0.85; }

/* Drawer transition */
.drawer-enter-active,
.drawer-leave-active { transition: opacity var(--duration-fast) var(--ease); }
.drawer-enter-active .drawer,
.drawer-leave-active .drawer { transition: transform var(--duration-base) var(--ease); }
.drawer-enter-from,
.drawer-leave-to { opacity: 0; }
.drawer-enter-from .drawer,
.drawer-leave-to .drawer { transform: translateX(100%); }

@media (max-width: 640px) {
  .drawer { width: 100vw; }
  .dr-row { flex-direction: column; }
}
</style>
