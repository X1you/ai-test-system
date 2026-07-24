<script setup lang="ts">
/**
 * ProtocolSelector — 协议大卡片单选
 * 3 个大卡片并排，每张含图标 + 协议名 + 描述
 * 选中态反色高亮；切换协议时保留已填字段（不重置表单）
 */

import { PROTOCOL_META, LLM_PROTOCOLS, type LLMProtocol } from '@/types/config'

const props = defineProps<{
  modelValue: LLMProtocol
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: LLMProtocol): void
}>()

function select(p: LLMProtocol) {
  if (p !== props.modelValue) emit('update:modelValue', p)
}
</script>

<template>
  <div class="protocol-selector" role="radiogroup" aria-label="选择协议类型">
    <button
      v-for="p in LLM_PROTOCOLS"
      :key="p"
      type="button"
      class="proto-card"
      :class="{ 'is-checked': modelValue === p }"
      role="radio"
      :aria-checked="modelValue === p"
      :aria-label="PROTOCOL_META[p].label"
      @click="select(p)"
    >
      <span class="proto-icon" aria-hidden="true">{{ PROTOCOL_META[p].icon }}</span>
      <span class="proto-title">{{ PROTOCOL_META[p].label }}</span>
      <span class="proto-desc">{{ PROTOCOL_META[p].desc }}</span>
    </button>
  </div>
</template>

<style scoped>
.protocol-selector {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-md);
}

.proto-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.9rem 1rem;
  text-align: left;
  background: var(--panel-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--fg);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease);
}
.proto-card:hover:not(.is-checked) {
  border-color: var(--muted-fg);
  background: var(--hover-bg);
}
.proto-card.is-checked {
  background: var(--fg);
  color: var(--bg);
  border-color: var(--fg);
}
.proto-icon {
  font-size: 1.4rem;
  line-height: 1;
}
.proto-title {
  font-size: 0.9rem;
  font-weight: 700;
}
.proto-desc {
  font-size: 0.7rem;
  line-height: 1.4;
  opacity: 0.75;
}

@media (max-width: 720px) {
  .protocol-selector {
    grid-template-columns: 1fr;
  }
}
</style>
