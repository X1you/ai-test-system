<template>
  <div class="settings-view">
    <PageHeader title="设置" subtitle="系统配置与健康状态" />

    <!-- System config -->
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
        </div>
        <div class="config-block">
          <h3>Pipeline 默认值</h3>
          <dl class="config-dl">
            <div><dt>模式</dt><dd>{{ config.pipeline?.default_mode }}</dd></div>
            <div><dt>维度</dt><dd>{{ config.pipeline?.default_dimensions }}</dd></div>
            <div><dt>格式</dt><dd>{{ config.pipeline?.default_formats }}</dd></div>
            <div><dt>自检</dt><dd>{{ config.pipeline?.self_check ? '开启' : '关闭' }}</dd></div>
          </dl>
        </div>
        <div class="config-block">
          <h3>知识库</h3>
          <dl class="config-dl">
            <div><dt>启用</dt><dd>{{ config.knowledge_base?.enabled ? '是' : '否' }}</dd></div>
            <div><dt>Vault 路径</dt><dd class="mono">{{ config.knowledge_base?.vault_path }}</dd></div>
          </dl>
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
import { ref, onMounted } from 'vue'
import PageHeader from '../components/PageHeader.vue'
import { api } from '../composables/useApi'
import { useTheme } from '../composables/useTheme'

const { theme: currentTheme, setTheme } = useTheme()

const themeOptions = [
  { value: 'system', label: '跟随系统' },
  { value: 'light', label: '亮色' },
  { value: 'dark', label: '暗色' },
]

const config = ref(null)
const configLoading = ref(true)
const health = ref(null)

function healthDot(val) {
  if (val === 'ok' || val === 'disabled' || val === 'not_configured') return 'health-item__dot--ok'
  if (String(val).startsWith('error')) return 'health-item__dot--error'
  return 'health-item__dot--warn'
}

async function loadConfig() {
  configLoading.value = true
  try { config.value = await api.get('/config') } catch { /* ignore */ }
  configLoading.value = false
}

async function loadHealth() {
  try {
    const resp = await fetch('/health')
    health.value = await resp.json()
  } catch { health.value = null }
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

.valid-ok { color: var(--feedback-success-text); font-size: var(--text-sm); }
.valid-err { color: var(--feedback-error-text); font-size: var(--text-sm); }
.validation-errors {
  list-style: disc;
  padding-left: var(--space-xl);
  font-size: var(--text-sm);
  color: var(--feedback-error-text);
}

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
