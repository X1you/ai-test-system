<template>
  <div class="login-page">
    <!-- ===== 后台布局"幽灵预演"：极淡竖线暗示侧栏存在（宽屏 only） ===== -->
    <div class="layout-ghost" aria-hidden="true">
      <span class="layout-ghost__line layout-ghost__line--left"></span>
      <span class="layout-ghost__line layout-ghost__line--right"></span>
    </div>

    <!-- ===== 主内容区域（动画时向两侧退让） ===== -->
    <div class="login-content" ref="contentRef" :class="{ 'content-shrunk': showLoginForm }">
      <!-- Bard 艺术字（上下双冷金线 — 方案 3.x 视觉锚点） -->
      <div ref="bardWordmarkRef" class="bard-wordmark" :class="{ 'bard-wordmark--shrunk': showLoginForm }">
        <div class="bard-line bard-line--top" aria-hidden="true"></div>
        <h1 ref="bardTitleRef" class="bard-title">Bard</h1>
        <div class="bard-line bard-line--bottom" aria-hidden="true"></div>
      </div>

      <!-- Slogan 区域（主标语大字轮播 + 副标语小字单次，错峰出现） -->
      <div ref="sloganAreaRef" class="slogan-area" :class="{ 'slogan-area--shrunk': showLoginForm }">
        <!-- 主 Slogan（第一行，大，慢，有重量） -->
        <p class="slogan-main">
          <Typewriter
            :text="currentSlogan"
            :speed="0.045"
            :delay="0.3"
            :loop="true"
            :loop-pause="2200"
            @cycle-complete="nextSlogan"
          />
        </p>
        <!-- 副 Slogan（第二行，小，浅色；主打完停留 600ms 后才开始打字，单条不轮播，打完光标消失） -->
        <p class="slogan-sub">
          <Typewriter
            :text="subSlogan"
            :speed="0.025"
            :delay="1.4"
            :loop="false"
            :hide-cursor-on-complete="true"
          />
        </p>
      </div>

      <!-- "开始使用"按钮（点击后立即 v-if 消失） -->
      <button v-if="!showLoginForm" ref="enterBtnRef" class="enter-btn" @click="handleEnterClick">
        开始使用
      </button>
    </div>

    <!-- ===== 登录框（柔和浮现，极简克制） ===== -->
    <div v-if="showLoginForm" ref="loginFormRef" class="login-form-wrapper">
      <div class="login-form">
        <!-- 保留原始 @submit.prevent + 表单结构 -->
        <form class="form-inner" @submit.prevent="handleLogin">
          <div class="form-field">
            <label for="username" class="form-label">用户名</label>
            <input
              id="username"
              v-model="form.username"
              type="text"
              class="form-input"
              autocomplete="username"
              :disabled="loading"
              placeholder="请输入用户名"
              required
            />
          </div>

          <div class="form-field">
            <label for="password" class="form-label">密码</label>
            <input
              id="password"
              v-model="form.password"
              type="password"
              class="form-input"
              autocomplete="current-password"
              :disabled="loading"
              placeholder="请输入密码"
              required
            />
          </div>

          <!-- 保留原始 v-if 错误提示 + role="alert" -->
          <p v-if="errorMsg" class="form-error" role="alert">{{ errorMsg }}</p>

          <!-- 保留原始 :disabled 绑定逻辑 -->
          <button
            type="submit"
            class="form-submit"
            :disabled="loading || !form.username || !form.password"
          >
            {{ loading ? '验证中…' : '登 录' }}
          </button>
        </form>
      </div>
    </div>

    <!-- ===== 底部品牌信息（页面锚点，增加完成感） ===== -->
    <div class="brand-footer">✦ Bard v7</div>
  </div>
</template>

