<script setup lang="ts">
/**
 * ProviderCard — 单个 LLM Provider 卡片
 * 显示：协议徽章 / 状态点 / 名称 / 模型 / 默认徽章 / API Key 脱敏 / 三点菜单
 *
 * 拖拽支持（V1）：
 *   - 通过 draggable 属性控制是否可拖（外部 v-for 时加 :draggable="true"）
 *   - 通过原生 HTML5 DnD 事件向外抛出 dragstart / dragover / drop / dragend
 *   - 卡片整体为 drag handle，避免按钮误触
 */

import { computed, ref } from 'vue'

import {
  PROTOCOL_META,
  parseStatus,
  type LLMProvider,
} from '@/types/config'

const props = defineProps<{
  provider: LLMProvider
  isDefault: boolean
  /** 最近一次测试结果（status 字段） */
  lastStatus?: string
  /** 是否可拖（V1 拖拽排序） */
  draggable?: boolean
  /** V2：是否启用选择模式（显示 checkbox 蒙层） */
  selectable?: boolean
  /** V2：是否已选中 */
  selected?: boolean
}>()

const emit = defineEmits<{
  (e: 'edit', provider: LLMProvider): void
  (e: 'delete', provider: LLMProvider): void
  (e: 'set-default', provider: LLMProvider): void
  (e: 'test', provider: LLMProvider): void
  (e: 'toggle-enabled', provider: LLMProvider): void
  /** V1：拖拽放置，通知父级把 draggedName 插入到 beforeName 之前 */
  (
    e: 'reorder-insert',
    payload: { draggedName: string; beforeName: string },
  ): void
  /** V2：选中/取消选中 */
  (e: 'select-change', payload: { name: string; selected: boolean }): void
}>()

const protocolLabel = computed(() => PROTOCOL_META[props.provider.protocol]?.label || props.provider.protocol)
const protocolIcon = computed(() => PROTOCOL_META[props.provider.protocol]?.icon || '🔮')

const statusKind = computed(() => parseStatus(props.lastStatus))
const statusLabel = computed(() => {
  if (!props.lastStatus) return '未测试'
  if (statusKind.value === 'ok') return '已联通'
  if (statusKind.value === 'degraded') return props.lastStatus.startsWith('degraded') ? '异常' : '检测失败'
  return '未配置'
})

const maskedKey = computed(() => {
  const k = props.provider.api_key || ''
  if (!k) return '未配置'
  if (k.includes('...')) return k
  if (k.length > 12) return k.slice(0, 8) + '...' + k.slice(-4)
  return '***'
})

const menuOpen = ref(false)
function closeMenu() {
  menuOpen.value = false
}

// ─── V1: 拖拽状态 ───
const isDragging = ref(false)
const isDragOver = ref(false)

function onDragStart(e: DragEvent) {
  if (!props.draggable) {
    e.preventDefault()
    return
  }
  // 用 dataTransfer 传递被拖 provider 的 name，drop 时取出
  e.dataTransfer?.setData('text/plain', props.provider.name)
  e.dataTransfer?.setData('application/x-provider-name', props.provider.name)
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move'
  isDragging.value = true
}

function onDragEnd() {
  isDragging.value = false
  isDragOver.value = false
}

function onDragOver(e: DragEvent) {
  if (!props.draggable) return
  e.preventDefault() // 必须 preventDefault 才能触发 drop
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'move'
  isDragOver.value = true
}

function onDragLeave() {
  isDragOver.value = false
}

function onDrop(e: DragEvent) {
  if (!props.draggable) return
  e.preventDefault()
  isDragOver.value = false
  const draggedName =
    e.dataTransfer?.getData('application/x-provider-name') ||
    e.dataTransfer?.getData('text/plain')
  if (!draggedName || draggedName === props.provider.name) return
  // 通知父级：把 draggedName 移到当前 provider 之前
  emit('reorder-insert', { draggedName, beforeName: props.provider.name })
}

// ─── V2: 选择模式 ───
function onToggleSelect() {
  if (!props.selectable) return
  emit('select-change', {
    name: props.provider.name,
    selected: !props.selected,
  })
}

function onCheckboxKeydown(e: KeyboardEvent) {
  // Space / Enter 切换选择
  if (e.key === ' ' || e.key === 'Enter') {
    e.preventDefault()
    onToggleSelect()
  }
}
</script>

