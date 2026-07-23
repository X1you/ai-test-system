<template>
  <div class="knowledge-view">
    <PageHeader title="知识库" subtitle="配置、搜索与管理测试知识" />

    <!-- Tabs -->
    <div class="tabs" role="tablist" aria-label="知识库功能">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        class="tabs__btn"
        :class="{ 'tabs__btn--active': activeTab === tab.id }"
        role="tab"
        :id="`tab-${tab.id}`"
        :aria-selected="activeTab === tab.id"
        :aria-controls="`panel-${tab.id}`"
        @click="activeTab = tab.id"
      >{{ tab.label }}</button>
    </div>

    <!-- Config Tab -->
    <section v-if="activeTab === 'config'" id="panel-config" class="tab-panel" role="tabpanel" aria-labelledby="tab-config">
      <div class="card-grid">
        <!-- Current config -->
        <div class="card">
          <h2 class="card__title">当前生效配置</h2>
          <div v-if="currentConfig?.configured" class="config-info">
            <p><strong>Provider:</strong> {{ currentConfig.provider_type }}</p>
            <p v-if="currentConfig.connection_url"><strong>URL:</strong> {{ currentConfig.connection_url }}</p>
            <p v-if="currentConfig.vault_path"><strong>Vault:</strong> {{ currentConfig.vault_path }}</p>
            <p><strong>Token:</strong> {{ currentConfig.auth_token_masked }}</p>
            <p><strong>更新时间:</strong> {{ currentConfig.updated_at }}</p>
          </div>
          <p v-else class="warn-hint">未配置（Dummy 模式）</p>
        </div>

        <!-- Stats -->
        <div class="card">
          <h2 class="card__title">知识库统计</h2>
          <div v-if="status">
            <p v-if="!status.enabled" class="warn-hint">知识库未启用</p>
            <template v-else>
              <p class="stat-big tabular-nums">{{ status.total }} <span class="stat-unit">条目</span></p>
              <div v-if="status.categories" class="cat-badges">
                <span v-for="(count, cat) in status.categories" :key="cat" class="cat-badge">
                  {{ cat }}: {{ count }}
                </span>
              </div>
            </template>
          </div>
        </div>
      </div>

      <!-- Config form -->
      <div class="card">
        <h2 class="card__title">动态配置</h2>
        <p class="card__desc">保存后立即热切换生效</p>
        <div class="form-grid">
          <div class="form-group">
            <label for="kb-provider">Provider 类型</label>
            <select id="kb-provider" v-model="form.provider_type">
              <option value="mcp_filesystem">MCP Filesystem（本地 Vault）</option>
              <option value="obsidian_api">Obsidian API（远程）</option>
            </select>
          </div>
          <div v-if="form.provider_type === 'obsidian_api'" class="form-group">
            <label for="kb-url">连接 URL</label>
            <input id="kb-url" v-model="form.connection_url" placeholder="http://127.0.0.1:27124" spellcheck="false" autocomplete="off" />
          </div>
          <div v-if="form.provider_type === 'obsidian_api'" class="form-group">
            <label for="kb-token">Auth Token</label>
            <input id="kb-token" v-model="form.auth_token" type="password" placeholder="可选" autocomplete="off" />
          </div>
          <div v-if="form.provider_type === 'mcp_filesystem'" class="form-group">
            <label for="kb-vault">Vault 路径</label>
            <input id="kb-vault" v-model="form.vault_path" placeholder="/path/to/vault" spellcheck="false" autocomplete="off" />
          </div>
        </div>
        <button class="btn-primary" :disabled="saving" @click="saveConfig">
          {{ saving ? '保存中…' : '保存并热切换' }}
        </button>
        <p v-if="configMsg" :class="['msg', configMsgOk ? 'msg--ok' : 'msg--err']" role="status" aria-live="polite">{{ configMsg }}</p>
      </div>
    </section>

    <!-- Search Tab -->
    <section v-if="activeTab === 'search'" id="panel-search" class="tab-panel" role="tabpanel" aria-labelledby="tab-search">
      <div class="search-bar">
        <input
          v-model="searchQuery"
          type="search"
          class="search-bar__input"
          placeholder="搜索知识库…"
          aria-label="搜索知识库"
          spellcheck="false"
          @keydown.enter="doSearch(1)"
        />
        <button class="btn-primary" @click="doSearch(1)">搜索</button>
      </div>
      <div v-if="searchLoading" class="loading-hint" role="status">搜索中…</div>
      <EmptyState v-else-if="searchResults.length === 0 && searchDone" message="未找到匹配结果" />
      <template v-else>
        <ul class="search-results">
          <li v-for="(r, i) in searchResults" :key="`${searchPage}-${i}`" class="search-result">
            <h3 class="search-result__title">{{ r.title || r.name || '未命名' }}</h3>
            <p v-if="r.category" class="search-result__cat">{{ r.category }}</p>
            <p class="search-result__snippet">{{ r.snippet || r.content?.slice(0, 200) || '' }}</p>
          </li>
        </ul>
        <div class="search-footer">
          <span class="search-footer__total">共 {{ searchTotal }} 条结果</span>
          <Pagination :page="searchPage" :pages="searchPages" @change="doSearch" />
        </div>
      </template>
    </section>

    <!-- Import Tab -->
    <section v-if="activeTab === 'import'" id="panel-import" class="tab-panel" role="tabpanel" aria-labelledby="tab-import">
      <div class="card">
        <h2 class="card__title">Excel 用例回灌</h2>
        <p class="card__desc">上传 .xlsx 文件，导入历史用例到知识库</p>
        <FileDropZone
          accept=".xlsx,.xls"
          hint="支持 .xlsx / .xls，最大 10 MB"
          label="上传 Excel 用例文件"
          compact
          @file="importExcel"
        />
        <p v-if="importMsg" :class="['msg', importOk ? 'msg--ok' : 'msg--err']" role="status" aria-live="polite">{{ importMsg }}</p>
      </div>

      <div class="card">
        <h2 class="card__title">添加单条知识</h2>
        <div class="form-grid">
          <div class="form-group">
            <label for="add-title">标题</label>
            <input id="add-title" v-model="addForm.title" autocomplete="off" />
          </div>
          <div class="form-group">
            <label for="add-category">分类</label>
            <select id="add-category" v-model="addForm.category">
              <option value="" disabled>请选择分类</option>
              <option value="business-rules">业务规则</option>
              <option value="historical-cases">历史用例</option>
              <option value="pitfalls">线上坑点</option>
              <option value="templates">模板</option>
              <option value="data-dictionary">数据字典</option>
              <option value="business-specs">业务规格</option>
              <option value="team-standards">团队规范</option>
            </select>
          </div>
          <div class="form-group form-group--full">
            <label for="add-content">内容</label>
            <textarea id="add-content" v-model="addForm.content" rows="4"></textarea>
          </div>
          <div class="form-group">
            <label for="add-tags">标签（逗号分隔）</label>
            <input id="add-tags" v-model="addForm.tags" autocomplete="off" />
          </div>
          <div class="form-group">
            <label for="add-module">模块</label>
            <input id="add-module" v-model="addForm.module" autocomplete="off" />
          </div>
        </div>
        <button class="btn-primary" :disabled="adding" @click="addKnowledge">
          {{ adding ? '添加中…' : '添加' }}
        </button>
        <p v-if="addMsg" :class="['msg', addOk ? 'msg--ok' : 'msg--err']" role="status" aria-live="polite">{{ addMsg }}</p>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import PageHeader from '../components/PageHeader.vue'
