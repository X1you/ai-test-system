<script setup lang="ts">
/**
 * BaseModal — 模态框
 * Teleport 到 body，overlay 背景模糊，ESC/点遮罩关闭，居中
 * 无障碍：role=dialog/aria-modal + aria-labelledby(标题) + aria-describedby(可选)
 * 焦点管理：打开时聚焦弹窗内首个可聚焦元素，Tab/Shift+Tab 循环，关闭后归还焦点给触发器
 */
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    title?: string
    width?: string
    /** aria-describedby 指向的元素 id（可选，用于描述弹窗目的） */
    describedby?: string
  }>(),
  {
    title: '',
    width: '480px',
    describedby: '',
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()

const panelRef = ref<HTMLElement | null>(null)
let lastFocused: HTMLElement | null = null

// 标题 id，用于 aria-labelledby（保证页面内多弹窗不冲突）
const titleId = `modal-title-${Math.random().toString(36).slice(2, 9)}`

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

function getFocusable(): HTMLElement[] {
  if (!panelRef.value) return []
  return Array.from(panelRef.value.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
}

function close() {
  emit('update:modelValue', false)
}

function onOverlayClick() {
  close()
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    close()
    return
  }
  if (e.key !== 'Tab') return
  // 焦点陷阱：Tab/Shift+Tab 在弹窗内循环
  const focusable = getFocusable()
  if (focusable.length === 0) {
    e.preventDefault()
    panelRef.value?.focus()
    return
  }
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  const active = document.activeElement as HTMLElement | null
  if (e.shiftKey) {
    if (active === first || !panelRef.value?.contains(active)) {
      e.preventDefault()
      last.focus()
    }
  } else {
    if (active === last || !panelRef.value?.contains(active)) {
      e.preventDefault()
      first.focus()
    }
  }
}

watch(
  () => props.modelValue,
  async (open) => {
    if (open) {
      lastFocused = document.activeElement as HTMLElement | null
      window.addEventListener('keydown', onKeydown)
      document.body.style.overflow = 'hidden'
      // 打开后聚焦弹窗内首个可聚焦元素（失败则聚焦面板本身）
      await nextTick()
      const focusable = getFocusable()
      if (focusable.length > 0) {
        focusable[0].focus()
      } else {
        panelRef.value?.focus()
      }
    } else {
      window.removeEventListener('keydown', onKeydown)
      document.body.style.overflow = ''
      // 关闭后把焦点归还触发器
      if (lastFocused && typeof lastFocused.focus === 'function') {
        lastFocused.focus()
      }
      lastFocused = null
    }
  },
)

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="modelValue"
        class="modal-overlay"
        @click.self="onOverlayClick"
      >
        <div
          ref="panelRef"
          class="modal-panel"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="title ? titleId : undefined"
          :aria-describedby="describedby || undefined"
          tabindex="-1"
          :style="{ width }"
        >
          <header v-if="title || $slots.header" class="modal-header">
            <slot name="header">
              <h3 :id="titleId" class="modal-title">{{ title }}</h3>
            </slot>
            <button
              class="modal-close"
              aria-label="关闭"
              @click="close"
            >
              ✕
            </button>
          </header>

          <div class="modal-body">
            <slot />
          </div>

          <footer v-if="$slots.footer" class="modal-footer">
            <slot name="footer" />
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* 面板仅作焦点回退容器，抑制其自身的聚焦轮廓（焦点由内部交互元素承载） */
.modal-panel:focus-visible {
  outline: none;
}
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-xl);
  background: rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
}

.modal-panel {
  max-width: calc(100vw - 2rem);
  max-height: calc(100vh - 2rem);
  display: flex;
  flex-direction: column;
  background: var(--panel-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.18);
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-xl) var(--space-2xl);
  border-bottom: 1px solid var(--border-light);
}

.modal-title {
  font-size: 1rem;
  font-weight: 700;
  color: var(--fg);
  letter-spacing: -0.01em;
}

.modal-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.6rem;
  height: 1.6rem;
  font-size: 0.85rem;
  color: var(--muted-fg);
  border-radius: var(--radius-md);
  transition: background var(--duration-fast) var(--ease),
    color var(--duration-fast) var(--ease);
}
.modal-close:hover {
  background: var(--hover-bg);
  color: var(--fg);
}

.modal-body {
  padding: var(--space-2xl);
  overflow-y: auto;
  color: var(--fg);
}

.modal-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-sm);
  padding: var(--space-lg) var(--space-2xl);
  border-top: 1px solid var(--border-light);
}

/* 过渡动画 */
.modal-enter-active,
.modal-leave-active {
  transition: opacity var(--duration-normal) var(--ease);
}
.modal-enter-active .modal-panel,
.modal-leave-active .modal-panel {
  transition: transform var(--duration-normal) var(--ease-out),
    opacity var(--duration-normal) var(--ease-out);
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-from .modal-panel,
.modal-leave-to .modal-panel {
  transform: translateY(12px) scale(0.98);
  opacity: 0;
}
</style>
