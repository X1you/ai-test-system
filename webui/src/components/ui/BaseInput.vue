<script setup lang="ts">
/**
 * BaseInput — 受控输入框
 * v-model 受控，emit update:modelValue
 */
import { computed } from 'vue'

type InputType = 'text' | 'password' | 'email' | 'number' | 'search' | 'url'

const props = withDefaults(
  defineProps<{
    modelValue: string
    type?: InputType
    placeholder?: string
    disabled?: boolean
  }>(),
  {
    type: 'text',
    placeholder: '',
    disabled: false,
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const value = computed({
  get: () => props.modelValue,
  set: (v: string) => emit('update:modelValue', v),
})

function onInput(e: Event) {
  const target = e.target as HTMLInputElement
  emit('update:modelValue', target.value)
}
</script>

<template>
  <input
    v-model="value"
    :type="type"
    :placeholder="placeholder"
    :disabled="disabled"
    :aria-disabled="disabled || undefined"
    class="base-input"
    @input="onInput"
  />
</template>

<style scoped>
.base-input {
  width: 100%;
  padding: 0.5rem 0.75rem;
  font-size: 0.82rem;
  font-family: var(--font);
  color: var(--fg);
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  transition: border-color var(--duration-fast) var(--ease),
    box-shadow var(--duration-fast) var(--ease);
}

.base-input::placeholder {
  color: var(--muted-fg);
}

.base-input:hover:not(:disabled) {
  border-color: var(--muted-fg);
}

.base-input:focus {
  outline: none;
  border-color: var(--fg);
  box-shadow: 0 0 0 2px var(--accent-dim);
}

.base-input:disabled {
  cursor: not-allowed;
  opacity: 0.5;
  background: var(--muted);
}
</style>
