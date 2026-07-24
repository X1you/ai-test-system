<script setup lang="ts">
/**
 * Badge — 状态徽标
 * status: pending/running/paused/done/error/cancelled/interrupted
 * 根据 status 映射到 buttons.css 中的 badge class + 对应中文文字
 */
import { computed } from 'vue'

type Status =
  | 'pending'
  | 'running'
  | 'paused'
  | 'done'
  | 'error'
  | 'cancelled'
  | 'interrupted'

const props = defineProps<{
  status: Status
}>()

/** status → CSS class 映射（复用 buttons.css 已定义的 badge 样式） */
const classMap: Record<Status, string> = {
  pending: 'badge badge-paused',
  running: 'badge badge-running',
  paused: 'badge badge-paused',
  done: 'badge badge-done',
  error: 'badge badge-error',
  cancelled: 'badge badge-cancelled',
  interrupted: 'badge badge-error',
}

/** status → 中文文字映射 */
const textMap: Record<Status, string> = {
  pending: '待执行',
  running: '执行中',
  paused: '已暂停',
  done: '已完成',
  error: '出错',
  cancelled: '已取消',
  interrupted: '已中断',
}

const classes = computed(() => classMap[props.status])
const text = computed(() => textMap[props.status])
</script>

<template>
  <span :class="classes">{{ text }}</span>
</template>

<style scoped>
/* 徽标样式来自全局 buttons.css，此处仅补充未覆盖场景的最小兜底 */
.badge {
  display: inline-flex;
  align-items: center;
}
</style>
