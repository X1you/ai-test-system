<script setup lang="ts">
/**
 * RadioCard — 单选卡片组的核心卡片组件
 * 选中态：背景 var(--fg) + 文字 var(--bg)
 * 未选中态：正常
 */
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    /** 当前选中值（v-model 在父级） */
    modelValue?: string | number | null
    /** 本卡片对应的值 */
    value: string | number
    /** 卡片标签文字 */
    label: string
  }>(),
  {
    modelValue: null,
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: string | number): void
}>()

const checked = computed(() => props.modelValue === props.value)

function select() {
  if (!checked.value) {
    emit('update:modelValue', props.value)
  }
}
</script>

<template>
  <button
    type="button"
    class="radio-card"
    :class="{ 'is-checked': checked }"
    role="radio"
    :aria-checked="checked"
    @click="select"
  >
    <span class="radio-dot" :class="{ 'is-checked': checked }" aria-hidden="true">
      <span v-if="checked" class="radio-dot-fill" />
    </span>
    <span class="radio-label">
      <slot>{{ label }}</slot>
    </span>
  </button>
</template>

<style scoped>
.radio-card {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  width: 100%;
  padding: var(--space-lg) var(--space-xl);
  font-size: 0.8rem;
  font-weight: 600;
  text-align: left;
  color: var(--fg);
  background: var(--panel-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease);
}

.radio-card:hover:not(.is-checked) {
  border-color: var(--muted-fg);
  background: var(--hover-bg);
}

/* 选中态：反色高亮 */
.radio-card.is-checked {
  background: var(--fg);
  color: var(--bg);
  border-color: var(--fg);
}

.radio-dot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 0.95rem;
  height: 0.95rem;
  flex-shrink: 0;
  border: 1.5px solid var(--muted-fg);
  border-radius: var(--radius-full);
  background: transparent;
  transition: border-color var(--duration-fast) var(--ease);
}
.radio-dot.is-checked {
  border-color: var(--bg);
}

.radio-dot-fill {
  width: 0.45rem;
  height: 0.45rem;
  border-radius: var(--radius-full);
  background: var(--bg);
}

.radio-label {
  flex: 1;
}
</style>
