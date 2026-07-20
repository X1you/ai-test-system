<template>
  <aside class="sidebar" :class="{ 'sidebar--mobile': isMobile }">
    <!-- Brand -->
    <div class="sidebar-brand">
      <svg class="brand-icon" viewBox="0 0 24 24" width="24" height="24" aria-hidden="true">
        <path fill="currentColor" d="M7 2v2h1v14a4 4 0 0 0 8 0V4h1V2H7zm4 14c-.6 0-1-.4-1-1s.4-1 1-1 1 .4 1 1-.4 1-1 1zm2-4c-.6 0-1-.4-1-1s.4-1 1-1 1 .4 1 1-.4 1-1 1z"/>
      </svg>
      <span class="brand-text">AI 测试系统</span>
    </div>

    <!-- Navigation -->
    <nav class="sidebar-nav" aria-label="主导航">
      <router-link
        v-for="item in navItems"
        :key="item.to"
        :to="item.to"
        class="nav-item"
        :aria-label="item.label"
      >
        <svg class="nav-icon" viewBox="0 0 20 20" width="18" height="18" aria-hidden="true" v-html="item.icon"></svg>
        <span class="nav-label">{{ item.label }}</span>
      </router-link>
    </nav>
  </aside>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const navItems = [
  {
    to: '/',
    label: '仪表盘',
    icon: '<path fill="currentColor" d="M3 3h6v8H3V3zm0 10h6v4H3v-4zm8-10h6v4h-6V3zm0 6h6v8h-6V9z"/>',
  },
  {
    to: '/pipeline/new',
    label: '新建任务',
    icon: '<path fill="currentColor" d="M10 3a1 1 0 0 1 1 1v5h5a1 1 0 1 1 0 2h-5v5a1 1 0 1 1-2 0v-5H4a1 1 0 1 1 0-2h5V4a1 1 0 0 1 1-1z"/>',
  },
  {
    to: '/pipelines',
    label: '任务列表',
    icon: '<path fill="currentColor" d="M3 4h14a1 1 0 0 1 0 2H3a1 1 0 0 1 0-2zm0 5h14a1 1 0 0 1 0 2H3a1 1 0 0 1 0-2zm0 5h14a1 1 0 0 1 0 2H3a1 1 0 0 1 0-2z"/>',
  },
  {
    to: '/knowledge',
    label: '知识库',
    icon: '<path fill="currentColor" d="M4 2a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H4zm2 4h8a1 1 0 0 1 0 2H6a1 1 0 0 1 0-2zm0 4h5a1 1 0 0 1 0 2H6a1 1 0 0 1 0-2z"/>',
  },
  {
    to: '/settings',
    label: '设置',
    icon: '<path fill="currentColor" d="M10 13a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm7.4-3a7.4 7.4 0 0 0-.1-1.2l2-1.5-2-3.5-2.4 1a7.6 7.6 0 0 0-2-1.2L12.5 1h-5l-.4 2.6a7.6 7.6 0 0 0-2 1.2l-2.4-1-2 3.5 2 1.5a7.4 7.4 0 0 0 0 2.4l-2 1.5 2 3.5 2.4-1a7.6 7.6 0 0 0 2 1.2l.4 2.6h5l.4-2.6a7.6 7.6 0 0 0 2-1.2l2.4 1 2-3.5-2-1.5c.06-.4.1-.8.1-1.2z"/>',
  },
]

// Mobile detection (for bottom tab bar)
const isMobile = ref(window.innerWidth < 768)
function onResize() { isMobile.value = window.innerWidth < 768 }
onMounted(() => window.addEventListener('resize', onResize))
onUnmounted(() => window.removeEventListener('resize', onResize))
</script>

<style scoped>
.sidebar {
  width: var(--sidebar-width);
  min-width: var(--sidebar-width);
  height: 100vh;
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-surface);
  border-right: 1px solid var(--border-default);
  padding: var(--space-lg) var(--space-md);
  overflow-y: auto;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-sm);
  margin-bottom: var(--space-xl);
}

.brand-icon {
  color: var(--accent);
  flex-shrink: 0;
}

.brand-text {
  font-size: var(--text-lg);
  font-weight: 700;
  color: var(--text-primary);
  white-space: nowrap;
}

.sidebar-nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: var(--text-base);
  text-decoration: none;
  transition: background var(--duration-fast) var(--ease-out),
              color var(--duration-fast) var(--ease-out);
  min-height: 36px;
}

.nav-item:hover {
  background: var(--bg-inset);
  color: var(--text-primary);
  text-decoration: none;
}

.nav-item.router-link-exact-active {
  background: var(--accent-subtle);
  color: var(--accent);
  font-weight: 500;
}

.nav-icon {
  flex-shrink: 0;
}

/* ─── Mobile: bottom tab bar ─── */
@media (max-width: 768px) {
  .sidebar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    top: auto;
    width: 100%;
    min-width: unset;
    height: auto;
    flex-direction: row;
    align-items: center;
    border-right: none;
    border-top: 1px solid var(--border-default);
    padding: var(--space-xs) var(--space-sm);
    z-index: 100;
  }

  .sidebar-brand {
    display: none;
  }

  .sidebar-nav {
    flex-direction: row;
    justify-content: space-around;
    gap: 0;
  }

  .nav-item {
    flex-direction: column;
    gap: 2px;
    padding: var(--space-xs);
    font-size: var(--text-xs);
    min-height: 44px;
    min-width: 44px;
    justify-content: center;
  }

  .nav-label {
    font-size: 10px;
  }
}
</style>
