<script setup lang="ts">
/**
 * 知识库管理页（IA 重构版）
 * 三段式：① 概览头（状态徽标 + 主信息）② 主工作区（工具条 + 列表）③ 添加抽屉
 * 操作分层：搜索/导入Excel 独立主操作；添加单条 改右侧 Drawer（渐进式披露）
 * 空状态：未配置 / 空库已配置 / 无搜索结果 三态引导
 * - 顶部状态：GET /knowledge/status
 * - 搜索：GET /knowledge/search?q=...&page=...（分页）
 * - 导入：POST /knowledge/import（FormData, file=.xlsx/.xls）
 * - 添加单条：POST /knowledge/add（FormData: title/category/content/tags/module）
 */
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import { apiGet, apiPost, ApiError } from '@/composables/useApi'
import { useToastStore } from '@/composables/useToast'
import { API } from '@/types/api'

const toast = useToastStore()

/* ─────────────── KB 状态 ─────────────── */
interface KbStatus {
  enabled?: boolean
  configured?: boolean
  total?: number
  categories?: Record<string, number>
  vault_path?: string
  message?: string
  source?: string
  provider_type?: string
  error?: string
}

const status = reactive<KbStatus>({})
const statusLoading = ref(false)

async function loadStatus() {
  statusLoading.value = true
  try {
    const data = await apiGet(API.KNOWLEDGE.STATUS)
    Object.assign(status, data)
  } catch (e) {
    toast.error(e instanceof ApiError ? e.message : '加载知识库状态失败')
  } finally {
    statusLoading.value = false
  }
}

/** 状态卡片「已配置 / 未配置」判定（兼容 enabled 与 configured 两种字段） */
const isConfigured = computed(() => Boolean(status.enabled ?? status.configured))
const totalCount = computed(() => status.total ?? 0)

/* ─────────────── 搜索 ─────────────── */
interface SearchResult {
  id?: string
  title: string
  content: string
  category: string
  module?: string
  tags?: string[] | string
  filepath?: string
  score?: number
}

const query = ref('')
const results = ref<SearchResult[]>([])
const searching = ref(false)
const hasSearched = ref(false)

// 分页
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const pages = ref(1)

async function doSearch(resetPage = false) {
  if (!query.value.trim()) {
    toast.info('请输入搜索关键词')
    return
  }
  if (resetPage) page.value = 1
  searching.value = true
  hasSearched.value = true
  try {
    const data = await apiGet(
      `${API.KNOWLEDGE.SEARCH}?q=${encodeURIComponent(query.value.trim())}` +
        `&page=${page.value}&page_size=${pageSize.value}`,
    )
    results.value = (data?.results ?? []) as SearchResult[]
    total.value = Number(data?.total ?? 0)
    pages.value = Number(data?.pages ?? 1)
    // 后端会钳制越界页码，回写以保持 UI 一致
    if (typeof data?.page === 'number') page.value = data.page
  } catch (e) {
    toast.error(e instanceof ApiError ? e.message : '搜索失败')
    results.value = []
  } finally {
    searching.value = false
  }
}

function goPage(n: number) {
  if (n < 1 || n > pages.value || n === page.value) return
  page.value = n
  doSearch()
}

function clearSearch() {
  query.value = ''
  results.value = []
  hasSearched.value = false
  total.value = 0
  pages.value = 1
  page.value = 1
}

/** 摘要：截断 content 为预览片段 */
function summarize(text: string, len = 140): string {
  const t = (text || '').replace(/\s+/g, ' ').trim()
  return t.length > len ? t.slice(0, len) + '…' : t
}

/** tags 统一成字符串展示 */
function tagsText(tags: SearchResult['tags']): string {
  if (!tags) return ''
  if (Array.isArray(tags)) return tags.join(', ')
  return String(tags)
}

/* ─────────────── 导入 Excel ─────────────── */
const importing = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

function triggerImport() {
  fileInput.value?.click()
}

async function onFileChange(e: Event) {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  // 清空 input value，确保同一文件可再次选择
  target.value = ''
  if (!file) return

  if (!/\.(xlsx|xls)$/i.test(file.name)) {
    toast.error('仅支持 .xlsx / .xls 文件')
    return
  }

  importing.value = true
  const fd = new FormData()
  fd.append('file', file)
  try {
    const res = (await apiPost(API.KNOWLEDGE.IMPORT, fd)) as {
      ok: boolean
      imported?: number
      message?: string
    }
    if (res?.ok) {
      const n = res.imported ?? 0
      toast.success(n > 0 ? `导入成功，共 ${n} 条` : '导入成功')
      loadStatus() // 刷新条目数
    } else {
      toast.error(res?.message || '导入失败')
    }
  } catch (err) {
    toast.error(err instanceof ApiError ? err.message : '导入失败')
  } finally {
    importing.value = false
  }
}

