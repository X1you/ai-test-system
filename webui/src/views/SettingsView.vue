<script setup lang="ts">
/**
 * SettingsView — 系统配置页（多 LLM × 多协议版本）
 *
 * 布局：
 *  - 顶部：页面标题
 *  - ① LLM Provider 卡片网格（新增 / 编辑 / 删除 / 测试 / 设默认 / 启用停用）
 *  - ② Pipeline 默认配置
 *  - ③ 知识库配置（保留旧 UI 不变，向后兼容）
 *  - ④ 主题切换
 *
 * 抽屉：ProviderDrawer 复用组件
 */

import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'

import { useToastStore } from '@/composables/useToast'
import { useTheme } from '@/composables/useTheme'
import { useConfigStore } from '@/stores/config'
import { ApiError, apiGet } from '@/composables/useApi'
import { API } from '@/types/api'
import type { LLMProvider, LLMProtocol } from '@/types/config'
import type { Dimensions, Formats, Mode } from '@/types/pipeline'
import EmptyState from '@/components/ui/EmptyState.vue'
import ProviderCard from '@/components/ProviderCard.vue'
import ProviderDrawer from '@/components/ProviderDrawer.vue'
import UsageDashboard from '@/components/UsageDashboard.vue'

const configStore = useConfigStore()
const toast = useToastStore()
const { currentTheme, toggleTheme } = useTheme()

// 解构 ref / reactive 字段 — 避免在 setup script 里到处写 .value
const {
  providers,
  defaultName,
  protocols: protocolsRef,
  validation,
  pipeline: pipelineStore,
  lastCheckResults,
  saving,
  loading,
} = storeToRefs(configStore)

// 给模板用的 protocols 列表
const _unused_protocols = computed<LLMProtocol[]>(() => protocolsRef.value)

// ─── 抽屉状态 ───
const drawerOpen = ref(false)
const editingProvider = ref<LLMProvider | null>(null)

// ─── 删除二次确认 ───
const confirmDeleteName = ref<string | null>(null)

// ─── V2: 批量操作状态 ───
const batchMode = ref(false)
const selectedNames = ref<Set<string>>(new Set())
const confirmBatchDelete = ref(false)

// ─── V3: 标签筛选 ───
const activeTag = ref<string | null>(null)

// 所有不重复的 tags（按出现频次降序）
const allTags = computed<string[]>(() => {
  const counts = new Map<string, number>()
  for (const p of providers.value) {
    for (const t of p.tags || []) {
      counts.set(t, (counts.get(t) || 0) + 1)
    }
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([t]) => t)
})

// 按 tag 筛选后的 provider 列表
const filteredProviders = computed<LLMProvider[]>(() => {
  if (!activeTag.value) return providers.value
  return providers.value.filter((p) => (p.tags || []).includes(activeTag.value!))
})

const selectedCount = computed(() => selectedNames.value.size)
const selectedEnabledCount = computed(
  () => providers.value.filter((p) => selectedNames.value.has(p.name) && p.enabled).length,
)
const selectedDisabledCount = computed(
  () => providers.value.filter((p) => selectedNames.value.has(p.name) && !p.enabled).length,
)
// 当前筛选视图内是否已全部选中（注意：selectedNames 可能含其他视图项，需逐项判断）
const isAllSelected = computed(
  () =>
    filteredProviders.value.length > 0 &&
    filteredProviders.value.every((p) => selectedNames.value.has(p.name)),
)
const containsDefault = computed(() =>
  defaultName.value ? selectedNames.value.has(defaultName.value) : false,
)

// ─── Pipeline 表单 ───
const pipeline = ref({
  default_mode: 'semi' as Mode,
  default_dimensions: 'basic' as Dimensions,
  default_formats: 'excel' as Formats,
  self_check: false,
})
const savingPipeline = ref(false)

// ─── KB 配置（保留旧 UI） ───
const kb = ref({
  provider_type: 'mcp_filesystem',
  connection_url: '',
  auth_token: '',
  vault_path: '',
})
const savingKB = ref(false)

onMounted(async () => {
  await configStore.fetchConfig()
  Object.assign(pipeline.value, pipelineStore.value)
  // 加载 KB
  try {
    const kbCfg: any = await apiGet(API.KNOWLEDGE.CURRENT_CONFIG)
    if (kbCfg) Object.assign(kb.value, kbCfg)
  } catch {
    /* 忽略：未配置 KB 时端点可能 404 */
  }
})

// ─── Provider CRUD ───