<template>
  <div
    class="provider-card"
    :class="{
      'is-default': isDefault,
      'is-disabled': !provider.enabled,
      'is-draggable': draggable && !selectable,
      'is-dragging': isDragging,
      'is-drag-over': isDragOver,
      'is-selectable': selectable,
      'is-selected': selectable && selected,
    }"
    role="article"
    :aria-label="`Provider ${provider.name}`"
    :draggable="(draggable && !selectable) || false"
    @dragstart="onDragStart"
    @dragend="onDragEnd"
    @dragover="onDragOver"
    @dragleave="onDragLeave"
    @drop="onDrop"
  >
    <!-- V2: 选择模式 checkbox 蒙层 -->
    <button
      v-if="selectable"
      type="button"
      class="pc-select"
      :class="{ 'is-checked': selected }"
      :aria-checked="!!selected"
      :aria-label="selected ? `取消选中 ${provider.name}` : `选中 ${provider.name}`"
      role="checkbox"
      tabindex="0"
      @click.stop="onToggleSelect"
      @keydown="onCheckboxKeydown"
    >
      <span class="pc-select-tick" aria-hidden="true">
        {{ selected ? '✓' : '' }}
      </span>
    </button>

    <!-- 顶部：协议徽章 + 状态点 -->
    <div class="pc-header">
      <span class="pc-protocol" :title="PROTOCOL_META[provider.protocol]?.desc">
        <span class="pc-protocol-icon" aria-hidden="true">{{ protocolIcon }}</span>
        <span class="pc-protocol-label">{{ protocolLabel }}</span>
      </span>
      <span class="pc-status" :class="`is-${statusKind}`" :title="lastStatus || '未测试'">
        <span class="pc-status-dot" :class="`is-${statusKind}`" aria-hidden="true" />
        <span class="pc-status-text">{{ statusLabel }}</span>
      </span>
    </div>

    <!-- 中部：名称 + 模型 -->
    <div class="pc-body">
      <div class="pc-name-row">
        <h3 class="pc-name">{{ provider.name || '未命名' }}</h3>
        <span v-if="isDefault" class="pc-default-badge" title="默认 Provider">★ 默认</span>
      </div>
      <p class="pc-model">{{ provider.model || '未设置模型' }}</p>
      <p v-if="provider.base_url" class="pc-url" :title="provider.base_url">
        {{ provider.base_url }}
      </p>
      <p v-else-if="provider.endpoint" class="pc-url" :title="provider.endpoint">
        {{ provider.endpoint }}
      </p>
      <p class="pc-key">Key: <code>{{ maskedKey }}</code></p>
      <!-- V3: Tags 展示 -->
      <div v-if="provider.tags && provider.tags.length" class="pc-tags" role="list" aria-label="Provider 标签">
        <span
          v-for="t in provider.tags"
          :key="t"
          class="pc-tag"
          role="listitem"
        >{{ t }}</span>
      </div>
    </div>

    <!-- 底部：操作 -->
    <div class="pc-footer">
      <button
        type="button"
        class="pc-btn pc-btn-test"
        :aria-label="`测试连接 ${provider.name}`"
        @click="emit('test', provider)"
      >
        测试
      </button>
      <button
        v-if="!isDefault && provider.enabled"
        type="button"
        class="pc-btn pc-btn-secondary"
        :aria-label="`设为默认 ${provider.name}`"
        @click="emit('set-default', provider)"
      >
        设为默认
      </button>
      <span class="pc-spacer" />
      <button
        type="button"
        class="pc-toggle"
        :aria-pressed="provider.enabled"
        :aria-label="provider.enabled ? `禁用 ${provider.name}` : `启用 ${provider.name}`"
        @click="emit('toggle-enabled', provider)"
      >
        {{ provider.enabled ? '✓ 已启用' : '○ 已禁用' }}
      </button>
      <div class="pc-menu-wrap">
        <button
          type="button"
          class="pc-menu-btn"
          :aria-label="`更多操作 ${provider.name}`"
          :aria-expanded="menuOpen"
          @click="menuOpen = !menuOpen"
          @keydown.escape="closeMenu"
        >
          ⋯
        </button>
        <div v-if="menuOpen" class="pc-menu" role="menu" @click="closeMenu">
          <button class="pc-menu-item" role="menuitem" @click="emit('edit', provider); closeMenu()">
            编辑
          </button>
          <button
            v-if="!isDefault"
            class="pc-menu-item pc-menu-item-danger"
            role="menuitem"
            @click="emit('delete', provider); closeMenu()"
          >
            删除
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.provider-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
  padding: var(--space-lg);
  background: var(--panel-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  transition: all var(--duration-fast) var(--ease);
}
.provider-card:hover {
  border-color: var(--muted-fg);
}
.provider-card.is-default {
  border-color: var(--fg);
  box-shadow: 0 0 0 1px var(--fg);
}
.provider-card.is-disabled {
  opacity: 0.55;
}
.provider-card.is-draggable {
  cursor: grab;
  user-select: none;
}
.provider-card.is-draggable:active {
  cursor: grabbing;
}
.provider-card.is-dragging {
  opacity: 0.4;
  border-style: dashed;
}
.provider-card.is-drag-over {
  border-color: var(--fg);
  box-shadow: -2px 0 0 0 var(--fg);
}