/* ─────────────── 添加单条（右侧 Drawer） ─────────────── */
const showAddDrawer = ref(false)
const form = reactive({
  title: '',
  category: '',
  content: '',
  tags: '',
  module: '',
})
const adding = ref(false)

function openAddDrawer() {
  form.title = ''
  form.category = ''
  form.content = ''
  form.tags = ''
  form.module = ''
  showAddDrawer.value = true
}

function closeAddDrawer() {
  showAddDrawer.value = false
}

async function onAdd() {
  if (!form.title.trim() || !form.category.trim() || !form.content.trim()) {
    toast.warn('请填写标题、分类和内容')
    return
  }
  adding.value = true
  const fd = new FormData()
  fd.append('title', form.title.trim())
  fd.append('category', form.category.trim())
  fd.append('content', form.content.trim())
  fd.append('tags', form.tags.trim())
  fd.append('module', form.module.trim())
  try {
    const res = (await apiPost(API.KNOWLEDGE.ADD, fd)) as { ok: boolean; message?: string }
    if (res?.ok) {
      toast.success('添加成功')
      closeAddDrawer()
      loadStatus()
    } else {
      toast.error(res?.message || '添加失败')
    }
  } catch (err) {
    toast.error(err instanceof ApiError ? err.message : '添加失败')
  } finally {
    adding.value = false
  }
}

/* ─────────────── 抽屉无障碍（焦点陷阱 + ESC + 焦点归还 + 滚动锁） ─────────────── */
/* 与 BaseModal 同标准：打开锁屏 + 聚焦首元素，Tab/Shift+Tab 循环，ESC 关闭，关闭归还焦点 */
const drawerPanelRef = ref<HTMLElement | null>(null)
let drawerLastFocused: HTMLElement | null = null

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

function getDrawerFocusable(): HTMLElement[] {
  if (!drawerPanelRef.value) return []
  return Array.from(drawerPanelRef.value.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
}

function onDrawerKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    closeAddDrawer()
    return
  }
  if (e.key !== 'Tab') return
  const focusable = getDrawerFocusable()
  if (focusable.length === 0) {
    e.preventDefault()
    drawerPanelRef.value?.focus()
    return
  }
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  const active = document.activeElement as HTMLElement | null
  if (e.shiftKey) {
    if (active === first || !drawerPanelRef.value?.contains(active)) {
      e.preventDefault()
      last.focus()
    }
  } else {
    if (active === last || !drawerPanelRef.value?.contains(active)) {
      e.preventDefault()
      first.focus()
    }
  }
}

watch(showAddDrawer, async (open) => {
  if (open) {
    drawerLastFocused = document.activeElement as HTMLElement | null
    window.addEventListener('keydown', onDrawerKeydown)
    document.body.style.overflow = 'hidden'
    await nextTick()
    const focusable = getDrawerFocusable()
    if (focusable.length > 0) {
      focusable[0].focus()
    } else {
      drawerPanelRef.value?.focus()
    }
  } else {
    window.removeEventListener('keydown', onDrawerKeydown)
    document.body.style.overflow = ''
    if (drawerLastFocused && typeof drawerLastFocused.focus === 'function') {
      drawerLastFocused.focus()
    }
    drawerLastFocused = null
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onDrawerKeydown)
  document.body.style.overflow = ''
})

/* ─────────────── 空状态判定 ─────────────── */
type EmptyKind = 'unconfigured' | 'empty-configured' | 'no-results' | 'initial' | null
const emptyKind = computed<EmptyKind>(() => {
  if (hasSearched.value && results.value.length === 0) return 'no-results'
  if (!isConfigured.value && totalCount.value === 0) return 'unconfigured'
  if (isConfigured.value && totalCount.value === 0 && !hasSearched.value) return 'empty-configured'
  if (!hasSearched.value && results.value.length === 0) return 'initial'
  return null
})

/* ─────────────── 生命周期 ─────────────── */
onMounted(async () => {
  await loadStatus()
})
</script>