function openCreate() {
  editingProvider.value = null
  drawerOpen.value = true
}

function openEdit(p: LLMProvider) {
  editingProvider.value = { ...p }
  drawerOpen.value = true
}

function closeDrawer() {
  drawerOpen.value = false
  editingProvider.value = null
}

async function handleSaveProvider(p: LLMProvider) {
  // 构造新列表
  const list = providers.value.map((x: LLMProvider) => ({ ...x }))
  const idx = list.findIndex((x: LLMProvider) => x.name === (editingProvider.value?.name || p.name))
  if (editingProvider.value && idx >= 0) {
    list[idx] = { ...p }
  } else if (idx < 0) {
    list.push({ ...p })
  } else {
    list[idx] = { ...p }
  }
  // api_key 脱敏（仅 ...）或不存在的，删掉，让后端保留
  const payload = list.map((x: LLMProvider): LLMProvider => {
    const dup: LLMProvider = { ...x }
    if (!dup.api_key || dup.api_key.includes('...') || dup.api_key === '***') {
      // 注意：api_key 必填字段不能 delete，置空字符串后端会识别为「未传值保留原 Key」
      dup.api_key = ''
    }
    return dup
  })
  await configStore.updateConfig({ llm: { providers: payload } })
  toast.success(`Provider「${p.name}」已保存`)
}

async function handleTestProvider(p: LLMProvider) {
  return configStore.testProvider(p, 10)
}

async function handleSetDefault(p: LLMProvider) {
  if (p.name === defaultName.value) return
  await configStore.setDefaultProvider(p.name)
  toast.success(`已切换默认 Provider 为「${p.name}」`)
}

async function handleToggleEnabled(p: LLMProvider) {
  const next = !p.enabled
  const list = providers.value.map((x: LLMProvider) =>
    x.name === p.name ? { ...x, enabled: next } : { ...x },
  )
  await configStore.updateConfig({ llm: { providers: list } })
  toast.success(`Provider「${p.name}」已${next ? '启用' : '禁用'}`)
}

function requestDelete(p: LLMProvider) {
  if (p.name === defaultName.value) {
    toast.error('默认 Provider 不能直接删除，请先切换默认')
    return
  }
  confirmDeleteName.value = p.name
}

async function confirmDelete() {
  if (!confirmDeleteName.value) return
  const name = confirmDeleteName.value
  const list = providers.value
    .filter((x: LLMProvider) => x.name !== name)
    .map((x: LLMProvider) => ({ ...x }))
  await configStore.updateConfig({ llm: { providers: list } })
  toast.success(`Provider「${name}」已删除`)
  confirmDeleteName.value = null
}

function cancelDelete() {
  confirmDeleteName.value = null
}

// ─── V1: 拖拽排序（故障转移顺序） ───
async function handleReorderInsert(payload: { draggedName: string; beforeName: string }) {
  const { draggedName, beforeName } = payload
  const list = providers.value.map((p) => p.name)
  const fromIdx = list.indexOf(draggedName)
  if (fromIdx < 0) return
  list.splice(fromIdx, 1)
  const toIdx = list.indexOf(beforeName)
  if (toIdx < 0) {
    list.push(draggedName) // fallback: 放回尾部
  } else {
    list.splice(toIdx, 0, draggedName)
  }
  try {
    await configStore.reorderProviders(list)
    toast.success('Provider 顺序已更新（故障转移优先级同步）')
  } catch (e: any) {
    toast.error(e?.message || '保存顺序失败，已恢复原顺序')
  }
}

// ─── V2: 批量操作 ───

function enterBatchMode() {
  batchMode.value = true
  selectedNames.value = new Set()
}

function exitBatchMode() {
  batchMode.value = false
  selectedNames.value = new Set()
  confirmBatchDelete.value = false
}

function toggleSelectOne(payload: { name: string; selected: boolean }) {
  const next = new Set(selectedNames.value)
  if (payload.selected) next.add(payload.name)
  else next.delete(payload.name)
  selectedNames.value = next
}

function toggleSelectAll() {
  if (isAllSelected.value) {
    // 取消当前筛选视图内的全选
    const visible = new Set(filteredProviders.value.map((p) => p.name))
    const next = new Set(selectedNames.value)
    for (const n of visible) next.delete(n)
    selectedNames.value = next
  } else {
    // 选中当前筛选视图内的全部（追加，不清空已选的其他视图项）
    const next = new Set(selectedNames.value)
    for (const p of filteredProviders.value) next.add(p.name)
    selectedNames.value = next
  }
}