import EmptyState from '../components/EmptyState.vue'
import FileDropZone from '../components/FileDropZone.vue'
import Pagination from '../components/Pagination.vue'
import { api } from '../composables/useApi'

const tabs = [
  { id: 'config', label: '配置' },
  { id: 'search', label: '搜索' },
  { id: 'import', label: '导入' },
]
const activeTab = ref('config')

// Config
const form = ref({ provider_type: 'mcp_filesystem', connection_url: '', auth_token: '', vault_path: '' })
const saving = ref(false)
const configMsg = ref('')
const configMsgOk = ref(true)
const currentConfig = ref(null)
const status = ref(null)

async function saveConfig() {
  saving.value = true
  configMsg.value = ''
  try {
    const data = await api.post('/knowledge/update_config', { json: form.value })
    configMsgOk.value = data.status === 'success'
    configMsg.value = data.message || (data.status === 'success' ? '配置已生效' : '保存失败')
    if (data.status === 'success') { loadCurrentConfig(); loadStatus() }
  } catch (e) {
    configMsgOk.value = false
    configMsg.value = e.message
  } finally { saving.value = false }
}

async function loadCurrentConfig() {
  try { currentConfig.value = await api.get('/knowledge/current_config') } catch { /* ignore */ }
}

async function loadStatus() {
  try { status.value = await api.get('/knowledge/status') } catch { /* ignore */ }
}