<template>
  <div class="kb-view">
    <!-- ① 概览头 -->
    <section class="overview">
      <div class="overview-head">
        <div class="overview-title">
          <span class="kb-icon" aria-hidden="true">📚</span>
          <h1>知识库管理</h1>
          <span class="config-badge" :class="isConfigured ? 'badge-on' : 'badge-off'">
            <span class="badge-dot" :class="isConfigured ? 'dot-on' : 'dot-off'" aria-hidden="true"></span>
            {{ isConfigured ? '已配置' : '未配置' }}
          </span>
        </div>
        <BaseButton variant="ghost" size="sm" :loading="statusLoading" @click="loadStatus">
          刷新状态
        </BaseButton>
      </div>

      <div class="overview-grid">
        <div class="overview-item">
          <span class="overview-label">数据源</span>
          <span class="overview-value">{{ status.source || status.provider_type || '—' }}</span>
        </div>
        <div class="overview-item">
          <span class="overview-label">Vault 路径</span>
          <span class="overview-value mono" :title="status.vault_path || ''">
            {{ status.vault_path || '—' }}
          </span>
        </div>
        <div class="overview-item">
          <span class="overview-label">条目总数</span>
          <span class="overview-value">{{ totalCount }}</span>
        </div>
      </div>

      <p v-if="status.message" class="overview-note">{{ status.message }}</p>
      <p v-if="status.error" class="overview-error">{{ status.error }}</p>
    </section>

    <!-- ② 主工作区 -->
    <section class="work-area">
      <!-- 工具条：搜索 + 导入 + 添加（操作分层） -->
      <div class="toolbar">
        <form class="search-bar" @submit.prevent="doSearch(true)">
          <input
            v-model="query"
            type="search"
            class="search-input"
            placeholder="输入关键词搜索（标题 / 内容 / 标签）"
            aria-label="搜索知识库"
          />
          <BaseButton type="submit" variant="primary" size="md" :loading="searching">
            搜索
          </BaseButton>
        </form>

        <div class="toolbar-actions">
          <BaseButton variant="secondary" size="md" :loading="importing" @click="triggerImport">
            <span aria-hidden="true">📥</span> 导入 Excel
          </BaseButton>
          <BaseButton variant="primary" size="md" @click="openAddDrawer">
            <span aria-hidden="true">+</span> 添加
          </BaseButton>
        </div>
        <input
          ref="fileInput"
          type="file"
          accept=".xlsx,.xls"
          hidden
          @change="onFileChange"
        />
      </div>

      <!-- 结果区 -->
      <div class="results">
        <div v-if="searching" class="results-loading">搜索中…</div>

        <EmptyState
          v-else-if="emptyKind === 'no-results'"
          icon="🔍"
          message="未找到匹配的知识条目"
        >
          <BaseButton variant="ghost" size="sm" @click="clearSearch">清空筛选</BaseButton>
        </EmptyState>

        <EmptyState
          v-else-if="emptyKind === 'unconfigured'"
          icon="⚙️"
          message="知识库尚未配置数据源"
        />

        <EmptyState
          v-else-if="emptyKind === 'empty-configured'"
          icon="📚"
          message="知识库已就绪，还没有条目"
        >
          <div class="empty-cta">
            <BaseButton variant="secondary" size="sm" :loading="importing" @click="triggerImport">
              导入 Excel
            </BaseButton>
            <BaseButton variant="ghost" size="sm" @click="openAddDrawer">添加单条</BaseButton>
          </div>
        </EmptyState>

        <EmptyState
          v-else-if="emptyKind === 'initial'"
          icon="🔎"
          message="输入关键词开始搜索知识库"
        />

        <ul v-else-if="results.length" class="result-list">
          <li
            v-for="(item, idx) in results"
            :key="(item.id ?? item.title) + '-' + idx"
            class="result-item"
          >
            <div class="result-top">
              <span class="result-title">{{ item.title }}</span>
              <span class="cat-badge">{{ item.category || 'unknown' }}</span>
            </div>
            <p class="result-snippet">{{ summarize(item.content) }}</p>
            <div class="result-meta">
              <span v-if="item.module" class="meta-tag">模块: {{ item.module }}</span>
              <span v-if="tagsText(item.tags)" class="meta-tag">标签: {{ tagsText(item.tags) }}</span>
            </div>
          </li>
        </ul>
      </div>

      <!-- 分页 -->
      <footer v-if="results.length" class="pager">
        <BaseButton variant="ghost" size="sm" :disabled="page <= 1" @click="goPage(page - 1)">
          上一页
        </BaseButton>
        <span class="pager-info">{{ page }} / {{ pages }}（共 {{ total }} 条）</span>
        <BaseButton variant="ghost" size="sm" :disabled="page >= pages" @click="goPage(page + 1)">
          下一页
        </BaseButton>
      </footer>
    </section>

    <!-- ③ 添加单条抽屉 -->
    <Transition name="kb-drawer">
      <div v-if="showAddDrawer" class="drawer-mask" @click.self="closeAddDrawer" role="presentation">
        <aside
          ref="drawerPanelRef"
          class="drawer"
          role="dialog"
          aria-modal="true"
          aria-labelledby="kb-add-title"
          tabindex="-1"
        >
          <header class="dr-header">
            <h2 id="kb-add-title" class="dr-title">添加单条知识</h2>
            <button type="button" class="dr-close" aria-label="关闭" @click="closeAddDrawer">×</button>
          </header>

          <div class="dr-body">
            <form class="add-form" @submit.prevent="onAdd">
              <label class="field">
                <span class="field-label">标题 <em>*</em></span>
                <input v-model="form.title" type="text" class="field-input" placeholder="例如：登录接口边界用例" />
              </label>

              <div class="field-row">
                <label class="field">
                  <span class="field-label">分类 <em>*</em></span>
                  <input v-model="form.category" type="text" class="field-input" placeholder="如 historical-cases" />
                </label>
                <label class="field">
                  <span class="field-label">模块</span>
                  <input v-model="form.module" type="text" class="field-input" placeholder="如 用户中心/登录" />
                </label>
              </div>

              <label class="field">
                <span class="field-label">标签</span>
                <input v-model="form.tags" type="text" class="field-input" placeholder="逗号分隔，如 登录, 边界, P0" />
              </label>

              <label class="field">
                <span class="field-label">内容 <em>*</em></span>
                <textarea v-model="form.content" rows="6" class="field-input field-textarea" placeholder="知识条目正文…"></textarea>
              </label>
            </form>
          </div>

          <footer class="dr-footer">
            <BaseButton variant="ghost" size="md" @click="closeAddDrawer">取消</BaseButton>
            <BaseButton variant="primary" size="md" :loading="adding" @click="onAdd">
              {{ adding ? '添加中...' : '添加' }}
            </BaseButton>
          </footer>
        </aside>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.kb-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-xl);
  padding: var(--space-2xl);
  max-width: var(--content-max-width);
  margin: 0 auto;
  background: var(--bg);
  min-height: 100vh;
}