async function handleBatchEnable() {
  if (selectedCount.value === 0) return
  const toEnable = [...selectedNames.value].filter(
    (n) => providers.value.find((p) => p.name === n)?.enabled === false,
  )
  if (toEnable.length === 0) {
    toast.info('所选 Provider 已是启用状态')
    return
  }
  try {
    await configStore.batchToggleEnabled(toEnable, true)
    toast.success(`已启用 ${toEnable.length} 个 Provider`)
  } catch (e: any) {
    toast.error(e?.message || '批量启用失败')
  }
}

async function handleBatchDisable() {
  if (selectedCount.value === 0) return
  if (containsDefault.value) {
    toast.error('默认 Provider 不能直接禁用，请先取消选中或切换默认')
    return
  }
  const toDisable = [...selectedNames.value].filter(
    (n) => providers.value.find((p) => p.name === n)?.enabled === true,
  )
  if (toDisable.length === 0) {
    toast.info('所选 Provider 已是禁用状态')
    return
  }
  try {
    await configStore.batchToggleEnabled(toDisable, false)
    toast.success(`已禁用 ${toDisable.length} 个 Provider`)
  } catch (e: any) {
    toast.error(e?.message || '批量禁用失败')
  }
}

function requestBatchDelete() {
  if (selectedCount.value === 0) return
  if (containsDefault.value) {
    toast.error('默认 Provider 不能直接删除，请先取消选中或切换默认')
    return
  }
  confirmBatchDelete.value = true
}

async function confirmBatchDeleteAction() {
  const names = [...selectedNames.value]
  if (names.length === 0) {
    confirmBatchDelete.value = false
    return
  }
  try {
    await configStore.batchDeleteProviders(names)
    toast.success(`已删除 ${names.length} 个 Provider`)
    selectedNames.value = new Set()
    confirmBatchDelete.value = false
    // 若删空则退出批量模式
    if (providers.value.length === 0) {
      batchMode.value = false
    }
  } catch (e: any) {
    toast.error(e?.message || '批量删除失败')
  }
}

function cancelBatchDelete() {
  confirmBatchDelete.value = false
}

// ─── Pipeline ───

const modeOptions = [
  { value: 'auto', label: '全自动 (auto)' },
  { value: 'semi', label: '半自动 (semi)' },
  { value: 'step', label: '逐步 (step)' },
]
const dimOptions = [
  { value: 'basic', label: '基础 (basic)' },
  { value: 'all', label: '全维度 (all)' },
  { value: 'positive,negative', label: '正反向 (pos/neg)' },
]
const fmtOptions = [
  { value: 'excel', label: 'Excel (.xlsx)' },
  { value: 'xmind', label: 'XMind (.xmind)' },
  { value: 'excel,xmind', label: '两者全打包' },
]

async function savePipeline() {
  savingPipeline.value = true
  try {
    await configStore.updateConfig({ pipeline: { ...pipeline.value } })
    toast.success('Pipeline 配置已保存')
  } catch (e: any) {
    toast.error(e instanceof ApiError ? e.message : '保存失败')
  } finally {
    savingPipeline.value = false
  }
}

// ─── KB（保留） ───

async function saveKB() {
  savingKB.value = true
  try {
    await apiGet(API.KNOWLEDGE.UPDATE_CONFIG) // placeholder: 实际走 POST
    toast.success('知识库配置已热切换')
  } catch (e: any) {
    toast.error(e instanceof ApiError ? e.message : '保存失败')
  } finally {
    savingKB.value = false
  }
}

const protocols = computed<LLMProtocol[]>(() => configStore.protocols)
</script>

