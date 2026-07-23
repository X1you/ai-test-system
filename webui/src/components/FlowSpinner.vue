<!--
  ════════════════════════════════════════════════════════════════
  FlowSpinner — 吟游诗人流线型加载动画 (Version Four)
  ════════════════════════════════════════════════════════════════
  设计意图：替代传统 spinner，用填充插画呈现"流畅的故事讲述者"
  实现机制：
    1. 渲染 Bard 填充插画（currentColor）
    2. 双层叠加：底色淡化层 + 上层呼吸缩放，模拟线条流动
    3. 呼吸脉动传达"吟游诗人演奏"的流动感
  性能：纯 CSS + SVG，无 JS 循环，GPU 友好
  可访问性：自动遵循 prefers-reduced-motion
  ════════════════════════════════════════════════════════════════
-->
<template>
  <div class="flow-spinner" :class="[`flow-spinner--${size}`]" role="status" :aria-label="label">
    <!-- 底层：淡化剪影（静态参考） -->
    <svg class="flow-spinner__base" viewBox="0 0 512 512" aria-hidden="true">
      <g :transform="groupTransform">
        <path v-for="(p, i) in paths" :key="i" :d="p.d" :transform="p.tf || undefined" fill="currentColor" />
      </g>
    </svg>
    <!-- 上层：完整剪影（呼吸脉动） -->
    <svg class="flow-spinner__overlay" viewBox="0 0 512 512" aria-hidden="true">
      <g :transform="groupTransform">
        <path v-for="(p, i) in paths" :key="i" :d="p.d" :transform="p.tf || undefined" fill="currentColor" />
      </g>
    </svg>
  </div>
</template>

<script setup>
import { useId } from 'vue'
import {
  BARD_TRANSFORM as groupTransform,
  BARD_DARK_PATHS as paths,
} from '../assets/icons/bardIconData.js'

defineProps({
  size: {
    type: String,
    default: 'medium',
    validator: (v) => ['small', 'medium', 'large', 'xlarge'].includes(v),
  },
  label: {
    type: String,
    default: '加载中',
  },
})

// 引用 useId 确保 SSR 唯一性（当前为 SPA，预留）
useId()
</script>

<style scoped>
.flow-spinner {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  position: relative;
  color: var(--accent);
}

.flow-spinner__base,
.flow-spinner__overlay {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
}

/* 底层：静态淡化剪影 */
.flow-spinner__base {
  opacity: 0.15;
}

/* 上层：呼吸缩放，模拟线条流动 */
.flow-spinner__overlay {
  animation: flow-breathe var(--duration-flow, 1200ms) var(--ease-flow, cubic-bezier(0.4, 0, 0.2, 1)) infinite;
  transform-origin: center;
}

@keyframes flow-breathe {
  0% {
    opacity: 0.3;
    transform: scale(0.9);
  }
  50% {
    opacity: 1;
    transform: scale(1.06);
  }
  100% {
    opacity: 0.3;
    transform: scale(0.9);
  }
}

/* 尺寸：与设计系统 token 对齐 */
.flow-spinner--small  { width: 20px; height: 20px; }
.flow-spinner--medium { width: 32px; height: 32px; }
.flow-spinner--large  { width: 56px; height: 56px; }
.flow-spinner--xlarge { width: 96px; height: 96px; }

@media (prefers-reduced-motion: reduce) {
  .flow-spinner__overlay {
    animation: none;
    opacity: 1;
    transform: none;
  }
  .flow-spinner__base {
    opacity: 0.5;
  }
}
</style>