/* ─── ① 概览头 ─── */
.overview {
  background: var(--panel-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-xl) var(--space-2xl);
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}
.overview-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
}
.overview-title {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}
.overview-title h1 {
  font-size: var(--text-lg);
  font-weight: var(--weight-bold);
  color: var(--fg);
  margin: 0;
}
.kb-icon {
  font-size: var(--text-lg);
}
.config-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: var(--text-xs);
  font-weight: var(--weight-semibold);
  letter-spacing: 0.05em;
  padding: 0.25rem 0.6rem;
  border-radius: var(--radius-full);
  border: 1px solid var(--border);
  white-space: nowrap;
}
.badge-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  display: inline-block;
}
.dot-on {
  background: #2e8b57;
}
.dot-off {
  background: var(--muted-fg);
}
.badge-on {
  background: var(--fg);
  color: var(--bg);
  border-color: var(--fg);
}
.badge-off {
  background: transparent;
  color: var(--muted-fg);
  border-color: var(--border);
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-lg);
  margin-top: var(--space-sm);
}
.overview-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.overview-label {
  font-size: var(--text-xs);
  color: var(--muted-fg);
  letter-spacing: 0.04em;
}
.overview-value {
  font-size: var(--text-sm);
  color: var(--fg);
  font-weight: var(--weight-semibold);
  word-break: break-all;
}
.overview-value.mono {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: var(--weight-medium);
}
.overview-note {
  font-size: var(--text-xs);
  color: var(--muted-fg);
  margin: 0;
}
.overview-error {
  font-size: var(--text-xs);
  color: var(--fg);
  margin: 0;
}

/* ─── ② 主工作区 ─── */
.work-area {
  background: var(--panel-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-xl) var(--space-2xl);
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
}

/* 工具条 */
.toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  flex-wrap: wrap;
}
.search-bar {
  display: flex;
  gap: var(--space-sm);
  flex: 1;
  min-width: 240px;
}
.search-input {
  flex: 1;
  padding: 0.5rem 0.75rem;
  font-size: var(--text-sm);
  font-family: var(--font);
  color: var(--fg);
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  transition: border-color var(--duration-fast) var(--ease),
    box-shadow var(--duration-fast) var(--ease);
}
.search-input::placeholder {
  color: var(--muted-fg);
}
.search-input:focus {
  outline: none;
  border-color: var(--fg);
  box-shadow: 0 0 0 2px var(--accent-dim);
}
.toolbar-actions {
  display: flex;
  gap: var(--space-sm);
}

