<script setup lang="ts">
/**
 * BaseButton — 原子按钮组件
 * variant: primary/secondary/danger/ghost/link（5 变体）
 * size: sm/md/lg（3 尺寸，统一 min-height 44px 满足 WCAG 2.5.8）
 * primary/secondary/danger/link 复用 buttons.css 中已定义的 class
 * ghost 使用透明背景
 */
import { computed } from 'vue'

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost' | 'link'
type Size = 'sm' | 'md' | 'lg'

const props = withDefaults(
  defineProps<{
    variant?: Variant
    size?: Size
    disabled?: boolean
    loading?: boolean
  }>(),
  {
    variant: 'primary',
    size: 'md',
    disabled: false,
    loading: false,
  },
)

const classMap: Record<Variant, string> = {
  primary: 'btn-primary',
  secondary: 'btn-secondary',
  danger: 'btn-danger',
  ghost: 'base-btn-ghost',
  link: 'btn-link',
}

const classes = computed(() => [
  'base-btn',
  classMap[props.variant],
  `base-btn-${props.size}`,
  {
    'is-disabled': props.disabled,
    'is-loading': props.loading,
  },
])

const isDisabled = computed(() => props.disabled || props.loading)
</script>

<template>
  <button
    :class="classes"
    :disabled="isDisabled"
    :aria-busy="loading || undefined"
  >
    <span v-if="loading" class="base-btn-spinner" aria-hidden="true" />
    <slot />
  </button>
</template>

<style scoped>
.base-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-sm);
  border-radius: var(--radius-md);
  cursor: pointer;
  white-space: nowrap;
  line-height: var(--leading-tight);
  font-family: var(--font);
  /* WCAG 2.5.8 Level AA 最小点击区域 44×44px */
  min-height: 44px;
  transition: opacity var(--duration-fast) var(--ease),
    background var(--duration-fast) var(--ease),
    color var(--duration-fast) var(--ease),
    border-color var(--duration-fast) var(--ease);
}

/* 尺寸（仅横向 padding + 字号，高度统一 44px） */
.base-btn-sm {
  padding: 0.3rem 0.65rem;
  font-size: var(--text-xs);
}
.base-btn-md {
  padding: 0.5rem 1rem;
  font-size: var(--text-sm);
}
.base-btn-lg {
  padding: 0.65rem 1.25rem;
  font-size: var(--text-md);
}

/* ghost：透明背景 */
.base-btn-ghost {
  background: transparent;
  color: var(--fg);
  border: 1px solid transparent;
  font-size: var(--text-sm);
  font-weight: var(--weight-semibold);
}
.base-btn-ghost:hover {
  background: var(--accent-dim);
}
.base-btn-ghost:active {
  background: var(--hover-bg);
}

/* 禁用态 */
.base-btn.is-disabled,
.base-btn:disabled {
  cursor: not-allowed;
  opacity: 0.45;
  pointer-events: none;
}

/* loading spinner */
.base-btn-spinner {
  width: 0.85em;
  height: 0.85em;
  border: 1.5px solid currentColor;
  border-top-color: transparent;
  border-radius: var(--radius-full);
  animation: base-btn-spin 0.6s linear infinite;
  flex-shrink: 0;
}
.is-loading {
  opacity: 0.75;
}

@keyframes base-btn-spin {
  to {
    transform: rotate(360deg);
  }
}

/* reduced-motion 降级：loading spinner 停止旋转，改用静态省略号 */
@media (prefers-reduced-motion: reduce) {
  .base-btn-spinner {
    animation: none;
    border-top-color: currentColor;
    border-style: dashed;
  }
}
</style>