<script setup>
/**
 * ════════════════════════════════════════════════════════════════
 *  Login.vue — 纯白叙事诗登录页 (Bard v7)
 * ════════════════════════════════════════════════════════════════
 *  设计：
 *    - 纯白纸张底 + 墨黑文字 + 冷金点缀（克制）
 *    - Bard 艺术字（Georgia 衬线 + 上下双线）作为视觉锚点
 *    - 打字机 slogan 轮播（哲学型金句）
 *    - 点击"开始使用"→ 主内容缩小虚化 + 登录框 transition 浮入
 *
 *  业务逻辑（完全保留原版，未做任何改动）：
 *    - api.post('/auth/login', { json }) + ApiError 错误处理
 *    - setAuth(resp.access_token, {...})
 *    - route.query.redirect 跳转
 * ════════════════════════════════════════════════════════════════
 */
import { reactive, ref, nextTick, onMounted, onBeforeUnmount, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { api, ApiError } from '../composables/useApi'
import { setAuth } from '../composables/useAuth'
import { Typewriter } from '@/components/ui'
import { animate } from 'motion'

// 动效语言（与后台统一）—— Motion One 原生 spring 物理动画
//   SPRING_MAIN：主要元素（Bard 标题、Slogan、按钮）入场，stiffness 350 / damping 30
//   SPRING_CARD：卡片/登录框浮现，stiffness 320 / damping 28（略软，有重量感）
//   SPRING_HOVER：悬停交互（下划线展开），stiffness 400 / damping 30（更脆快）
//   EASE_AUX：辅助元素（副 Slogan、光晕、装饰线），0.5s ease-out（无弹簧，克制）
const SPRING_MAIN = { type: 'spring', stiffness: 350, damping: 30, mass: 1 }
const SPRING_CARD = { type: 'spring', stiffness: 320, damping: 28, mass: 1 }
const SPRING_HOVER = { type: 'spring', stiffness: 400, damping: 30, mass: 1 }
const EASE_AUX = 'ease-out'

const router = useRouter()
const route = useRoute()

// ===== 表单状态（保留原版） =====
const form = reactive({
  username: '',
  password: '',
})
const loading = ref(false)
const errorMsg = ref('')

// ===== 登录框显示控制 =====
const showLoginForm = ref(false)

// ===== Slogan 金句池（P1 组合 · 哲学型） =====
const slogans = [
  '测试的本质，是理解需求',
  '质量，始于清晰的表达',
  '需求是问题，用例是答案',
]

const sloganIndex = ref(0)
const currentSlogan = ref(slogans[0])

// Typewriter 完成一个周期（打出→停留→回删→停顿）后回调，切换下一条
function nextSlogan() {
  sloganIndex.value = (sloganIndex.value + 1) % slogans.length
  currentSlogan.value = slogans[sloganIndex.value]
}

// ===== 副标语（功能型，单条不轮播；主 Slogan 轮播时保持不变） =====
// 时序：主 Slogan 首条打完（delay 0.3 + 11字×0.045 ≈ 0.795s）+ 停留 600ms
//       → 副 Slogan 在 1.4s 开始打字，形成"注释"层次
const subSlogan = '上传需求文档 · AI 自动生成全量用例'

// ===== DOM 引用 =====
const contentRef = ref(null)
const bardWordmarkRef = ref(null)
const bardTitleRef = ref(null)
const sloganAreaRef = ref(null)
const enterBtnRef = ref(null)
const loginFormRef = ref(null)

// 持有所有动画句柄，卸载时统一清理
let animControls = []

// 鼠标视差句柄（onBeforeUnmount 时移除）
let onMouseMove = null
// 视差 rAF 句柄（onBeforeUnmount 时取消）
let parallaxRafId = null

// ===== 页面入场动画（stagger 错落，与后台统一 spring 物理感） =====
// 主要元素（Bard 标题、Slogan、按钮）：SPRING_MAIN，0.7s 视觉时长
// 辅助元素（title 内层浮出）：EASE_AUX，0.5s（无弹簧，克制）
onMounted(() => {
  const wordmark = bardWordmarkRef.value
  const title = bardTitleRef.value
  const slogan = sloganAreaRef.value
  const btn = enterBtnRef.value

  // wordmark 容器（主要元素）：opacity 0→1 + y -8→0，SPRING_MAIN，0.7s
  if (wordmark) {
    animate(
      wordmark,
      { opacity: [0, 1], y: [-8, 0] },
      { ...SPRING_MAIN, duration: 0.7, delay: 0 }
    )
  }
  // bard-title 内层（辅助元素）：scale 1.02→1 + opacity 0.6→1，EASE_AUX，0.5s
  if (title) {
    animate(
      title,
      { scale: [1.02, 1], opacity: [0.6, 1] },
      { duration: 0.5, easing: EASE_AUX, delay: 0 }
    )
  }
  // Slogan（主要元素）：opacity 0→1 + y 6→0，SPRING_MAIN，0.7s，delay 0.25
  if (slogan) {
    animate(
      slogan,
      { opacity: [0, 1], y: [6, 0] },
      { ...SPRING_MAIN, duration: 0.7, delay: 0.25 }
    )
  }
  // 按钮（主要元素）：opacity 0→1，SPRING_MAIN，0.7s，delay 0.5
  if (btn) {
    animate(
      btn,
      { opacity: [0, 1] },
      { ...SPRING_MAIN, duration: 0.7, delay: 0.5 }
    )
  }

  // ===== 鼠标视差：Bard 标题 ±4px + 光晕 ±8px（弹簧感跟随） =====
  // 用 requestAnimationFrame 节流 + 弹簧插值（指数衰减追赶目标），对齐屏幕刷新率
  // 登录框显示后停止视差（避免与背景退让的 transform 冲突）
  // 延迟到入场动画结束后（主要元素最晚 0.5+0.7=1.2s）才启用，避免覆盖入场 scale
  let parallaxEnabled = false
  let pendingEvent = null
  // 当前实际位移（弹簧插值后的值），目标位移（鼠标即时值）
  let curX = 0, curY = 0, tgtX = 0, tgtY = 0
  // 弹簧系数：stiffness≈300/damping≈25 的近似（每帧逼近目标的比例）
  // 0.18 对应 ~60fps 下约 300ms 趋近，有轻微过冲感
  const SPRING_FACTOR = 0.18

  setTimeout(() => { parallaxEnabled = true }, 1250)

  onMouseMove = (e) => {
    if (!parallaxEnabled || showLoginForm.value || !title) return
    pendingEvent = e
    if (parallaxRafId !== null) return
    parallaxRafId = requestAnimationFrame(() => {
      parallaxRafId = null
      const ev = pendingEvent
      if (!ev) return

      // 鼠标相对屏幕中心的归一化位置（-1 ~ 1）
      const cx = window.innerWidth / 2
      const cy = window.innerHeight / 2
      const nx = (ev.clientX - cx) / cx  // -1 ~ 1
      const ny = (ev.clientY - cy) / cy  // -1 ~ 1

      // 目标位移：标题 ±4px，光晕 ±8px（比标题稍多，营造层次感）
      tgtX = nx * 4
      tgtY = ny * 4

      // 弹簧插值：当前值向目标值按 SPRING_FACTOR 逼近（指数衰减，有弹簧感）
      curX += (tgtX - curX) * SPRING_FACTOR
      curY += (tgtY - curY) * SPRING_FACTOR
      title.style.transform = `translate(${curX}px, ${curY}px)`

      // 光晕偏移 ±8px：通过 CSS 变量传递给 ::before（也用弹簧插值，稍快）
      const glowX = nx * 8
      const glowY = ny * 8
      title.style.setProperty('--glow-x', `${glowX}px`)
      title.style.setProperty('--glow-y', `${glowY}px`)
    })
  }

  // 无障碍：减少动画偏好下不注册鼠标视差（方案 6.4）
  // 原因：CSS 的 prefers-reduced-motion 媒体查询无法接管 JS 直接操作 style.transform，
  // 必须在此显式判断，否则 reduce 用户仍会被视差扰动。
  if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    window.addEventListener('mousemove', onMouseMove)
  }
})

