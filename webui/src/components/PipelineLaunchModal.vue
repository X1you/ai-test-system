<script setup lang="ts">
/**
 * PipelineLaunchModal — 上传需求文件后弹出的流水线配置弹框
 * 复用 BaseModal（圆角/阴影/ARIA/ESC/滚动锁/焦点陷阱/三段式）
 * 参数组：执行模式（带描述）/ 测试维度 / 输出格式，均用 Card 式 RadioGroup
 * 给默认值，允许用户「直接启动」（Linear/Vercel 自动预填哲学）
 */
import { ref, watch } from 'vue'
import type { Mode, Dimensions, Formats } from '@/types/pipeline'
import { useToastStore } from '@/composables/useToast'
import { usePipelineStore } from '@/stores/pipeline'
import { ApiError } from '@/composables/useApi'
import BaseModal from '@/components/ui/BaseModal.vue'
import BaseButton from '@/components/ui/BaseButton.vue'

const props = defineProps<{
  modelValue: boolean
  file: File | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
}>()

const toast = useToastStore()
const pipelineStore = usePipelineStore()
const submitting = ref(false)

const mode = ref<Mode>('semi')
const dimensions = ref<Dimensions>('basic')
const formats = ref<Formats>('excel')

// 弹窗打开时重置为默认值
watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      mode.value = 'semi'
      dimensions.value = 'basic'
      formats.value = 'excel'
    }
  }
)

const modeOptions: { value: Mode; label: string; desc: string }[] = [
  { value: 'auto', label: '全自动 (auto)', desc: '全自动跑到底，无需人工干预' },
  { value: 'semi', label: '半自动 (semi)', desc: '在需求拆解/测试点/用例评审 3 个检查点暂停' },
  { value: 'step', label: '逐步 (step)', desc: '逐步确认，每一步完成后暂停等待操作' },
]

const dimensionOptions: { value: Dimensions; label: string; desc?: string }[] = [
  { value: 'basic', label: '基础 (basic)', desc: '覆盖核心功能路径' },
  { value: 'all', label: '全维度 (all)', desc: '基础 + 边界 + 异常 + 性能' },
  { value: 'positive,negative', label: '正反向 (pos/neg)', desc: '正向用例与反向用例' },
]

const formatOptions: { value: Formats; label: string; desc?: string }[] = [
  { value: 'excel', label: 'Excel (.xlsx)', desc: '表格化用例，便于评审' },
  { value: 'xmind', label: 'XMind (.xmind)', desc: '脑图结构，便于拆解' },
  { value: 'excel,xmind', label: '两者全打包', desc: '同时输出两种格式' },
]

function close() {
  emit('update:modelValue', false)
}

function formatSize(bytes: number): string {
  return (bytes / 1024).toFixed(1) + ' KB'
}

async function submit() {
  if (!props.file) {
    toast.error('请先选择需求文件')
    return
  }
  submitting.value = true
  try {
    await pipelineStore.startPipeline(props.file, mode.value, dimensions.value, formats.value)
    toast.success(`流水线已启动 [${mode.value}]`)
    close()
  } catch (err) {
    const msg = err instanceof ApiError ? err.message : '启动失败'
    toast.error(msg)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <BaseModal
    :model-value="modelValue"
    :width="'560px'"
    title="启动测试流水线"
    describedby="launch-modal-desc"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
  >
    <!-- 文件摘要（兼作 aria-describedby 目标） -->
    <p id="launch-modal-desc" class="file-summary">
      已上传
      <span class="file-name" :title="file?.name">{{ file?.name || '未选择' }}</span>
      <span v-if="file" class="file-size">{{ formatSize(file.size) }}</span>
      ，选择执行参数后启动流水线。
    </p>

    <!-- 执行模式 -->
    <fieldset class="param-group">
      <legend class="param-title" id="group-mode-label">执行模式</legend>
      <div class="option-grid" role="radiogroup" aria-labelledby="group-mode-label">
        <button
          v-for="opt in modeOptions"
          :key="opt.value"
          type="button"
          class="opt-card"
          :class="{ 'is-checked': mode === opt.value }"
          role="radio"
          :aria-checked="mode === opt.value"
          @click="mode = opt.value"
        >
          <span class="opt-label">{{ opt.label }}</span>
          <span class="opt-desc">{{ opt.desc }}</span>
        </button>
      </div>
    </fieldset>

    <!-- 测试维度 -->
    <fieldset class="param-group">
      <legend class="param-title" id="group-dim-label">测试维度</legend>
      <div class="option-grid" role="radiogroup" aria-labelledby="group-dim-label">
        <button
          v-for="opt in dimensionOptions"
          :key="opt.value"
          type="button"
          class="opt-card"
          :class="{ 'is-checked': dimensions === opt.value }"
          role="radio"
          :aria-checked="dimensions === opt.value"
          @click="dimensions = opt.value"
        >
          <span class="opt-label">{{ opt.label }}</span>
          <span v-if="opt.desc" class="opt-desc">{{ opt.desc }}</span>
        </button>
      </div>
    </fieldset>

    <!-- 输出格式 -->
    <fieldset class="param-group">
      <legend class="param-title" id="group-fmt-label">输出格式</legend>
      <div class="option-grid" role="radiogroup" aria-labelledby="group-fmt-label">
        <button
          v-for="opt in formatOptions"
          :key="opt.value"
          type="button"
          class="opt-card"
          :class="{ 'is-checked': formats === opt.value }"
          role="radio"
          :aria-checked="formats === opt.value"
          @click="formats = opt.value"
        >
          <span class="opt-label">{{ opt.label }}</span>
          <span v-if="opt.desc" class="opt-desc">{{ opt.desc }}</span>
        </button>
      </div>
    </fieldset>

    <template #footer>
      <BaseButton variant="ghost" size="md" @click="close">取消</BaseButton>
      <BaseButton variant="primary" size="md" :loading="submitting" @click="submit">
        {{ submitting ? '启动中...' : '启动流水线' }}
      </BaseButton>
    </template>
  </BaseModal>
</template>

<style scoped>
/* 文件摘要 */
.file-summary {
  font-size: 0.8rem;
  color: var(--muted-fg);
  line-height: 1.6;
  margin: 0 0 var(--space-lg);
  padding: var(--space-md) var(--space-lg);
  background: var(--muted);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  word-break: break-all;
}
.file-name {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--fg);
  font-weight: 600;
}
.file-size {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: var(--muted-fg);
  margin-left: var(--space-xs);
}

/* 参数组 */
.param-group {
  border: none;
  margin: 0 0 var(--space-lg);
  padding: 0;
}
.param-group:last-of-type {
  margin-bottom: 0;
}
.param-title {
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--muted-fg);
  font-family: var(--font-mono);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 0;
  margin-bottom: var(--space-sm);
}

/* 卡片网格 */
.option-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-sm);
}
@media (max-width: 720px) {
  .option-grid {
    grid-template-columns: 1fr;
  }
}

/* 单选卡片（沿用 ProtocolSelector 视觉语言） */
.opt-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.3rem;
  padding: var(--space-md) var(--space-lg);
  text-align: left;
  background: var(--panel-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--fg);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease);
}
.opt-card:hover:not(.is-checked) {
  border-color: var(--muted-fg);
  background: var(--hover-bg);
}
.opt-card.is-checked {
  background: var(--fg);
  color: var(--bg);
  border-color: var(--fg);
}
.opt-label {
  font-size: 0.82rem;
  font-weight: 700;
}
.opt-desc {
  font-size: 0.7rem;
  line-height: 1.45;
  opacity: 0.75;
}
</style>