// Search
const searchQuery = ref('')
const searchResults = ref([])
const searchLoading = ref(false)
const searchDone = ref(false)
const searchPage = ref(1)
const searchPages = ref(1)
const searchTotal = ref(0)

// 竞态保护：快速搜索/翻页时丢弃旧请求结果
let searchReqId = 0

async function doSearch(page = 1) {
  if (!searchQuery.value.trim()) return
  searchLoading.value = true
  searchDone.value = false
  const myReqId = ++searchReqId
  try {
    const data = await api.get(
      `/knowledge/search?q=${encodeURIComponent(searchQuery.value)}&page=${page}&page_size=20`
    )
    if (myReqId !== searchReqId) return  // 竞态丢弃
    searchResults.value = data.results || []
    searchPage.value = data.page || 1
    searchPages.value = data.pages || 1
    searchTotal.value = data.total || 0
  } catch {
    if (myReqId !== searchReqId) return  // 竞态丢弃
    searchResults.value = []
  }
  if (myReqId === searchReqId) {
    searchLoading.value = false
    searchDone.value = true
  }
}

// Import
const importMsg = ref('')
const importOk = ref(true)

async function importExcel(file) {
  importMsg.value = ''
  const fd = new FormData()
  fd.append('file', file)
  try {
    const data = await api.upload('/knowledge/import', fd)
    importOk.value = data.ok !== false
    importMsg.value = data.message || `导入 ${data.imported || 0} 条`
    if (data.ok !== false) loadStatus()
  } catch (e) {
    importOk.value = false
    importMsg.value = e.message
  }
}

// Add
const addForm = ref({ title: '', category: '', content: '', tags: '', module: '' })
const adding = ref(false)
const addMsg = ref('')
const addOk = ref(true)

async function addKnowledge() {
  if (!addForm.value.title || !addForm.value.content) {
    addMsg.value = '标题和内容必填'
    addOk.value = false
    return
  }
  adding.value = true
  addMsg.value = ''
  const fd = new FormData()
  Object.entries(addForm.value).forEach(([k, v]) => fd.append(k, v))
  try {
    const data = await api.upload('/knowledge/add', fd)
    addOk.value = data.ok !== false
    addMsg.value = data.message || '添加成功'
    if (data.ok !== false) {
      addForm.value = { title: '', category: '', content: '', tags: '', module: '' }
      loadStatus()
    }
  } catch (e) {
    addOk.value = false
    addMsg.value = e.message
  } finally { adding.value = false }
}

onMounted(() => { loadCurrentConfig(); loadStatus() })
</script>

<style scoped>
.knowledge-view {
  max-width: var(--content-max-width);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-xl);
}

/* Tabs */
.tabs {
  display: flex;
  gap: var(--space-xs);
  border-bottom: 1px solid var(--border-default);
  padding-bottom: var(--space-xs);
}
.tabs__btn {
  padding: var(--space-sm) var(--space-lg);
  border: none;
  border-radius: var(--radius-md) var(--radius-md) 0 0;
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--text-base);
  transition: background var(--duration-fast) var(--ease-out),
              color var(--duration-fast) var(--ease-out);
}
.tabs__btn:hover { background: var(--bg-inset); }
.tabs__btn--active {
  color: var(--accent);
  font-weight: 500;
  box-shadow: inset 0 -2px 0 var(--accent);
}
[data-theme="dark"] .tabs__btn--active {
  text-shadow: var(--text-glow);
  box-shadow: inset 0 -2px 0 var(--accent), 0 2px 4px hsl(0 0% 50% / 0.15);
}