// onBeforeUnmount 移除鼠标视差监听 + 清理 rAF
onBeforeUnmount(() => {
  if (parallaxRafId !== null) {
    cancelAnimationFrame(parallaxRafId)
    parallaxRafId = null
  }
  if (onMouseMove) {
    window.removeEventListener('mousemove', onMouseMove)
    onMouseMove = null
  }
})

// ===== 点击"开始使用"→ 背景退让 + 登录框卡片浮现（与后台卡片动效一致） =====
// 动画时序（spring 物理感，错开衔接）：
//   0.00s: 背景 scale 1→0.85（SPRING_CARD，先退让）
//   0.10s: 登录框卡片浮现 opacity 0→1 + y 8→0（SPRING_CARD，微微上浮，无 scale）
//   0.65s: 背景 blur 0→3px（EASE_AUX，登录框浮现后错开虚化收尾）
function handleEnterClick() {
  showLoginForm.value = true

  nextTick(() => {
    const login = loginFormRef.value
    const content = contentRef.value

    if (!login || !content) return

    // 清空旧句柄
    animControls.forEach((c) => c && c.stop && c.stop())
    animControls = []

    // 1. 背景 scale 退让：1→0.85，SPRING_CARD（先开始）
    animControls.push(
      animate(
        content,
        { scale: [1, 0.85] },
        { ...SPRING_CARD, duration: 0.6 }
      )
    )

    // 2. 登录框卡片浮现：opacity 0→1 + y 8→0（微微上浮，无 scale）
    //    SPRING_CARD，0.6s，延迟 0.1s 启动（背景退让开始 100ms 后跟上）
    animControls.push(
      animate(
        login,
        { opacity: [0, 1], y: [8, 0] },
        { ...SPRING_CARD, duration: 0.6, delay: 0.1 }
      )
    )

    // 3. 背景 blur 虚化：0→3px，EASE_AUX，0.3s
    //    延迟 0.65s 启动（登录框 0.7s 完成后错开再虚化收尾）
    animControls.push(
      animate(
        content,
        { filter: ['blur(0px)', 'blur(3px)'] },
        { duration: 0.3, easing: EASE_AUX, delay: 0.65 }
      )
    )
  })
}

