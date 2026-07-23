<template>
  <span ref="wrapperRef" class="typewriter-wrapper" :class="className">
    <!-- 超长文本降级：纯文本渲染，零 span 节点，避免 DOM 暴增 -->
    <span v-if="tooLong">{{ text }}</span>
    <!-- 正常文本：逐字 span + 竖线光标跟随 -->
    <span v-else class="char-container" ref="containerRef">
      <span
        v-for="(ch, i) in chars"
        :key="i"
        :ref="el => { if (el) charRefs[i] = el }"
        class="char"
        :class="{ 'char--visible': i < visible }"
      >{{ ch }}</span>
      <!-- 竖线光标：absolute 定位，2px 宽 × 1.2em 高，在当前字符右侧闪烁 -->
      <span
        v-if="cursorVisible && chars.length > 0"
        class="cursor-block"
        :style="cursorStyle"
      />
    </span>
  </span>
</template>

<script setup>
/**
 * ════════════════════════════════════════════════════════════════
 *  Typewriter — 打字机效果组件 (Bard v7)
 * ════════════════════════════════════════════════════════════════
 *  特性：
 *    1. Array.from(text) 拆字，兼容中文/Emoji/代理对
 *    2. inView { once: true } 仅在进入视口时触发一次
 *    3. maxLength 防御：超长文本直接纯文本渲染，避免 DOM 节点暴增
 *    4. loop 模式：打字 → 停留 → 删除 → 循环（用于登录页 slogan 轮播）
 *    5. 终端高亮块光标：absolute 定位，跟随当前字符移动
 *       - 打字时向右推进，覆盖新打出的字符
 *       - 删除时向左回退，覆盖即将被删的字符
 *       - 无字符时回到起始位置，半透明闪烁
 *    6. onUnmounted 清理所有 timer + stop inView + stop animate + remove resize
 *
 *  性能注意：
 *    - 默认 maxLength=120，超过则降级为纯文本
 *    - 每个字符一个 <span>，长文本会显著增加 DOM 节点数
 *    - 光标位置通过 getBoundingClientRect 计算，visible 变化时 nextTick 更新
 * ════════════════════════════════════════════════════════════════
 */
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { animate, inView } from 'motion'

const props = defineProps({
  text: { type: String, required: true },
  speed: { type: Number, default: 0.045 },          // 每字耗时（秒），45ms/字
  delay: { type: Number, default: 0 },                // 初始延迟（秒）
  className: { type: String, default: '' },
  maxLength: { type: Number, default: 120 },          // 超长降级阈值
  loop: { type: Boolean, default: false },            // 循环模式
  loopPause: { type: Number, default: 2200 },         // 打完后停留时长（ms）
  showCursor: { type: Boolean, default: true },       // 是否显示光标
  hideCursorOnComplete: { type: Boolean, default: false }, // 打字完成后隐藏光标（非 loop 场景）
})

// 循环周期完成事件：父组件监听后切换下一段文本
const emit = defineEmits(['cycle-complete'])

const wrapperRef = ref(null)
const containerRef = ref(null)
// DOM 引用不需要响应式 —— 用普通数组避免渲染期间 charRefs[i]=el 触发响应式更新，
// 否则每个字符都会产生一条 Vue 警告（正好等于字符数）
const charRefs = []
const visible = ref(0)

// Array.from 兼容中文/Emoji/代理对（split('') 会拆坏代理对）
const chars = computed(() => Array.from(props.text))
const tooLong = computed(() => chars.value.length > props.maxLength)

// 无障碍降级标记：减少动画偏好下直接显示全文，不跑打字动画与光标
const reducedMotion = ref(false)
const isDegraded = computed(() => tooLong.value || reducedMotion.value)