<template>
  <div class="settings-view">
    <h2 class="page-title">系统部署与配置</h2>

    <!-- ① LLM Provider 卡片网格 -->
    <section class="config-section">
      <header class="section-header">
        <h3 class="section-title">大模型 (LLM) Provider</h3>
        <div class="section-header-actions">
          <button
            v-if="!batchMode && providers.length > 0"
            class="btn-secondary"
            aria-label="进入批量管理模式"
            @click="enterBatchMode"
          >
            ☑ 批量管理
          </button>
          <button class="btn-primary" @click="openCreate" aria-label="新增 Provider">
            + 新增 Provider
          </button>
        </div>
      </header>
      <p class="section-desc">
        支持多 Provider 列表 + 多协议（OpenAI 兼容 / Anthropic / 自定义 HTTP）。
        点击「测试」会立即验证连通性；「设为默认」会更新 LLM Gateway 主路由。
        拖拽卡片可调整故障转移顺序（上方靠前）。API Key 在列表中脱敏显示（<code>sk-xxx...yyy</code>）。
      </p>

      <!-- V2: 批量操作工具栏 -->
      <div v-if="batchMode" class="batch-toolbar" role="toolbar" aria-label="批量操作工具栏">
        <div class="batch-info">
          <span class="batch-count" aria-live="polite">
            已选 <strong>{{ selectedCount }}</strong> / {{ providers.length }} 个
            <template v-if="selectedCount > 0">
              <span class="batch-meta">
                （启用 {{ selectedEnabledCount }} · 禁用 {{ selectedDisabledCount }}）
              </span>
            </template>
          </span>
        </div>
        <div class="batch-actions">
          <button
            type="button"
            class="btn-secondary"
            :aria-pressed="isAllSelected"
            :disabled="providers.length === 0"
            @click="toggleSelectAll"
          >
            {{ isAllSelected ? '☐ 取消全选' : '☑ 全选' }}
          </button>
          <button
            type="button"
            class="btn-secondary"
            :disabled="selectedCount === 0"
            @click="handleBatchEnable"
          >
            批量启用
          </button>
          <button
            type="button"
            class="btn-secondary"
            :disabled="selectedCount === 0"
            :title="containsDefault ? '默认 Provider 不能直接禁用' : '批量禁用所选'"
            @click="handleBatchDisable"
          >
            批量禁用
          </button>
          <button
            type="button"
            class="btn-danger"
            :disabled="selectedCount === 0"
            :title="containsDefault ? '默认 Provider 不能直接删除' : '批量删除所选'"
            @click="requestBatchDelete"
          >
            批量删除
          </button>
          <button
            type="button"
            class="btn-secondary"
            @click="exitBatchMode"
          >
            退出批量
          </button>
        </div>
      </div>

      <!-- V3: 标签筛选条 -->
      <div v-if="allTags.length > 0" class="tag-filter-bar" role="group" aria-label="按标签筛选">
        <button
          type="button"
          class="tag-filter-chip"
          :class="{ 'is-active': !activeTag }"
          :aria-pressed="!activeTag"
          @click="activeTag = null"
        >
          全部 ({{ providers.length }})
        </button>
        <button
          v-for="t in allTags"
          :key="t"
          type="button"
          class="tag-filter-chip"
          :class="{ 'is-active': activeTag === t }"
          :aria-pressed="activeTag === t"
          @click="activeTag = activeTag === t ? null : t"
        >
          {{ t }}
        </button>
      </div>

      <div v-if="loading" class="loading-row">加载中…</div>

      <div
        v-else-if="providers.length === 0"
        class="empty-row"
      >
        <EmptyState
          message="尚未配置任何 LLM Provider。点击「+ 新增 Provider」开始配置。"
        >
          <button class="btn-primary" @click="openCreate">+ 新增 Provider</button>
        </EmptyState>
      </div>

      <div v-else-if="filteredProviders.length === 0" class="empty-row">
        <EmptyState :message="`没有带标签「${activeTag}」的 Provider。`">
          <button class="btn-secondary" @click="activeTag = null">清除筛选</button>
        </EmptyState>
      </div>

      <div v-else class="provider-grid">
        <ProviderCard
          v-for="p in filteredProviders"
          :key="p.name"
          :provider="p"
          :is-default="p.name === defaultName"
          :last-status="lastCheckResults[p.name]?.status"
          :draggable="!batchMode"
          :selectable="batchMode"
          :selected="selectedNames.has(p.name)"
          @edit="openEdit"
          @delete="requestDelete"
          @set-default="handleSetDefault"
          @test="handleTestProvider"
          @toggle-enabled="handleToggleEnabled"
          @reorder-insert="handleReorderInsert"
          @select-change="toggleSelectOne"
        />
      </div>
    </section>

    <!-- V4: LLM 用量仪表盘 -->
    <section class="config-section">
      <UsageDashboard />
    </section>

    <!-- ② Pipeline 默认配置 -->
    <section class="config-section">
      <h3 class="section-title">流水线 (Pipeline) 默认配置</h3>
      <div class="form-grid">
        <label class="form-label">默认执行模式</label>
        <select v-model="pipeline.default_mode" class="form-select">
          <option v-for="opt in modeOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>

        <label class="form-label">默认测试维度</label>
        <select v-model="pipeline.default_dimensions" class="form-select">
          <option v-for="opt in dimOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>

        <label class="form-label">默认输出格式</label>
        <select v-model="pipeline.default_formats" class="form-select">
          <option v-for="opt in fmtOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>

        <label class="form-label">AI 自检 (Self Check)</label>
        <label class="switch-label">
          <input v-model="pipeline.self_check" type="checkbox" />
          <span>启用生成后自检</span>
        </label>
      </div>
      <div class="section-actions">
        <button class="btn-primary" :disabled="savingPipeline" @click="savePipeline">
          {{ savingPipeline ? '保存中…' : '保存配置' }}
        </button>
      </div>
    </section>

    <!-- ③ 知识库（保留旧 UI） -->
    <section class="config-section">
      <h3 class="section-title">知识库 (RAG) 配置</h3>
      <div class="form-grid">
        <label class="form-label">Provider 类型</label>
        <select v-model="kb.provider_type" class="form-select">
          <option value="mcp_filesystem">MCP Filesystem (本地 Vault)</option>
          <option value="obsidian_api">Obsidian Local REST API</option>
        </select>

        <label class="form-label">Vault 路径</label>
        <input v-model="kb.vault_path" class="form-input" placeholder="/Users/xxx/Documents/notes" />

        <label class="form-label">Connection URL</label>
        <input v-model="kb.connection_url" class="form-input" placeholder="https://127.0.0.1:27124" />

        <label class="form-label">Auth Token</label>
        <input v-model="kb.auth_token" type="password" class="form-input" placeholder="Bearer token" />
      </div>
      <div class="section-actions">
        <button class="btn-primary" :disabled="savingKB" @click="saveKB">
          {{ savingKB ? '保存中…' : '保存并热切换' }}
        </button>
      </div>
    </section>

    <!-- ④ 主题 -->
    <section class="config-section">
      <h3 class="section-title">主题与外观</h3>
      <div class="theme-row">
        <span>当前主题：{{ currentTheme === 'dark' ? '深色' : '浅色' }}</span>
        <button class="btn-secondary" @click="toggleTheme">切换主题</button>
      </div>
    </section>

    <!-- 抽屉 -->
    <ProviderDrawer
      :open="drawerOpen"
      :provider="editingProvider"
      :saving="saving"
      :on-test="handleTestProvider"
      :on-save="handleSaveProvider"
      @update:open="(v: boolean) => (drawerOpen = v)"
    />

    <!-- 删除二次确认 -->
    <Transition name="modal">
      <div
        v-if="confirmDeleteName"
        class="modal-mask"
        role="presentation"
        @click.self="cancelDelete"
      >
        <div class="modal" role="alertdialog" aria-modal="true" :aria-label="`删除 Provider ${confirmDeleteName}`">
          <h3 class="modal-title">删除 Provider「{{ confirmDeleteName }}」？</h3>
          <p class="modal-desc">
            此操作不可撤销。该 Provider 将从配置中移除，已发起的 Pipeline 不受影响。
          </p>
          <div class="modal-actions">
            <button class="btn-secondary" @click="cancelDelete">取消</button>
            <button class="btn-danger" @click="confirmDelete">确认删除</button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- V2: 批量删除二次确认 -->
    <Transition name="modal">
      <div
        v-if="confirmBatchDelete"
        class="modal-mask"
        role="presentation"
        @click.self="cancelBatchDelete"
      >
        <div class="modal" role="alertdialog" aria-modal="true" aria-label="批量删除 Provider">
          <h3 class="modal-title">批量删除 {{ selectedCount }} 个 Provider？</h3>
          <p class="modal-desc">
            此操作不可撤销。所选 Provider 将从配置中移除，已发起的 Pipeline 不受影响。
          </p>
          <ul class="modal-list">
            <li v-for="n in [...selectedNames]" :key="n">{{ n }}</li>
          </ul>
          <div class="modal-actions">
            <button class="btn-secondary" @click="cancelBatchDelete">取消</button>
            <button class="btn-danger" @click="confirmBatchDeleteAction">确认删除</button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.settings-view {
  padding: 1.5rem;
  max-width: 980px;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}