// ===== 登录提交（保留原始逻辑，仅加重入保护） =====
async function handleLogin() {
  // 重入保护：防止请求未返回前重复提交。按钮虽在 loading 态 disabled，
  // 但键盘 Enter 或辅助技术仍可能二次触发 submit，需在函数入口短路。
  if (loading.value) return
  loading.value = true
  errorMsg.value = ''

  try {
    const resp = await api.post('/auth/login', {
      json: {
        username: form.username,
        password: form.password,
      },
    })

    // 持久化 token + 用户信息
    setAuth(resp.access_token, {
      username: resp.username,
      role: resp.role,
    })

    // 跳转到 redirect 参数或首页
    const redirect = route.query.redirect || '/'
    router.push(redirect)
  } catch (e) {
    if (e instanceof ApiError) {
      if (e.status === 429) {
        errorMsg.value = e.data?.detail || '登录尝试过于频繁，请稍后再试'
      } else if (e.status === 401) {
        errorMsg.value = '用户名或密码错误'
      } else {
        errorMsg.value = e.data?.detail || `登录失败（${e.status}）`
      }
    } else {
      errorMsg.value = '网络错误，请检查连接后重试'
    }
  } finally {
    loading.value = false
  }
}

// 卸载时清理所有动画句柄
onUnmounted(() => {
  animControls.forEach((c) => c && c.stop && c.stop())
  animControls = []
})
</script>

