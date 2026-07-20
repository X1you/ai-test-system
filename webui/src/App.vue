<template>
  <div class="app-layout">
    <a href="#main-content" class="skip-link">跳到主内容</a>
    <AppSidebar />
    <main id="main-content" class="app-main">
      <!-- 顶栏：全局操作区（外观切换） -->
      <div class="topbar">
        <button
          class="topbar__theme-btn"
          :aria-label="`切换外观（当前：${theme === 'dark' ? '暗色' : '亮色'}）`"
          :title="theme === 'dark' ? '切换到亮色模式' : '切换到暗色模式'"
          @click="toggleTheme"
        >
          <!-- 暗色下显示太阳（点击切换到亮色） -->
          <svg v-if="theme === 'dark'" viewBox="0 0 20 20" width="18" height="18" aria-hidden="true">
            <path fill="currentColor" d="M10 13a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm0-8a1 1 0 0 1-1-1V3a1 1 0 1 1 2 0v1a1 1 0 0 1-1 1zm0 12a1 1 0 0 1-1-1v-1a1 1 0 1 1 2 0v1a1 1 0 0 1-1 1zm8-7h-1a1 1 0 1 0 0 2h1a1 1 0 1 0 0-2zM4 10a1 1 0 0 1-1 1H2a1 1 0 1 1 0-2h1a1 1 0 0 1 1 1zm12.7-6.7a1 1 0 0 1 0 1.4l-.7.7a1 1 0 0 1-1.4-1.4l.7-.7a1 1 0 0 1 1.4 0zM5.4 15.6l-.7.7a1 1 0 0 1-1.4-1.4l.7-.7a1 1 0 0 1 1.4 1.4zm9.2 0a1 1 0 0 1 1.4-1.4l.7.7a1 1 0 0 1-1.4 1.4l-.7-.7zM5.4 5.4a1 1 0 0 1-1.4 0l-.7-.7a1 1 0 0 1 1.4-1.4l.7.7a1 1 0 0 1 0 1.4z"/>
          </svg>
          <!-- 亮色下显示月亮（点击切换到暗色） -->
          <svg v-else viewBox="0 0 20 20" width="18" height="18" aria-hidden="true">
            <path fill="currentColor" d="M14.5 11a6 6 0 0 1-7.4-7.4A6 6 0 1 0 14.5 11z"/>
          </svg>
        </button>
      </div>
      <router-view />
    </main>
    <ToastContainer />
  </div>
</template>

<script setup>
import AppSidebar from './components/AppSidebar.vue'
import ToastContainer from './components/ToastContainer.vue'
import { useTheme } from './composables/useTheme'

const { theme, toggleTheme } = useTheme()
</script>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
}

.app-main {
  flex: 1;
  min-width: 0;
  padding: var(--space-xl);
  overflow-y: auto;
}

/* ─── 顶栏 ─── */
.topbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: var(--space-lg);
}

.topbar__theme-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-secondary);
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out),
              color var(--duration-fast) var(--ease-out),
              border-color var(--duration-fast) var(--ease-out),
              transform var(--duration-fast) var(--ease-out);
}
.topbar__theme-btn:hover {
  background: var(--bg-inset);
  color: var(--accent);
  border-color: var(--border-strong);
  transform: rotate(15deg);
}
.topbar__theme-btn:active {
  transform: rotate(15deg) scale(0.92);
}
.topbar__theme-btn:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

@media (max-width: 768px) {
  .app-layout {
    flex-direction: column;
  }
  .app-main {
    padding: var(--space-lg);
    padding-bottom: 72px; /* bottom tab bar space */
  }
}
</style>
