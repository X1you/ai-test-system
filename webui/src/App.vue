<template>
  <div class="app-layout" :class="{ 'app-layout--auth': !isAuthenticated }">
    <a href="#main-content" class="skip-link">跳到主内容</a>
    <AppSidebar v-if="isAuthenticated" />
    <main id="main-content" class="app-main" :class="{ 'app-main--full': !isAuthenticated }">
      <router-view />
    </main>
    <ToastContainer />
  </div>
</template>

<script setup>
import AppSidebar from './components/AppSidebar.vue'
import ToastContainer from './components/ToastContainer.vue'
import { isAuthenticated } from './composables/useAuth'
// useTheme 已在 AppSidebar 导入 useTheme.js 时自初始化为模块级单例，
// 此处无需再调用（原顶栏 toggle 已移除，主题切换入口统一收敛到侧边栏底部）。
</script>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
  /* 光线渐暗（方案 4.1）：主题切换时整页背景做 1.0s 渐变过渡。
     背景色取自语义 token --bg-app（light:#ffffff / dark:#0b0e14），
     [data-theme] 切换时该变量重新求值，触发 transition。 */
  background: var(--bg-app);
  transition: background-color 1.0s var(--ease-out, cubic-bezier(0.16, 1, 0.3, 1));
}

.app-main {
  flex: 1;
  min-width: 0;
  /* 修复布局 bug：侧边栏为 position:fixed，主内容必须留出对应左 padding，
     否则内容会被侧边栏遮挡。侧边栏宽度由 AppSidebar 通过 --sidebar-actual-w
     同步到 documentElement（默认 64px 折叠态，展开 220px）。 */
  padding: var(--space-xl) var(--space-2xl);
  padding-left: var(--sidebar-actual-w, 64px);
  overflow-y: auto;
  transition: padding-left var(--duration-normal) var(--ease-out);
}

/* 未登录页面（Login）— 全屏居中，无侧边栏 padding */
.app-main--full {
  padding: 0;
  padding-left: 0;
  display: flex;
  flex-direction: column;
}

/* 响应式：移动端侧边栏变为底部 tab bar，主内容无需左 padding */
@media (max-width: 768px) {
  .app-layout {
    flex-direction: column;
  }

  .app-main {
    padding: var(--space-lg);
    padding-left: var(--space-lg);
    padding-bottom: 72px; /* bottom tab bar space */
  }

  .app-main--full {
    padding: 0;
    padding-left: 0;
    padding-bottom: 0;
  }
}

/* 无障碍：减少动画偏好下取消 1.0s 光线渐暗，瞬切（方案 6.4） */
@media (prefers-reduced-motion: reduce) {
  .app-layout,
  .app-main {
    transition: none;
  }
}
</style>