<style scoped>
/* Tailwind v4：Vue SFC 的 <style scoped> 使用 @apply 必须用 @reference 引用主 CSS，
   否则报 "Cannot apply unknown utility class" */
@reference "../styles/globals.css";

/* ===== 页面布局（白 → 墨蓝渐变，与后台呼应） ===== */
/* 中央 60% 区域接近纯白，边缘微微泛墨蓝（#e8ecf2 / #d5dae6），
   像"暮色从边缘渗入"，消除与后台墨蓝的颜色断层。
   叠加极淡冷金暖意（rgba(212,184,122,0.04)）保留品牌色 */
.login-page {
  @apply min-h-screen w-full flex items-center justify-center overflow-hidden relative;
  background:
    radial-gradient(ellipse at 50% 30%, rgba(212, 184, 122, 0.04) 0%, transparent 60%),
    radial-gradient(ellipse at 50% 30%, #ffffff 0%, #f5f6fa 40%, #e8ecf2 70%, #d5dae6 100%);
}

/* 页面底部极细墨蓝渐变线（与后台顶部衔接）：只在宽屏显示，避免窄屏拥挤
   位置 bottom 上方 8px，高度 2px，透明 → #0b0e14（墨蓝）→ 透明 */
.login-page::after {
  content: '';
  position: absolute;
  bottom: 8px;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(
    to right,
    rgba(11, 14, 20, 0) 0%,
    rgba(11, 14, 20, 0.15) 50%,
    rgba(11, 14, 20, 0) 100%
  );
  pointer-events: none;
  z-index: 5;
}

@media (max-width: 1024px) {
  .login-page::after {
    display: none;
  }
}

/* ===== 后台布局"幽灵预演"：极淡竖线暗示侧栏存在 =====
   左竖线在 64px（后台侧栏宽度），右竖线对称；高度 30%，顶部对齐 Bard 标题底部
   rgba(11,14,20,0.03) 极淡，是后台侧栏的"幽灵"，宽屏 only */
.layout-ghost {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 1;
}

.layout-ghost__line {
  position: absolute;
  top: 30%;
  height: 30%;
  width: 1px;
  background: rgba(11, 14, 20, 0.03);
}

.layout-ghost__line--left {
  left: 64px;
}

.layout-ghost__line--right {
  right: 64px;
}

@media (max-width: 1024px) {
  .layout-ghost {
    display: none;
  }
}

/* ===== 主内容区域 ===== */
/* 注意：不使用 CSS transition，transform/filter 由 Motion animate 直接驱动，
   避免 transition 与 animate 的 inline style 冲突导致抖动
   pb-10 = 40px（按钮底部到页面底部至少 40px） */
.login-content {
  @apply flex flex-col items-center justify-center max-w-4xl w-full px-6 pb-10;
  position: relative;
  transform-origin: center center;
}

/* content-shrunk 类保留为标记（animate 接管实际变换），不在此设置样式 */

/* "开始使用"按钮下方极细冷金线（暗示后台边框材质）
   挂在 login-content（按钮 v-if 消失后容器仍在），absolute 定位在底部
   距底边 20px（按钮下方约 20px），宽度 50% 居中
   rgba(201,169,110,0.06) 呼应后台卡片边框 rgba(201,169,110,0.12)，更克制 */
.login-content::after {
  content: '';
  position: absolute;
  left: 50%;
  bottom: 20px;
  width: 50%;
  height: 0;
  border-bottom: 1px solid rgba(201, 169, 110, 0.06);
  transform: translateX(-50%);
  pointer-events: none;
  transition: opacity 0.3s ease;
}

/* 显示登录框后冷金线随内容一起淡出退让 */
.content-shrunk::after {
  opacity: 0;
}

/* ===== Bard 艺术字 ===== */
/* mb-5 = 20px（Bard 底部到 Slogan 顶部）
   margin-left: 32px 让标题微微偏右，让出左侧空间给"幽灵侧栏"
   偏移极其轻微（约占容器 3.5%），用户不明确感知但视觉重心微偏右 */
.bard-wordmark {
  @apply flex flex-col items-center mb-5 transition-all duration-800 ease-in-out;
  position: relative;
  margin-left: 32px;
}

/* 后台卡片材质预览：Bard 标题底部下方 12px 的极细横条
   模仿后台卡片边框的"冷金线"质感，但极其克制（rgba(11,14,20,0.04)）
   宽度 60% 居中，absolute 避免影响 flex 布局 */
.bard-wordmark::after {
  content: '';
  position: absolute;
  left: 50%;
  bottom: -12px;
  width: 60%;
  height: 1px;
  transform: translateX(-50%);
  background: rgba(11, 14, 20, 0.04);
  pointer-events: none;
}

.bard-wordmark--shrunk {
  @apply opacity-40;
}

.bard-title {
  font-family: var(--font-serif);
  font-weight: 700;
  font-style: italic;
  font-size: clamp(80px, 14vw, 160px);
  /* 字母间距微调：0.04em 时 r-d 偏挤，提到 0.05em 整体更舒展 */
  letter-spacing: 0.05em;
  line-height: 1.0;
  color: #1a1a1a;
  position: relative;
  /* 视差由 JS 设置 transform，声明 will-change 优化合成层 */
  will-change: transform;
  /* 光晕偏移变量默认值（鼠标未移动时光晕居中） */
  --glow-x: 0px;
  --glow-y: 0px;
  /* 四层光晕叠加：冷金近距 + 冷金中距 + 墨蓝远距 + 底部微阴影
     冷金（rgba(201,169,110)）与墨蓝（rgba(11,14,20)）同时投射，
     让标题在白→墨蓝渐变背景上颜色过渡更自然 */
  text-shadow:
    0 0 20px rgba(201, 169, 110, 0.15),
    0 0 60px rgba(201, 169, 110, 0.08),
    0 0 120px rgba(11, 14, 20, 0.04),
    0 4px 20px rgba(0, 0, 0, 0.02);
}

/* 光晕伪元素：从字母正后方透出，有"来源感"而非浮在文字上
   光晕中心随鼠标位置偏移 ±8px（通过 --glow-x/--glow-y 变量） */
.bard-title::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 120%;
  height: 120%;
  /* translate(-50%,-50%) 保持居中，再叠加鼠标偏移变量 */
  transform: translate(calc(-50% + var(--glow-x)), calc(-50% + var(--glow-y)));
  background: radial-gradient(ellipse, rgba(212, 184, 122, 0.08), transparent 70%);
  filter: blur(30px);
  z-index: -1;
  pointer-events: none;
  transition: transform 0.3s ease-out;
}