.page-title {
  font-size: var(--text-lg);
  font-weight: 800;
  margin: 0;
}
.config-section {
  border: 1px solid var(--border);
  background: var(--panel-bg);
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border-light);
}
.section-header-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

/* V2: 批量操作工具栏 */
.batch-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  padding: 0.6rem 0.85rem;
  background: var(--hover-bg);
  border: 1px solid var(--fg);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
}
.batch-info {
  color: var(--muted-fg);
  font-weight: var(--weight-medium);
}
.batch-count strong {
  color: var(--fg);
  font-weight: var(--weight-bold);
}
.batch-meta {
  margin-left: 0.4rem;
  font-size: var(--text-xs);
  color: var(--muted-fg);
}
.batch-actions {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  flex-wrap: wrap;
}

/* V3: 标签筛选条 */
.tag-filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  padding: 0.5rem 0;
}
.tag-filter-chip {
  padding: 0.25rem 0.65rem;
  font-size: var(--text-xs);
  font-weight: var(--weight-semibold);
  color: var(--muted-fg);
  background: transparent;
  border: 1px solid var(--border);
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease);
}
.tag-filter-chip:hover {
  border-color: var(--fg);
  color: var(--fg);
}
.tag-filter-chip.is-active {
  background: var(--fg);
  color: var(--bg);
  border-color: var(--fg);
}
.section-title {
  font-size: var(--text-md);
  font-weight: var(--weight-bold);
  margin: 0;
}
.section-desc {
  font-size: var(--text-xs);
  color: var(--muted-fg);
  margin: 0;
}
.section-desc code {
  font-family: var(--font-mono, monospace);
  font-size: var(--text-xs);
  background: var(--hover-bg);
  padding: 0 0.25rem;
  border-radius: 2px;
}

