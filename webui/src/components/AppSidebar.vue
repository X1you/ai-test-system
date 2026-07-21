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

    <!-- 用户信息 + 登出 -->
    <div class="sidebar-footer">
      <div class="user-info">
        <span class="user-avatar">{{ currentUser?.username?.charAt(0).toUpperCase() || 'U' }}</span>
        <span class="user-name">{{ currentUser?.username || '未知用户' }}</span>
      </div>
      <button class="logout-btn" title="登出" @click="handleLogout">
        <svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true">
          <path fill="currentColor" d="M3 3h8a1 1 0 0 1 1 1v3a1 1 0 1 1-2 0V5H4v10h6v-2a1 1 0 1 1 2 0v3a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zm12.7 3.3a1 1 0 0 1 1.4 0l3 3a1 1 0 0 1 0 1.4l-3 3a1 1 0 0 1-1.4-1.4l1.3-1.3H9a1 1 0 1 1 0-2h8l-1.3-1.3a1 1 0 0 1 0-1.4z"/>
        </svg>
      </button>
    </div>
  </aside>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { currentUser, logout } from '../composables/useAuth'

function handleLogout() {
  if (confirm('确定要登出吗？')) {
    logout()
  }
}

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
  background: var(--gradient-sidebar);
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
  filter: drop-shadow(0 2px 4px var(--accent-glow));
}
[data-theme="dark"] .brand-icon {
  filter: drop-shadow(0 0 6px hsl(150 100% 50% / 0.4));
}

.brand-text {
  font-size: var(--text-lg);
  font-weight: 700;
  color: var(--text-primary);
  white-space: nowrap;
  letter-spacing: -0.02em;
}
[data-theme="dark"] .brand-text {
  text-shadow: var(--text-glow);
  letter-spacing: 0;
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
  transition: background var(--duration-normal) var(--ease-out),
              color var(--duration-normal) var(--ease-out),
              transform var(--duration-normal) var(--ease-out);
  min-height: 38px;
  position: relative;
}

.nav-item:hover {
  background: var(--bg-inset);
  color: var(--text-primary);
  text-decoration: none;
  transform: translateX(2px);
}

.nav-item.router-link-exact-active {
  background: var(--accent-subtle);
  color: var(--accent);
  font-weight: 600;
  box-shadow: inset 3px 0 0 var(--accent);
}
[data-theme="dark"] .nav-item.router-link-exact-active {
  box-shadow: inset 3px 0 0 var(--accent), 0 0 8px hsl(150 100% 50% / 0.15);
  text-shadow: var(--text-glow);
}

.nav-icon {
  flex-shrink: 0;
}

/* ─── 用户信息 + 登出 ─── */
.sidebar-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-sm);
  padding: var(--space-md) var(--space-sm);
  margin-top: var(--space-lg);
  border-top: 1px solid var(--border-default);
}

.user-info {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  min-width: 0;
}

.user-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--gradient-accent);
  color: var(--accent-text);
  font-size: 0.8rem;
  font-weight: 700;
  flex-shrink: 0;
  box-shadow: var(--shadow-sm);
}
[data-theme="dark"] .user-avatar {
  background: var(--accent);
  box-shadow: var(--shadow-sm), 0 0 6px hsl(150 100% 50% / 0.3);
}

.user-name {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.logout-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-secondary);
  cursor: pointer;
  transition: background var(--duration-normal) var(--ease-out),
              color var(--duration-normal) var(--ease-out),
              border-color var(--duration-normal) var(--ease-out);
  flex-shrink: 0;
}

.logout-btn:hover {
  background: var(--feedback-error-bg);
  color: var(--status-error);
  border-color: var(--feedback-error-border);
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

  .sidebar-brand,
  .sidebar-footer {
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

  .nav-item:hover {
    transform: none;
  }

  .nav-item.router-link-exact-active {
    box-shadow: none;
  }

  .nav-label {
    font-size: 10px;
  }
}
</style>