// 光标是否应该显示
// - showCursor=false：不显示
// - 降级模式（超长/reduced-motion）：不显示
// - hideCursorOnComplete=true 且打字完成（visible === chars.length）：不显示
// - 无字符（visible <= 0 且无 hideCursorOnComplete）：显示在起始位置闪烁
const cursorVisible = computed(() => {
  if (!props.showCursor || isDegraded.value) return false
  if (props.hideCursorOnComplete && visible.value >= chars.value.length) return false
  return true
})

// 光标索引：指向光标所在位置的字符
//   打字时：cursorIndex = visible - 1（光标在该字符右侧）
//   删除时：cursorIndex = visible - 1（光标在即将被删的字符右侧）
//   无字符时：cursorIndex = -1（光标回到第一个字符位置闪烁）
const cursorIndex = computed(() => {
  if (!cursorVisible.value) return -1
  if (visible.value <= 0) return -1
  return visible.value - 1
})

// 光标位置：竖线光标只需 left（宽高固定为 2px × 1.2em，由 CSS 控制）
const cursorStyle = ref({ left: '0px' })

/**
 * 更新光标位置：定位到当前字符的右侧（+1px 偏移，视觉上贴着字符右边）
 * - 有字符时：left = 字符 left + 字符 width + 1px
 * - 无字符时：left = 第一个字符的 left（起始位置）
 */
function updateCursorPosition() {
  const container = containerRef.value
  if (!container) return
  const containerRect = container.getBoundingClientRect()

  const idx = cursorIndex.value
  // 无字符：定位到第一个字符位置（字符已渲染，只是 opacity:0）
  const targetIdx = idx >= 0 ? idx : 0
  const el = charRefs[targetIdx]
  if (!el) return

  const charRect = el.getBoundingClientRect()
  if (idx >= 0) {
    // 有字符：光标在字符右侧 +1px
    cursorStyle.value = {
      left: (charRect.left - containerRect.left + charRect.width + 1) + 'px',
    }
  } else {
    // 无字符：光标在第一个字符左侧（起始位置）
    cursorStyle.value = {
      left: (charRect.left - containerRect.left) + 'px',
    }
  }
}

// 监听 visible 变化，nextTick 后更新光标位置（DOM 已更新）
watch(visible, () => {
  nextTick(() => {
    updateCursorPosition()
  })
})

// 窗口大小变化时重新计算光标位置
function handleResize() {
  updateCursorPosition()
}

// ===== 动画与定时器句柄 =====
let stopInView = null
let controls = null
let delayTimer = null   // 初始 delay 定时器
let pauseTimer = null   // loopPause / 300ms 停顿定时器

// 标记是否已开始过首次动画（避免 watch 在 onMounted 前误触发）
let started = false

/**
 * 清理所有进行中的动画与定时器
 * 在重置（watch）和卸载（onUnmounted）时调用
 */
function clearAll() {
  if (delayTimer) { clearTimeout(delayTimer); delayTimer = null }
  if (pauseTimer) { clearTimeout(pauseTimer); pauseTimer = null }
  if (controls) { controls.stop(); controls = null }
}

/**
 * 打字动画：从 0 递增到 total
 * visible 每帧更新 → watch 触发 → 光标跟随右移
 * @param {Function} [onComplete] - 完成回调
 */
function typeText(onComplete) {
  const total = chars.value.length
  const duration = total * props.speed
  controls = animate(0, total, {
    duration,
    ease: 'linear',
    onUpdate: (v) => { visible.value = Math.round(v) },
    onComplete,
  })
}

/**
 * 回删动画：从 total 递减到 0
 * 删除 duration = 打字 duration * 0.6（删除稍慢，更从容）
 * visible 每帧递减 → watch 触发 → 光标跟随左移
 * @param {Function} [onComplete] - 完成回调
 */
function deleteText(onComplete) {
  const total = chars.value.length
  const duration = Math.max(total * props.speed * 0.6, 0.2)
  controls = animate(total, 0, {
    duration,
    ease: 'linear',
    onUpdate: (v) => { visible.value = Math.round(v) },
    onComplete,
  })
}

