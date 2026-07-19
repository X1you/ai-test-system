<template>
  <div class="settings-view">
    <PageHeader title="设置" subtitle="系统配置与健康状态" />

    <!-- System config (read-only) -->
    <section class="card" aria-label="系统配置">
      <h2 class="card__title">系统配置</h2>
      <div v-if="configLoading" class="loading-hint" role="status">加载中…</div>
      <div v-else-if="config" class="config-sections">
        <div class="config-block">
          <h3>LLM</h3>
          <dl class="config-dl">
            <div><dt>Provider</dt><dd>{{ config.llm?.provider }}</dd></div>
            <div><dt>Model</dt><dd>{{ config.llm?.model }}</dd></div>
            <div><dt>Base URL</dt><dd class="mono">{{ config.llm?.base_url }}</dd></div>
            <div><dt>API Key</dt><dd class="mono">{{ config.llm?.api_key }}</dd></div>
            <div><dt>Temperature</dt><dd class="tabular-nums">{{ config.llm?.temperature }}</dd></div>
          </dl>
          <p class="config-note">LLM 配置通过 config.yaml / 环境变量管理，不可在此修改</p>
        </div>
        <div v-if="config.validation" class="config-block">
          <h3>配置校验</h3>
          <p :class="config.validation.valid ? 'valid-ok' : 'valid-err'">
            {{ config.validation.valid ? '✓ 配置有效' : '✗ 配置存在问题' }}
          </p>
          <ul v-if="config.validation.errors?.length" class="validation-errors">
            <li v-for="(e, i) in config.validation.errors" :key="i">{{ e }}</li>
          </ul>
        </div>
      </div>
    </section>

    <!-- Editable: Pipeline defaults -->
    <section class="card" aria-label="Pipeline 默认值">
      <h2 class="card__title">Pipeline 默认值</h2>
      <div class="edit-form">
        <div class="form-row">
          <label class="form-label" for="cfg-mode">默认模式</label>
          <select id="cfg-mode" v-model="form.pipeline.default_mode" class="form-select">
            <option value="auto">自动（全自动执行）</option>
            <option value="semi">半自动（关键步骤暂停）</option>
            <option value="step">完整（每步暂停）</option>
          </select>
        </div>
        <fieldset class="form-fieldset">
          <legend>默认测试维度</legend>
          <div class="checkbox-grid">
            <label v-for="d in dimensionOptions" :key="d.value" class="checkbox-item">
              <input type="checkbox" :value="d.value" v-model="selectedDimensions" />
              <span>{{ d.label }}</span>
            </label>
          </div>
        </fieldset>
        <fieldset class="form-fieldset">
          <legend>默认输出格式</legend>
          <div class="checkbox-grid">
            <label v-for="f in formatOptions" :key="f.value" class="checkbox-item">
              <input type="checkbox" :value="f.value" v-model="selectedFormats" />
              <span>{{ f.label }}</span>
            </label>
          </div>
        </fieldset>
        <div class="form-row">
          <label class="form-label" for="cfg-selfcheck">自检</label>
          <label class="toggle-switch">
            <input id="cfg-selfcheck" type="checkbox" v-model="form.pipeline.self_check" />
            <span class="toggle-track"><span class="toggle-thumb"></span></span>
            <span>{{ form.pipeline.self_check ? '开启' : '关闭' }}</span>
          </label>
        </div>
      </div>
    </section>

    <!-- Editable: Knowledge base -->
    <section class="card" aria-label="知识库配置">
      <h2 class="card__title">知识库</h2>
      <div class="edit-form">
        <div class="form-row">
          <label class="form-label" for="cfg-kb-enabled">启用知识库</label>
          <label class="toggle-switch">
            <input id="cfg-kb-enabled" type="checkbox" v-model="form.knowledge_base.enabled" />
            <span class="toggle-track"><span class="toggle-thumb"></span></span>
            <span>{{ form.knowledge_base.enabled ? '已启用' : '已禁用' }}</span>
          </label>
        </div>
        <div class="form-row">
          <label class="form-label" for="cfg-kb-path">Vault 路径</label>
          <input id="cfg-kb-path" type="text" v-model="form.knowledge_base.vault_path"
                 class="form-input mono" placeholder="~/Documents/test-interview-kb" />
        </div>
      </div>
    </section>

    <!-- Editable: Output -->
    <section class="card" aria-label="输出配置">
      <h2 class="card__title">输出</h2>
      <div class="edit-form">
        <div class="form-row">
          <label class="form-label" for="cfg-output-dir">输出目录</label>
          <input id="cfg-output-dir" type="text" v-model="form.output.dir"
                 class="form-input mono" placeholder="./output" />
        </div>
      </div>
    </section>

    <!-- Save bar -->
    <div class="save-bar" role="status" aria-live="polite">
      <span v-if="saveMsg" :class="saveOk ? 'save-ok' : 'save-err'">{{ saveMsg }}</span>
      <button class="btn-save" :disabled="saving" @click="saveConfig">
        {{ saving ? '保存中…' : '保存配置' }}
      </button>
    </div>

    <!-- Health -->
    <section class="card" aria-label="健康检查">
      <h2 class="card__title">
        健康检查
        <button class="btn-refresh" aria-label="刷新健康状态" @click="loadHealth">刷新</button>
      </h2>
      <div v-if="health" class="health-grid">
        <div v-for="(val, key) in health.checks" :key="key" class="health-item">
          <span class="health-item__dot" :class="healthDot(val)" aria-hidden="true"></span>
          <span class="health-item__key">{{ key }}</span>
          <span class="health-item__val">{{ val }}</span>
        </div>
      </div>
      <p v-if="health" class="health-status">
        状态: <strong>{{ health.status }}</strong>
        <span class="tabular-nums"> · v{{ health.version }}</span>
      </p>
    </section>

    <!-- Appearance -->
    <section class="card" aria-label="外观">
      <h2 class="card__title">外观</h2>
      <div class="theme-options" role="radiogroup" aria-label="主题选择">
        <label v-for="t in themeOptions" :key="t.value" class="theme-option">
          <input type="radio" :value="t.value" v-model="currentTheme" name="theme" @change="setTheme(t.value)" />
          <span>{{ t.label }}</span>
        </label>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import PageHeader from '../components/PageHeader.vue'