/* V2: 选择模式 */
.provider-card.is-selectable {
  cursor: pointer;
  position: relative;
}
.provider-card.is-selected {
  border-color: var(--fg);
  box-shadow: 0 0 0 2px var(--fg);
  background: var(--hover-bg);
}
.pc-select {
  position: absolute;
  top: 0.6rem;
  right: 0.6rem;
  width: 1.4rem;
  height: 1.4rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--bg);
  border: 1.5px solid var(--border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--bg);
  z-index: 2;
  transition: all var(--duration-fast) var(--ease);
}
.pc-select:hover {
  border-color: var(--fg);
}
.pc-select:focus-visible {
  outline: 2px solid var(--fg);
  outline-offset: 2px;
}
.pc-select.is-checked {
  background: var(--fg);
  border-color: var(--fg);
}
.pc-select-tick {
  line-height: 1;
}

.pc-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-sm);
}

.pc-protocol {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.25rem 0.6rem;
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--muted-fg);
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-full);
}
.pc-protocol-icon {
  font-size: 0.9rem;
}

.pc-status {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.7rem;
  font-weight: 500;
  color: var(--muted-fg);
}
.pc-status-dot {
  display: inline-block;
  width: 0.5rem;
  height: 0.5rem;
  border-radius: var(--radius-full);
  background: var(--muted-fg);
}
.pc-status-dot.is-ok { background: #10b981; box-shadow: 0 0 6px #10b98180; }
.pc-status-dot.is-degraded { background: #f59e0b; }
.pc-status-dot.is-unknown { background: var(--muted-fg); }
.pc-status.is-ok { color: #10b981; }
.pc-status.is-degraded { color: #f59e0b; }

.pc-body {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.pc-name-row {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}
.pc-name {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--fg);
}
.pc-default-badge {
  font-size: 0.65rem;
  font-weight: 600;
  color: var(--bg);
  background: var(--fg);
  padding: 0.15rem 0.45rem;
  border-radius: var(--radius-sm);
}
.pc-model {
  margin: 0;
  font-size: 0.82rem;
  color: var(--muted-fg);
  font-family: var(--font-mono, monospace);
}
.pc-url {
  margin: 0;
  font-size: 0.7rem;
  color: var(--muted-fg);
  font-family: var(--font-mono, monospace);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pc-key {
  margin: 0;
  font-size: 0.7rem;
  color: var(--muted-fg);
}
.pc-key code {
  font-family: var(--font-mono, monospace);
  font-size: 0.7rem;
}

/* V3: Tags 展示 */
.pc-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  margin-top: 0.2rem;
}
.pc-tag {
  display: inline-block;
  padding: 0.1rem 0.45rem;
  font-size: 0.65rem;
  font-weight: 600;
  color: var(--muted-fg);
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-full);
}

.pc-footer {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding-top: var(--space-sm);
  border-top: 1px dashed var(--border);
}
.pc-btn {
  padding: 0.3rem 0.7rem;
  font-size: 0.72rem;
  font-weight: 600;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg);
  color: var(--fg);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease);
}
.pc-btn:hover {
  border-color: var(--fg);
}
.pc-btn-secondary {
  background: transparent;
  color: var(--muted-fg);
}
.pc-spacer { flex: 1; }

.pc-toggle {
  padding: 0.3rem 0.6rem;
  font-size: 0.7rem;
  font-weight: 500;
  color: var(--muted-fg);
  background: transparent;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  cursor: pointer;
}
.pc-toggle[aria-pressed="true"] {
  color: #10b981;
  border-color: #10b981;
}

.pc-menu-wrap { position: relative; }
.pc-menu-btn {
  width: 1.8rem;
  height: 1.8rem;
  font-size: 1rem;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--fg);
  cursor: pointer;
}
.pc-menu-btn:hover { border-color: var(--fg); }
.pc-menu {
  position: absolute;
  right: 0;
  bottom: calc(100% + 4px);
  min-width: 8rem;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
  z-index: 10;
  padding: 0.25rem;
}
.pc-menu-item {
  display: block;
  width: 100%;
  padding: 0.45rem 0.6rem;
  font-size: 0.78rem;
  text-align: left;
  background: transparent;
  border: none;
  color: var(--fg);
  cursor: pointer;
  border-radius: var(--radius-sm);
}
.pc-menu-item:hover { background: var(--hover-bg); }
.pc-menu-item-danger { color: #dc2626; }
</style>