/**
 * loop 模式完整周期：
 *   打出完整句子 → 停留 loopPause → 逐字回删 → 停顿 300ms → emit('cycle-complete')
 * 父组件切换 text 后，watch 会重置 visible=0 并重新 runCycle
 */
function runCycle() {
  if (tooLong.value) {
    visible.value = chars.value.length
    return
  }
  typeText(() => {
    // 打完 → 停留 loopPause
    pauseTimer = setTimeout(() => {
      deleteText(() => {
        // 删完 → 停顿 300ms → 通知父组件切换文本
        pauseTimer = setTimeout(() => {
          emit('cycle-complete')
        }, 300)
      })
    }, props.loopPause)
  })
}

/**
 * 非 loop 模式：只打一次
 */
function typeOnce() {
  if (tooLong.value) {
    visible.value = chars.value.length
    return
  }
  typeText()
}

onMounted(() => {
  // 无障碍：减少动画偏好下直接显示全文，不跑 JS 打字动画与光标
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    reducedMotion.value = true
    visible.value = chars.value.length
    return
  }

  // 超长文本：直接全部可见，不走动画
  if (tooLong.value) {
    visible.value = chars.value.length
    return
  }

  // 初始定位光标到起始位置（首个字符尚未可见，光标 idle 闪烁）
  nextTick(() => updateCursorPosition())

  // once: true 防止反复触发
  stopInView = inView(
    wrapperRef.value,
    () => {
      delayTimer = setTimeout(() => {
        started = true
        if (props.loop) {
          runCycle()
        } else {
          typeOnce()
        }
      }, props.delay * 1000)
    },
    { once: true }
  )

  window.addEventListener('resize', handleResize)
})

/**
 * 监听 text 变化：父组件切换文本后重置并重新打字
 * - 清理当前动画与定时器
 * - 重置 visible=0
 * - 重新触发 runCycle（仅当已开始过，避免与 onMounted 的 delay 冲突）
 */
watch(() => props.text, () => {
  if (tooLong.value) {
    visible.value = chars.value.length
    return
  }
  clearAll()
  // 重置 charRefs（旧字符 DOM 已被 Vue 回收，索引需清空避免悬空引用）
  charRefs.length = 0
  visible.value = 0
  if (started) {
    if (props.loop) {
      runCycle()
    } else {
      typeOnce()
    }
  }
})

// 卸载时清理所有定时器、动画与监听，防止内存泄漏与"卸载后仍执行"
onUnmounted(() => {
  clearAll()
  if (stopInView) {
    stopInView()
    stopInView = null
  }
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.typewriter-wrapper {
  position: relative;
  display: inline-block;
}

.char-container {
  position: relative;
  display: inline-block;
  white-space: pre-wrap;
  word-break: break-word;
}

/* 每个字符默认透明，char--visible 时淡入 */
.char {
  display: inline;
  opacity: 0;
  transition: opacity 0.08s ease-out;
}

.char--visible {
  opacity: 1;
}

/* 竖线光标：2px 宽 × 1.2em 高，墨黑色（登录页纸张主题），在当前字符右侧闪烁
   宽高固定，不跟随字符动态变化 */
.cursor-block {
  position: absolute;
  top: 0;
  width: 2px;
  height: 1.2em;
  background: var(--color-bard-ink, #1a1a1a);
  border-radius: 0;
  pointer-events: none;
  z-index: 1;
  transition: left 0.08s ease-out;
  opacity: 1;
  animation: cursor-blink 1s step-end infinite;
}

@keyframes cursor-blink {
  0%, 50% { opacity: 1; }
  50.01%, 100% { opacity: 0; }
}

/* 无障碍降级：减少动画偏好时停止闪烁，保持半透明 */
@media (prefers-reduced-motion: reduce) {
  .cursor-block {
    transition: none;
    animation: none;
    opacity: 0.5;
  }
}
</style>