.tab-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-xl);
}

/* Cards */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--space-lg);
}
.card {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: var(--space-xl);
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}
.card__title { font-size: var(--text-lg); font-weight: 600; }
[data-theme="dark"] .card__title { text-shadow: var(--text-glow); }
.card__desc { font-size: var(--text-sm); color: var(--text-secondary); }

.config-info p { font-size: var(--text-sm); margin-bottom: var(--space-xs); }
.warn-hint { color: var(--status-paused); font-size: var(--text-sm); }

.stat-big { font-size: var(--text-2xl); font-weight: 700; }
.stat-unit { font-size: var(--text-sm); font-weight: 400; color: var(--text-secondary); }

.cat-badges { display: flex; flex-wrap: wrap; gap: var(--space-xs); }
.cat-badge {
  padding: 2px 10px;
  background: var(--accent-subtle);
  color: var(--accent);
  border-radius: 999px;
  font-size: var(--text-xs);
}
[data-theme="dark"] .cat-badge {
  border: 1px solid hsl(0 0% 20%);
}

/* Forms */
.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: var(--space-md);
}
.form-group { display: flex; flex-direction: column; gap: var(--space-xs); }
.form-group--full { grid-column: 1 / -1; }
.form-group label {
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-secondary);
}
.form-group input,
.form-group select,
.form-group textarea {
  padding: var(--space-sm) var(--space-md);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: var(--text-base);
  font-family: inherit;
  transition: border-color var(--duration-fast) var(--ease-out);
}
.form-group input:focus,
.form-group select:focus,
.form-group textarea:focus {
  border-color: var(--accent);
  outline: none;
}

.btn-primary {
  align-self: flex-start;
  padding: var(--space-sm) var(--space-xl);
  background: var(--accent);
  color: var(--accent-text);
  border: none;
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  font-weight: 500;
  transition: background var(--duration-fast) var(--ease-out);
}
.btn-primary:hover:not(:disabled) { background: var(--accent-hover); }
[data-theme="dark"] .btn-primary { box-shadow: var(--shadow-accent); }
[data-theme="dark"] .btn-primary:hover:not(:disabled) { box-shadow: var(--shadow-accent-lg); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.msg { font-size: var(--text-sm); padding: var(--space-sm) var(--space-md); border-radius: var(--radius-md); }
.msg--ok { background: var(--feedback-success-bg); color: var(--feedback-success-text); }
.msg--err { background: var(--feedback-error-bg); color: var(--feedback-error-text); }

/* Search */
.search-bar { display: flex; gap: var(--space-sm); }
.search-bar__input {
  flex: 1;
  padding: var(--space-sm) var(--space-md);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: var(--text-base);
}
.search-bar__input:focus { border-color: var(--accent); outline: none; }

.loading-hint { text-align: center; padding: var(--space-xl); color: var(--text-tertiary); }

.search-results { list-style: none; display: flex; flex-direction: column; gap: var(--space-md); }
.search-result {
  padding: var(--space-lg);
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
}
.search-result__title { font-size: var(--text-base); font-weight: 600; margin-bottom: var(--space-xs); }
[data-theme="dark"] .search-result__title { text-shadow: var(--text-glow); }
[data-theme="dark"] .search-result__cat { text-shadow: var(--text-glow); }
.search-result__cat { font-size: var(--text-xs); color: var(--accent); margin-bottom: var(--space-xs); }
.search-result__snippet { font-size: var(--text-sm); color: var(--text-secondary); line-height: 1.6; }

.search-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--space-md);
  padding-top: var(--space-md);
}
.search-footer__total {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
}
</style>
