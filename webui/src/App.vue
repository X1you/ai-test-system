<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useTheme } from '@/composables/useTheme'
import AppSidebar from '@/components/AppSidebar.vue'
import ToastContainer from '@/components/ToastContainer.vue'

const route = useRoute()
const { currentTheme } = useTheme()

// 核心色由 :root / .dark 统一提供（单一暖白色系）；.landing 仅用于落地页导航透明 token
const isLanding = computed(() => route.path === '/')
const showSidebar = computed(() => route.path !== '/' && route.name !== 'not-found')

// 移动端侧边栏抽屉状态（< 768px 时侧边栏变 overlay drawer）
const mobileSidebarOpen = ref(false)
// 路由切换时自动关闭移动端抽屉，避免导航后抽屉残留
watch(() => route.path, () => {
  mobileSidebarOpen.value = false
})
</script>

<template>
  <div :class="[{ landing: isLanding }, { dark: currentTheme === 'dark' }]" class="app-root">
    <AppSidebar
      v-if="showSidebar"
      :mobile-open="mobileSidebarOpen"
      @close="mobileSidebarOpen = false"
    />
    <!-- 移动端遮罩：点击关闭抽屉 -->
    <div
      v-if="showSidebar && mobileSidebarOpen"
      class="sidebar-overlay"
      aria-hidden="true"
      @click="mobileSidebarOpen = false"
    />
    <!-- 移动端汉堡按钮（< 768px 可见） -->
    <button
      v-if="showSidebar"
      class="mobile-menu-btn"
      :aria-label="mobileSidebarOpen ? '关闭菜单' : '打开菜单'"
      :aria-expanded="mobileSidebarOpen"
      @click="mobileSidebarOpen = !mobileSidebarOpen"
    >
      <span aria-hidden="true">{{ mobileSidebarOpen ? '✕' : '☰' }}</span>
    </button>
    <main class="app-main" :class="{ 'app-main--full': !showSidebar }">
      <router-view v-slot="{ Component }">
        <Transition name="route-fade" mode="out-in">
          <component :is="Component" />
        </Transition>
      </router-view>
    </main>
    <ToastContainer />
  </div>
</template>

<style scoped>
.app-root {
  display: flex;
  min-height: 100vh;
  background: var(--bg);
  color: var(--fg);
  /* 暗色模式切换时背景/前景色平滑插值（@property 已注册 --bg/--fg 为 <color>） */
  transition: background-color var(--duration-slow) var(--ease),
    color var(--duration-slow) var(--ease);
}
.app-main {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
}
.app-main--full {
  /* 落地页无侧边栏，占满全宽 */
}

/* 路由过渡：250ms opacity cross-fade（reduced-motion 降级到瞬时） */
.route-fade-enter-active,
.route-fade-leave-active {
  transition: opacity 0.25s var(--ease);
}
.route-fade-enter-from,
.route-fade-leave-to {
  opacity: 0;
}

/* 移动端汉堡按钮：< 768px 显示，固定左上 */
.mobile-menu-btn {
  display: none;
  position: fixed;
  top: 0.5rem;
  left: 0.5rem;
  z-index: 60;
  width: 44px;
  height: 44px;
  align-items: center;
  justify-content: center;
  background: var(--panel-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: var(--text-md);
  color: var(--fg);
  cursor: pointer;
}

.sidebar-overlay {
  display: none;
}

/* 移动端：< 768px 启用抽屉 + 遮罩 */
@media (max-width: 767px) {
  .mobile-menu-btn {
    display: inline-flex;
  }
  .sidebar-overlay {
    display: block;
    position: fixed;
    inset: 0;
    z-index: 50;
    background: rgba(0, 0, 0, 0.4);
    animation: overlay-fade 0.2s var(--ease);
  }
}

@keyframes overlay-fade {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

/* reduced-motion 降级：路由过渡瞬时 */
@media (prefers-reduced-motion: reduce) {
  .route-fade-enter-active,
  .route-fade-leave-active {
    transition-duration: 0.01ms;
  }
  .sidebar-overlay {
    animation: none;
  }
}
</style>
