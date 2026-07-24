<script setup lang="ts">
/**
 * LandingNavbar — 落地页顶部导航
 * - 滚动 > 20px：高度收缩 + 毛玻璃 + 底部边框显现
 * - 右侧主题切换按钮（复用 useTheme）
 * - 左侧品牌标识，中部锚点导航
 */
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import BrandMark from '@/components/ui/BrandMark.vue'
import { useTheme } from '@/composables/useTheme'

const router = useRouter()
const { currentTheme, toggleTheme } = useTheme()

const scrolled = ref(false)

const onScroll = () => {
  scrolled.value = window.scrollY > 20
}

const goWorkbench = () => {
  router.push('/workbench')
}

const scrollTo = (id: string) => {
  const el = document.getElementById(id)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

onMounted(() => {
  window.addEventListener('scroll', onScroll, { passive: true })
  onScroll()
})
onBeforeUnmount(() => {
  window.removeEventListener('scroll', onScroll)
})
</script>

<template>
  <header class="landing-nav" :class="{ 'is-scrolled': scrolled }">
    <div class="nav-inner">
      <a class="nav-brand" href="/" @click.prevent="scrollTo('top')">
        <BrandMark :size="scrolled ? 24 : 28" />
      </a>

      <nav class="nav-links">
        <a href="#pipeline" @click.prevent="scrollTo('pipeline')">流水线</a>
        <a href="#value" @click.prevent="scrollTo('value')">价值</a>
        <a href="#stats" @click.prevent="scrollTo('stats')">数据</a>
      </nav>

      <div class="nav-actions">
        <button
          class="theme-toggle"
          :aria-label="currentTheme === 'dark' ? '切换到浅色' : '切换到深色'"
          :title="currentTheme === 'dark' ? '浅色模式' : '深色模式'"
          @click="toggleTheme"
        >
          <span v-if="currentTheme === 'dark'" class="icon-sun" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round">
              <circle cx="12" cy="12" r="4.2" />
              <path d="M12 2.5v2.2M12 19.3v2.2M4.6 4.6l1.6 1.6M17.8 17.8l1.6 1.6M2.5 12h2.2M19.3 12h2.2M4.6 19.4l1.6-1.6M17.8 6.2l1.6-1.6" />
            </svg>
          </span>
          <span v-else class="icon-moon" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
              <path d="M20 14.2A8.4 8.4 0 0 1 9.8 4 6.6 6.6 0 1 0 20 14.2Z" />
            </svg>
          </span>
        </button>

        <button class="nav-cta" @click="goWorkbench">开始使用</button>
      </div>
    </div>
  </header>
</template>

<style scoped>
.landing-nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  height: 80px;
  background: transparent;
  border-bottom: 1px solid transparent;
  transition:
    height var(--duration-normal) var(--ease),
    background-color var(--duration-normal) var(--ease),
    border-color var(--duration-normal) var(--ease),
    backdrop-filter var(--duration-normal) var(--ease);
}
.landing-nav.is-scrolled {
  height: 60px;
  background: var(--nav-bg-solid);
  backdrop-filter: saturate(180%) blur(18px);
  -webkit-backdrop-filter: saturate(180%) blur(18px);
  border-bottom-color: var(--border-light);
}

.nav-inner {
  max-width: var(--content-max-width);
  margin: 0 auto;
  height: 100%;
  padding: 0 var(--space-3xl);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2xl);
}

.nav-brand {
  display: inline-flex;
  align-items: center;
  color: var(--fg);
}

.nav-links {
  display: flex;
  align-items: center;
  gap: var(--space-2xl);
}
.nav-links a {
  font-size: 0.85rem;
  letter-spacing: 0.02em;
  color: var(--muted-fg);
  transition: color var(--duration-fast) var(--ease);
}
.nav-links a:hover {
  color: var(--fg);
}

.nav-actions {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.theme-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: var(--radius-full);
  color: var(--fg);
  background: transparent;
  border: 1px solid var(--border-light);
  transition: background-color var(--duration-fast) var(--ease),
    border-color var(--duration-fast) var(--ease);
}
.theme-toggle:hover {
  background: var(--hover-bg);
}

.nav-cta {
  display: inline-flex;
  align-items: center;
  height: 34px;
  padding: 0 var(--space-xl);
  font-size: 0.85rem;
  letter-spacing: 0.02em;
  color: var(--bg);
  background: var(--fg);
  border-radius: var(--radius-full);
  transition: opacity var(--duration-fast) var(--ease);
}
.nav-cta:hover {
  opacity: 0.82;
}

@media (max-width: 720px) {
  .nav-links {
    display: none;
  }
  .nav-inner {
    padding: 0 var(--space-xl);
  }
}
</style>