/* ===== Bard 上下双冷金线（方案 3.x 视觉锚点） ===== */
/* 极细 1px 冷金渐变线，上下夹住 Bard 艺术字，强化"铭刻"感。
   上线短（40%）下线长（80%），打破对称避免呆板。
   #c9a96e 为暗色主题 accent，在纯白底上呈克制冷金。 */
.bard-line {
  height: 1px;
  background: linear-gradient(
    to right,
    rgba(201, 169, 110, 0) 0%,
    rgba(201, 169, 110, 0.5) 50%,
    rgba(201, 169, 110, 0) 100%
  );
  margin: 20px auto;
}

.bard-line--top {
  width: 40%;
}

.bard-line--bottom {
  width: 80%;
}

/* ===== Slogan 区域 ===== */
.slogan-area {
  @apply text-center mb-8 transition-all duration-800 ease-in-out;
}

/* 主 Slogan：大、慢、有重量；Playfair Display 衬线诗意
   text-2xl(24px)→md:text-3xl(30px)，#1a1a1a 深墨，tracking-wide */
.slogan-main {
  @apply text-2xl md:text-3xl font-light tracking-wide leading-snug;
  font-family: var(--font-serif);
  color: #1a1a1a;
}

/* 副 Slogan：小、浅色，有"注释感"；无衬线，单条不轮播
   text-sm(14px)→md:text-base(16px)，#8a8a8a 浅灰，mt-3(12px) */
