<!--
  ════════════════════════════════════════════════════════════════
  BardIcon — 统一图标组件 (Version Four — 填充插画)
  ════════════════════════════════════════════════════════════════
  设计意图：所有页面/组件引用图标都通过本组件，避免散落 SVG
  源文件：/Users/x1you/Downloads/bard.svg (390×444 填充插画)
  路径数据由 generate_icons.py 从源 SVG 自动生成到 bardIconData.js
  特性：
    - size: 任意像素值（预设 12/16/24/32/48/64/96/128）
    - variant: brand(currentColor填充) | emoji(白底黑线+高光) | inverted(黑底白线)
    - animated: 启用"呼吸流光"脉动效果（侧边栏 Logo 适用）
    - circle: 强制显示背景圆
    - aria-label / title: 自动注入无障碍标签
  ════════════════════════════════════════════════════════════════
-->
<template>
  <span
    class="bard-icon"
    :class="spanClass"
    :style="iconStyle"
    role="img"
    :aria-label="label"
  >
    <svg viewBox="0 0 512 512" fill="none" xmlns="http://www.w3.org/2000/svg">
      <title>{{ label }}</title>

      <!-- 背景圆（emoji / inverted 变体或显式 circle=true） -->
      <circle
        v-if="showBackground"
        cx="256" cy="256" r="252"
        :fill="bgColor"
        :stroke="lineColor"
        stroke-width="3"
      />

      <!-- 人物主体（填充插画，规范化自源文件 bard.svg） -->
      <g :transform="groupTransform">
        <path
          v-for="(p, i) in darkPaths"
          :key="'dark-' + i"
          :d="p.d"
          :transform="p.tf || undefined"
          :fill="lineColor"
        />
        <!-- 高光细节（仅 emoji 变体保留白色高光） -->
        <template v-if="variant === 'emoji'">
          <path
            v-for="(p, i) in lightPaths"
            :key="'light-' + i"
            :d="p.d"
            :transform="p.tf || undefined"
            :fill="lineColor"
          />
        </template>
      </g>
    </svg>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import {
  BARD_TRANSFORM as groupTransform,
  BARD_DARK_PATHS as darkPaths,
  BARD_LIGHT_PATHS as lightPaths,
} from '../assets/icons/bardIconData.js'

const props = defineProps({
  size: {
    type: [String, Number],
    default: 32,
    validator: (v) => {
      const n = Number(v)
      return Number.isFinite(n) && n >= 1 && n <= 1024
    },
  },
  variant: {
    type: String,
    default: 'brand',
    validator: (v) => ['brand', 'emoji', 'inverted'].includes(v),
  },
  animated: {
    type: Boolean,
    default: false,
  },
  circle: {
    type: Boolean,
    default: false,
  },
  color: {
    type: String,
    default: 'currentColor',
  },
  background: {
    type: String,
    default: null,
  },
  label: {
    type: String,
    default: 'Bard — AI Test System',
  },
})

// ─── 计算属性 ───
const sizeNum = computed(() => Number(props.size))

const lineColor = computed(() => {
  if (props.variant === 'emoji')    return props.color === 'currentColor' ? '#080808' : props.color
  if (props.variant === 'inverted') return props.color === 'currentColor' ? '#ffffff' : props.color
  return props.color
})

const bgColor = computed(() => {
  if (props.background) return props.background
  if (props.variant === 'emoji')    return '#ffffff'
  if (props.variant === 'inverted') return '#0a0a0a'
  return 'transparent'
})

const showBackground = computed(() =>
  props.circle || props.variant === 'emoji' || props.variant === 'inverted'
)

const PRESETS = [12, 16, 24, 32, 48, 64, 96, 128]

const presetSize = computed(() => {
  const s = sizeNum.value
  return PRESETS.includes(s) ? String(s) : 'custom'
})

const spanClass = computed(() => [
  `bard-icon--${presetSize.value}`,
  { 'bard-icon--animated': props.animated, 'bard-icon--circle': showBackground.value },
])

const iconStyle = computed(() =>
  presetSize.value === 'custom'
    ? { width: sizeNum.value + 'px', height: sizeNum.value + 'px' }
    : {}
)
</script>

<style scoped>
.bard-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  vertical-align: middle;
  line-height: 0;
}

.bard-icon svg {
  width: 100%;
  height: 100%;
  display: block;
  overflow: visible;
}

.bard-icon--12   { width: 12px;  height: 12px;  }
.bard-icon--16   { width: 16px;  height: 16px;  }
.bard-icon--24   { width: 24px;  height: 24px;  }
.bard-icon--32   { width: 32px;  height: 32px;  }
.bard-icon--48   { width: 48px;  height: 48px;  }
.bard-icon--64   { width: 64px;  height: 64px;  }
.bard-icon--96   { width: 96px;  height: 96px;  }
.bard-icon--128  { width: 128px; height: 128px; }

/* ─── 呼吸流光动画 ─── */
/* 填充插画无法用 stroke-dasharray 描边绘制，改用 opacity 呼吸 + 微妙缩放，
   模拟"吟游诗人吹笛"的流动呼吸感，呼应"流畅的故事讲述者"主题 */
.bard-icon--animated svg {
  animation: bard-breathe var(--duration-breath, 2400ms) var(--ease-breath, cubic-bezier(0.45, 0, 0.55, 1)) infinite;
  transform-origin: center;
}

@keyframes bard-breathe {
  0%, 100% {
    opacity: 0.82;
    transform: scale(0.96);
  }
  50% {
    opacity: 1;
    transform: scale(1.02);
  }
}

@media (prefers-reduced-motion: reduce) {
  .bard-icon--animated svg {
    animation: none;
    opacity: 1;
    transform: none;
  }
}
</style>