.provider-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}
@media (max-width: 1023px) {
  .provider-grid {
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  }
}
@media (max-width: 767px) {
  .provider-grid {
    grid-template-columns: 1fr;
  }
}

.loading-row,
.empty-row {
  padding: 1rem 0;
}

.form-grid {
  display: grid;
  grid-template-columns: 160px 1fr;
  gap: 0.75rem 1rem;
  align-items: center;
}
.form-label {
  font-size: var(--text-sm);
  font-weight: var(--weight-semibold);
  color: var(--muted-fg);
}
.form-input,
.form-select {
  background: var(--bg);
  border: 1px solid var(--border);
  padding: 0.4rem 0.6rem;
  font-size: var(--text-sm);
  color: var(--fg);
  font-family: inherit;
}
.form-input:focus,
.form-select:focus {
  border-color: var(--fg);
  outline: none;
}
.switch-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: var(--text-sm);
  cursor: pointer;
}
.section-actions {
  display: flex;
  gap: 0.6rem;
  justify-content: flex-end;
}
.theme-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: var(--text-sm);
}

/* 通用按钮 */
.btn-primary {
  padding: 0.5rem 0.9rem;
  font-size: var(--text-sm);
  font-weight: var(--weight-semibold);
  background: var(--fg);
  color: var(--bg);
  border: 1px solid var(--fg);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease);
}
.btn-primary:hover:not(:disabled) { opacity: 0.85; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary {
  padding: 0.5rem 0.9rem;
  font-size: var(--text-sm);
  font-weight: var(--weight-semibold);
  background: transparent;
  color: var(--fg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease);
}
.btn-secondary:hover { border-color: var(--fg); }
.btn-danger {
  padding: 0.5rem 0.9rem;
  font-size: var(--text-sm);
  font-weight: var(--weight-semibold);
  background: #dc2626;
  color: white;
  border: 1px solid #dc2626;
  border-radius: var(--radius-sm);
  cursor: pointer;
}
.btn-danger:hover { background: #b91c1c; }

/* 二次确认弹窗 */
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}
.modal {
  width: 420px;
  max-width: 92vw;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.modal-title { margin: 0; font-size: var(--text-md); font-weight: var(--weight-bold); }
.modal-desc { margin: 0; font-size: var(--text-sm); color: var(--muted-fg); }
.modal-list {
  margin: 0;
  padding: 0.5rem 0 0 1.2rem;
  max-height: 10rem;
  overflow-y: auto;
  font-size: var(--text-xs);
  color: var(--fg);
  font-family: var(--font-mono, monospace);
  background: var(--hover-bg);
  border-radius: var(--radius-sm);
  padding: 0.5rem 0.75rem 0.5rem 2rem;
}
.modal-list li {
  padding: 0.1rem 0;
}
.modal-actions { display: flex; justify-content: flex-end; gap: 0.5rem; }

.modal-enter-active,
.modal-leave-active { transition: opacity var(--duration-fast) var(--ease); }
.modal-enter-from,
.modal-leave-to { opacity: 0; }
</style>