.slogan-sub {
  @apply text-sm md:text-base font-light tracking-wide mt-3;
  font-family: var(--font-sans);
  color: #8a8a8a;
  min-height: 1.2em;  /* 占位，避免打字前后高度抖动 */
}

.slogan-area--shrunk {
  @apply opacity-30;
}

/* ===== "开始使用"按钮 ===== */
/* 悬停微交互：scale 1.02 + 下划线从中间向两端展开（::after scaleX）
   呼吸光晕：::before 脉动冷金光晕，周期 3s，暗示点击 */
.enter-btn {
  @apply bg-transparent text-[#1a1a1a] text-lg font-light tracking-widest;
  padding: 6px 4px;
  position: relative;
  /* 文字颜色：0.25s 过渡到冷金；transform 用 SPRING_HOVER 近似曲线 */
  transition: transform 0.3s cubic-bezier(0.3, 1.4, 0.5, 1), color 0.25s ease;
}

/* 呼吸光晕伪元素：脉动冷金辉光，周期 3s
   rgba(212,184,122) 更透亮的冷金 */
.enter-btn::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 140%;
  height: 300%;
  transform: translate(-50%, -50%);
  background: radial-gradient(ellipse, rgba(212, 184, 122, 0.18), transparent 60%);
  filter: blur(8px);
  z-index: -1;
  pointer-events: none;
  animation: btn-breathe 3s ease-in-out infinite;
}

@keyframes btn-breathe {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 0.6; }
}

/* 下划线伪元素：初始 scaleX(0) 居中，hover 时展开到 scaleX(1)
   SPRING_HOVER 近似曲线（stiffness 400/damping 30，脆快微弹），0.3s */
.enter-btn::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 1.5px;
  background: #1a1a1a;
  transform: scaleX(0);
  transform-origin: center;
  transition: transform 0.3s cubic-bezier(0.3, 1.4, 0.5, 1), background 0.3s ease;
}

.enter-btn:hover {
  /* 暗金 #b8860b 改为 #c9a96e（统一同色系，更干净） */
  @apply text-[#c9a96e];
  transform: scale(1.02);
}

.enter-btn:hover::after {
  transform: scaleX(1);
  background: #c9a96e;
}

/* ===== 登录框容器（固定居中浮层） ===== */
.login-form-wrapper {
  @apply fixed inset-0 flex items-center justify-center pointer-events-none z-50;
}

/* 登录框质感：磨砂白底（0.78 略透出墨蓝背景）+ 细腻磨砂（blur 16px）+ 墨蓝阴影 + 极淡白边
   叠加极浅网格颗粒纹理（radial-gradient 1px 圆点 × 16px），呼应后台卡片磨砂质感
   圆角 12px（与后台卡片统一），宽度 420px（与后台内容区常用宽度一致）
   ::before 绘制极淡"后台结构预览"：左上角色块（侧栏）+ 右侧空白（内容区），opacity 0.03 */
.login-form {
  @apply pointer-events-auto rounded-xl p-10 w-[420px] max-w-[92vw];
  position: relative;
  background:
    radial-gradient(circle, rgba(11, 14, 20, 0.01) 1px, transparent 1px),
    rgba(255, 255, 255, 0.78);
  background-size: 16px 16px, auto;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  box-shadow:
    0 0 0 1px rgba(11, 14, 20, 0.02),
    0 8px 40px rgba(11, 14, 20, 0.06),
    0 2px 8px rgba(11, 14, 20, 0.02);
  overflow: hidden;
}

/* 后台结构预览：左上角 40px 宽色块（对应侧栏）+ 右侧贯穿的极淡分隔线
   opacity 0.03 几乎不可见，特定角度能感知"这里有一个结构" */
.login-form::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 40px;
  height: 100%;
  background: linear-gradient(
    to right,
    rgba(11, 14, 20, 0.03) 0%,
    rgba(11, 14, 20, 0.03) 90%,
    rgba(11, 14, 20, 0) 100%
  );
  pointer-events: none;
  z-index: 0;
}