/* 结果区 */
.results {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
  min-height: 8rem;
}
.results-loading {
  padding: var(--space-xl);
  text-align: center;
  color: var(--muted-fg);
  font-size: var(--text-sm);
}
.empty-cta {
  display: flex;
  gap: var(--space-sm);
  justify-content: center;
  margin-top: var(--space-md);
}
.result-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}
.result-item {
  padding: var(--space-md) var(--space-lg);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg);
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  transition: border-color var(--duration-fast) var(--ease);
}
.result-item:hover {
  border-color: var(--border);
}
.result-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
}
.result-title {
  font-size: var(--text-sm);
  font-weight: var(--weight-semibold);
  color: var(--fg);
}
.cat-badge {
  flex-shrink: 0;
  font-size: var(--text-xs);
  font-weight: var(--weight-semibold);
  letter-spacing: 0.04em;
  padding: 0.15rem 0.5rem;
  border-radius: var(--radius-full);
  background: var(--muted);
  color: var(--muted-fg);
  border: 1px solid var(--border);
}
.result-snippet {
  font-size: var(--text-xs);
  color: var(--muted-fg);
  line-height: 1.5;
  margin: 0;
}
.result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-sm);
  font-size: var(--text-xs);
  color: var(--muted-fg);
}
.meta-tag {
  font-family: var(--font-mono);
}

/* 分页 */
.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-md);
  padding-top: var(--space-sm);
  border-top: 1px solid var(--border-light);
}
.pager-info {
  font-size: var(--text-xs);
  color: var(--muted-fg);
}

/* ─── ③ 添加抽屉 ─── */
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
  background: var(--panel-bg);
  display: flex;
  flex-direction: column;
  border-left: 1px solid var(--border);
  box-shadow: -8px 0 24px rgba(0, 0, 0, 0.12);
}
/* 面板作焦点回退容器，抑制其自身聚焦轮廓（焦点由内部交互元素承载） */
.drawer:focus-visible {
  outline: none;
}
.dr-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-lg) var(--space-2xl);
  border-bottom: 1px solid var(--border);
}
.dr-title {
  margin: 0;
  font-size: var(--text-md);
  font-weight: var(--weight-bold);
  color: var(--fg);
}
.dr-close {
  font-size: var(--text-lg);
  line-height: 1;
  color: var(--muted-fg);
  cursor: pointer;
  padding: 0.25rem 0.4rem;
  border-radius: var(--radius-md);
  transition: background var(--duration-fast) var(--ease), color var(--duration-fast) var(--ease);
}
.dr-close:hover {
  background: var(--hover-bg);
  color: var(--fg);
}
.dr-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-2xl);
}

/* 添加表单 */
.add-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}
.field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
.field-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-md);
}
.field-label {
  font-size: var(--text-xs);
  color: var(--muted-fg);
  font-weight: var(--weight-semibold);
}
.field-label em {
  color: var(--fg);
  font-style: normal;
  margin-left: 0.15rem;
}
.field-input {
  width: 100%;
  padding: 0.5rem 0.75rem;
  font-size: var(--text-sm);
  font-family: var(--font);
  color: var(--fg);
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  transition: border-color var(--duration-fast) var(--ease),
    box-shadow var(--duration-fast) var(--ease);
}
.field-input::placeholder {
  color: var(--muted-fg);
}
.field-input:focus {
  outline: none;
  border-color: var(--fg);
  box-shadow: 0 0 0 2px var(--accent-dim);
}
.field-textarea {
  resize: vertical;
  min-height: 6rem;
  line-height: 1.5;
}
.dr-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-sm);
  padding: var(--space-lg) var(--space-2xl);
  border-top: 1px solid var(--border);
  background: var(--panel-bg);
}

/* 抽屉过渡 */
.kb-drawer-enter-active,
.kb-drawer-leave-active {
  transition: opacity var(--duration-fast) var(--ease);
}
.kb-drawer-enter-active .drawer,
.kb-drawer-leave-active .drawer {
  transition: transform var(--duration-normal) var(--ease);
}
.kb-drawer-enter-from,
.kb-drawer-leave-to {
  opacity: 0;
}
.kb-drawer-enter-from .drawer,
.kb-drawer-leave-to .drawer {
  transform: translateX(100%);
}

/* ─── 响应式 ─── */
@media (max-width: 960px) {
  .overview-grid {
    grid-template-columns: 1fr;
  }
  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }
  .toolbar-actions {
    justify-content: flex-end;
  }
  .field-row {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 640px) {
  .drawer {
    width: 100vw;
  }
}
</style>