import { api } from '../composables/useApi'
import { useTheme } from '../composables/useTheme'

const { theme: currentTheme, setTheme } = useTheme()

const themeOptions = [
  { value: 'system', label: '跟随系统' },
  { value: 'light', label: '亮色' },
  { value: 'dark', label: '暗色' },
]

const dimensionOptions = [
  { value: 'basic', label: '功能测试' },
  { value: 'api', label: 'API 测试' },
  { value: 'security', label: '安全测试' },
  { value: 'performance', label: '性能测试' },
  { value: 'compatibility', label: '兼容性测试' },
  { value: 'usability', label: '易用性测试' },
]

const formatOptions = [
  { value: 'excel', label: 'Excel (.xlsx)' },
  { value: 'json', label: 'JSON' },
  { value: 'xmind', label: 'XMind' },
]

const config = ref(null)
const configLoading = ref(true)
const health = ref(null)

// ─── 可编辑表单 ───
const form = reactive({
  pipeline: { default_mode: 'semi', self_check: true },
  knowledge_base: { enabled: true, vault_path: '' },
  output: { dir: './output' },
})
const selectedDimensions = ref(['basic'])
const selectedFormats = ref(['excel'])
const saving = ref(false)
const saveMsg = ref('')
const saveOk = ref(true)

function healthDot(val) {
  if (val === 'ok' || val === 'disabled' || val === 'not_configured') return 'health-item__dot--ok'
  if (String(val).startsWith('error')) return 'health-item__dot--error'
  return 'health-item__dot--warn'
}

async function loadConfig() {
  configLoading.value = true
  try {
    const c = await api.get('/config')
    config.value = c
    // 填充编辑表单
    if (c.pipeline) {
      form.pipeline.default_mode = c.pipeline.default_mode || 'semi'
      form.pipeline.self_check = !!c.pipeline.self_check
      // 维度/格式可能是逗号分隔字符串
      const dims = (c.pipeline.default_dimensions || 'basic').split(',').map(s => s.trim()).filter(Boolean)
      selectedDimensions.value = dims
      const fmts = (c.pipeline.default_formats || 'excel').split(',').map(s => s.trim()).filter(Boolean)
      selectedFormats.value = fmts
    }
    if (c.knowledge_base) {
      form.knowledge_base.enabled = !!c.knowledge_base.enabled
      form.knowledge_base.vault_path = c.knowledge_base.vault_path || ''
    }
  } catch { /* ignore */ }
  configLoading.value = false
}

async function loadHealth() {
  try {
    const resp = await fetch('/health')
    health.value = await resp.json()
  } catch { health.value = null }
}

async function saveConfig() {
  saving.value = true
  saveMsg.value = ''
  try {
    const body = {
      pipeline: {
        default_mode: form.pipeline.default_mode,
        default_dimensions: selectedDimensions.value.join(','),
        default_formats: selectedFormats.value.join(','),
        self_check: form.pipeline.self_check,
      },
      knowledge_base: {
        enabled: form.knowledge_base.enabled,
        vault_path: form.knowledge_base.vault_path,
      },
      output: {
        dir: form.output.dir,
      },
    }
    const res = await api.put('/config', { json: body })
    saveOk.value = true
    saveMsg.value = res.message || '保存成功'
    // 刷新只读配置
    await loadConfig()
  } catch (e) {
    saveOk.value = false
    saveMsg.value = e.message || '保存失败'
  }
  saving.value = false
}