/* 表单内容层级高于 ::before 预览，确保输入可交互且文字清晰 */
.form-inner {
  @apply flex flex-col gap-6;
  position: relative;
  z-index: 1;
}

.form-field {
  @apply relative flex flex-col gap-1;
}

.form-label {
  @apply text-sm font-medium text-[#8a8a8a] font-light;
}

/* 输入框：极简，只保留极细底部边框，聚焦时变冷金色 + 1px→2px + 极淡光晕
   圆角 rounded-none（底部边框风格不需要圆角）
   用 box-shadow 模拟第 2px 边框（避免 border-width 变化导致布局抖动） */
.form-input {
  @apply w-full bg-transparent rounded-none border-b border-[#d0d0d0] py-2 px-1 text-[#1a1a1a];
  font-size: 15px;
  letter-spacing: 0.02em;
  /* 0.25s 过渡：border-color + box-shadow（模拟宽度+光晕） */
  transition: border-color 0.25s ease, box-shadow 0.25s ease;
}

.form-input::placeholder {
  /* #b8b8b8 比 #b0b0b0 更柔和一点 */
  @apply text-[#b8b8b8] font-light;
}

.form-input:focus {
  @apply outline-none;
  /* 聚焦：边框变冷金色 + box-shadow 模拟第 2px 宽度 + 下方极淡光晕 */
  border-bottom-color: #d4b87a;
  box-shadow:
    0 1px 0 #d4b87a,
    0 2px 8px rgba(212, 184, 122, 0.1);
}

.form-input:disabled {
  @apply opacity-60 cursor-not-allowed;
}

/* ===== 错误提示（保留 role="alert" 语义） ===== */
.form-error {
  @apply text-sm text-[#e8747c] text-center -mt-2;
}

/* ===== 提交按钮（描边胶囊，hover 冷金） ===== */
.form-submit {
  @apply w-full mt-2 py-3 bg-transparent text-[#1a1a1a] font-medium border border-[#d0d0d0] rounded-full transition-all duration-300;
  font-size: 14px;
  letter-spacing: 0.15em;
}

.form-submit:hover:not(:disabled) {
  /* hover 冷金：#b8860b → #c9a96e（统一同色系，更干净） */
  @apply bg-[#f5f0eb] text-[#c9a96e];
  border-color: #c9a96e;
}

.form-submit:disabled {
  @apply opacity-40 cursor-not-allowed;
}

/* ===== 底部品牌信息（页面锚点，增加完成感） ===== */
.brand-footer {
  position: fixed;
  bottom: 24px;
  left: 0;
  right: 0;
  text-align: center;
  font-size: 11px;
  letter-spacing: 0.1em;
  color: #d0d0d0;
  font-family: var(--font-serif);
  font-style: italic;
  pointer-events: none;
  z-index: 10;
}

/* ===== 响应式 ===== */
@media (max-width: 768px) {
  .login-form {
    @apply p-6 w-[95vw];
  }
  .bard-title {
    font-size: clamp(56px, 18vw, 96px);
  }
}

/* ===== 减少动画偏好 — 无障碍降级 ===== */
@media (prefers-reduced-motion: reduce) {
  .login-content,
  .bard-wordmark,
  .slogan-area {
    @apply transition-none;
  }
  /* 禁用按钮呼吸光晕动画 */
  .enter-btn::before {
    animation: none;
  }
}
</style>