onMounted(() => { loadConfig(); loadHealth() })
</script>

<style scoped>
.settings-view {
  max-width: 800px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-xl);
}

.card {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: var(--space-xl);
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
}
.card__title {
  font-size: var(--text-lg);
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.loading-hint { text-align: center; padding: var(--space-lg); color: var(--text-tertiary); }

.config-sections {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: var(--space-xl);
}

.config-block h3 {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: var(--space-sm);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.config-dl {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}
.config-dl > div {
  display: flex;
  justify-content: space-between;
  gap: var(--space-md);
  font-size: var(--text-sm);
}
.config-dl dt { color: var(--text-tertiary); }
.config-dl dd { color: var(--text-primary); text-align: right; min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.mono { font-family: var(--font-mono); font-size: var(--text-xs); }
.config-note { font-size: var(--text-xs); color: var(--text-tertiary); margin-top: var(--space-sm); }

.valid-ok { color: var(--feedback-success-text); font-size: var(--text-sm); }
.valid-err { color: var(--feedback-error-text); font-size: var(--text-sm); }
.validation-errors {
  list-style: disc;
  padding-left: var(--space-xl);
  font-size: var(--text-sm);
  color: var(--feedback-error-text);
}

/* ─── Edit form ─── */
.edit-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
}
.form-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
}
.form-label {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  flex-shrink: 0;
}
.form-select,
.form-input {
  flex: 1;
  max-width: 320px;
  padding: var(--space-sm) var(--space-md);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: var(--bg-inset);
  color: var(--text-primary);
  font-size: var(--text-sm);
}
.form-select:focus,
.form-input:focus {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}

.form-fieldset {
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: var(--space-md) var(--space-lg);
}
.form-fieldset legend {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  padding: 0 var(--space-xs);
}
.checkbox-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: var(--space-sm) var(--space-md);
}
.checkbox-item {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  font-size: var(--text-sm);
  cursor: pointer;
}

/* Toggle switch */
.toggle-switch {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  cursor: pointer;
  font-size: var(--text-sm);
  color: var(--text-secondary);
}
.toggle-switch input { position: absolute; opacity: 0; width: 0; height: 0; }
.toggle-track {
  width: 36px;
  height: 20px;
  border-radius: 10px;
  background: var(--bg-inset);
  border: 1px solid var(--border-default);
  position: relative;
  transition: background var(--duration-fast) var(--ease-out);
  flex-shrink: 0;
}
.toggle-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--text-tertiary);
  transition: transform var(--duration-fast) var(--ease-out), background var(--duration-fast) var(--ease-out);
}
.toggle-switch input:checked + .toggle-track {
  background: var(--accent);
  border-color: var(--accent);
}
.toggle-switch input:checked + .toggle-track .toggle-thumb {
  transform: translateX(16px);
  background: #fff;
}
.toggle-switch input:focus-visible + .toggle-track {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

/* Save bar */
.save-bar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-md);
  padding: var(--space-md) 0;
}
.save-ok { font-size: var(--text-sm); color: var(--feedback-success-text); }
.save-err { font-size: var(--text-sm); color: var(--feedback-error-text); }
.btn-save {
  padding: var(--space-sm) var(--space-xl);
  border: none;
  border-radius: var(--radius-md);
  background: var(--accent);
  color: var(--accent-contrast, #fff);
  font-size: var(--text-sm);
  font-weight: 600;
  cursor: pointer;
  transition: opacity var(--duration-fast) var(--ease-out);
}
.btn-save:hover { opacity: 0.85; }
.btn-save:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-save:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

/* Health */
.health-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-md);
}
.health-item {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  font-size: var(--text-sm);
  padding: var(--space-sm) var(--space-md);
  background: var(--bg-inset);
  border-radius: var(--radius-md);
}
.health-item__dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.health-item__dot--ok { background: var(--status-done); }
.health-item__dot--warn { background: var(--status-paused); }
.health-item__dot--error { background: var(--status-error); }
.health-item__key { color: var(--text-secondary); text-transform: capitalize; }
.health-item__val { color: var(--text-tertiary); font-size: var(--text-xs); margin-left: auto; }

.health-status { font-size: var(--text-sm); color: var(--text-secondary); }

.btn-refresh {
  padding: 2px 10px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--text-xs);
  transition: background var(--duration-fast) var(--ease-out);
}
.btn-refresh:hover { background: var(--bg-inset); }

/* Theme */
.theme-options { display: flex; gap: var(--space-lg); }
.theme-option {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  font-size: var(--text-base);
  cursor: pointer;
}
</style>
