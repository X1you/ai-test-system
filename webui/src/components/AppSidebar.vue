<template>
  <aside class="app-sidebar" :class="{ 'app-sidebar--collapsed': isCollapsed }">
    <!-- Logo Section -->
    <div class="app-sidebar__logo">
      <BardIcon
        :size="isCollapsed ? 32 : 36"
        variant="brand"
        :animated="true"
        label="Bard — AI Test System"
        class="app-sidebar__logo-icon"
      />
      <span class="app-sidebar__logo-text">AI Test System</span>
    </div>

    <!-- 折叠/展开按钮（方案 4.2：64px ↔ 220px） -->
    <button
      class="app-sidebar__collapse-btn"
      :aria-label="isCollapsed ? '展开侧边栏' : '收起侧边栏'"
      :aria-expanded="!isCollapsed"
      :title="isCollapsed ? '展开侧边栏' : '收起侧边栏'"
      @click="toggleCollapse"
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
        <!-- 折叠态显示右箭头（点击展开）；展开态显示左箭头（点击收起） -->
        <path v-if="isCollapsed" d="M9 6l6 6-6 6"/>
        <path v-else d="M15 6l-6 6 6 6"/>
      </svg>
    </button>

    <!-- Navigation — 5 项（方案 4.2：仪表盘 / 任务列表 / 新建任务 / 知识库 / 设置） -->
    <nav class="sidebar__nav" aria-label="主导航">
      <router-link
        to="/"
        class="sidebar__nav-item"
        :class="{ 'sidebar__nav-item--active': currentRoute === '/' }"
        :title="'仪表盘'"
      >
        <svg class="sidebar__nav-item__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/>
        </svg>
        <span class="sidebar__nav-item__label">仪表盘</span>
      </router-link>

      <router-link
        to="/pipelines"
        class="sidebar__nav-item"
        :class="{ 'sidebar__nav-item--active': currentRoute.startsWith('/pipelines') }"
        :title="'任务列表'"
      >
        <svg class="sidebar__nav-item__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path d="M4 6h16M4 12h16M4 18h16"/>
        </svg>
        <span class="sidebar__nav-item__label">任务列表</span>
      </router-link>

      <router-link
        to="/pipeline/new"
        class="sidebar__nav-item"
        :class="{ 'sidebar__nav-item--active': currentRoute === '/pipeline/new' }"
        :title="'新建任务'"
      >
        <svg class="sidebar__nav-item__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path d="M12 5v14M5 12h14"/>
        </svg>
        <span class="sidebar__nav-item__label">新建任务</span>
      </router-link>

      <router-link
        to="/knowledge"
        class="sidebar__nav-item"
        :class="{ 'sidebar__nav-item--active': currentRoute.startsWith('/knowledge') }"
        :title="'知识库'"
      >
        <svg class="sidebar__nav-item__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
        </svg>
        <span class="sidebar__nav-item__label">知识库</span>
      </router-link>

      <router-link
        to="/settings"
        class="sidebar__nav-item"
        :class="{ 'sidebar__nav-item--active': currentRoute === '/settings' }"
        :title="'设置'"
      >
        <svg class="sidebar__nav-item__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/>
          <path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
        </svg>
        <span class="sidebar__nav-item__label">设置</span>
      </router-link>
    </nav>

    <!-- Bottom: Theme Toggle -->
    <div class="sidebar__bottom">
      <button
        class="sidebar__theme-btn"
        @click="toggleTheme"
        :aria-label="`切换外观（当前：${theme === 'dark' ? '暗色' : '亮色'}）`"
        :title="theme === 'dark' ? '切换到亮色模式' : '切换到暗色模式'"
      >
        <!-- 暗色下显示太阳（点击切到亮色） -->
        <svg v-if="theme === 'dark'" class="sidebar__theme-btn__icon" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
          <circle cx="10" cy="10" r="4"/>
          <path d="M10 2v2m0 12v2M2 10h2m12 0h2M4.93 4.93l1.41 1.41m8.48 8.48l1.41 1.41M4.93 15.07l1.41-1.41m8.48-8.48l1.41-1.41"/>
        </svg>
        <!-- 亮色下显示月亮（点击切到暗色） -->
        <svg v-else class="sidebar__theme-btn__icon" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
          <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z"/>
        </svg>
        <span class="sidebar__theme-btn__label">{{ theme === 'dark' ? '亮色模式' : '暗色模式' }}</span>
      </button>
    </div>
  </aside>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useTheme } from '../composables/useTheme'
import BardIcon from './BardIcon.vue'

const route = useRoute()
const { theme, toggleTheme } = useTheme()

const currentRoute = computed(() => route.path)

// ─── 折叠态（方案 4.2：默认 64px 仅图标，可展开至 220px） ───
// 用 CSS class（app-sidebar--collapsed）控制 label 显隐，而非 v-show，
// 原因：v-show 的 inline style display:none 会被移动端 media query 的 display 规则覆盖失败，
// 改用 class + media query 可保证移动端 label 始终可见。
const SIDEBAR_WIDTH_COLLAPSED = '64px'
const SIDEBAR_WIDTH_EXPANDED = '220px'

const isCollapsed = ref(true)  // 默认折叠，符合方案 4.2「64px thin sidebar with icons only」

// 同步实际宽度到 documentElement，供 App.vue 的 app-main 计算左 padding
// （修复内容被 position:fixed 侧边栏遮挡的布局 bug）
function syncSidebarWidth() {
  document.documentElement.style.setProperty(
    '--sidebar-actual-w',
    isCollapsed.value ? SIDEBAR_WIDTH_COLLAPSED : SIDEBAR_WIDTH_EXPANDED
  )
}

function toggleCollapse() {
  isCollapsed.value = !isCollapsed.value
}

onMounted(syncSidebarWidth)
watch(isCollapsed, syncSidebarWidth)
</script>

<style scoped>
/* ═══ 桌面端：固定侧边栏，默认 64px 折叠，可展开至 220px（方案 4.2） ═══ */
.app-sidebar {
  width: var(--sidebar-actual-w, 64px);
  background: var(--bg-surface);
  border-right: 1px solid var(--border-default);
  display: flex;
  flex-direction: column;
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  z-index: 100;
  overflow-x: hidden;
  overflow-y: auto;
  transition: width var(--duration-normal) var(--ease-out),
              background-color var(--duration-normal) var(--ease-out);
}

/* 滚动条样式 */
.app-sidebar::-webkit-scrollbar {
  width: 6px;
}
.app-sidebar::-webkit-scrollbar-track {
  background: transparent;
}
.app-sidebar::-webkit-scrollbar-thumb {
  background: var(--border-default);
  border-radius: var(--radius-full);
}

/* ─── Logo 区域 ─── */
.app-sidebar__logo {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-lg) var(--space-md);
  margin-bottom: var(--space-lg);
  justify-content: center;  /* 折叠态居中图标 */
}

.app-sidebar__logo-icon {
  color: var(--accent);
  border-radius: var(--radius-md);
  padding: 2px;
  flex-shrink: 0;
  transition: color var(--duration-normal) var(--ease-out),
              transform var(--duration-slow) var(--ease-out);
}

.app-sidebar__logo:hover .app-sidebar__logo-icon {
  transform: scale(1.05);
}

.app-sidebar__logo-text {
  color: var(--text-primary);
  font-size: var(--text-lg);
  font-weight: 600;
  letter-spacing: -0.015em;
  white-space: nowrap;
  transition: color var(--duration-normal) var(--ease-out);
}

/* ─── 折叠/展开按钮 ─── */
.app-sidebar__collapse-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  margin: 0 auto var(--space-md);
  padding: 0;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-secondary);
  cursor: pointer;
  flex-shrink: 0;
  transition: background-color var(--duration-normal) var(--ease-out),
              color var(--duration-normal) var(--ease-out),
              border-color var(--duration-normal) var(--ease-out);
}

.app-sidebar__collapse-btn:hover {
  background: var(--bg-inset);
  color: var(--accent);
  border-color: var(--accent);
}

.app-sidebar__collapse-btn svg {
  width: 16px;
  height: 16px;
}

.app-sidebar__collapse-btn:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

/* ─── 导航区域 ─── */
.sidebar__nav {
  flex: 1;
  padding: var(--space-md) 0;
}

.sidebar__nav-item {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-md);
  margin: var(--space-xs) var(--space-sm);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  text-decoration: none;
  font-size: var(--text-base);
  font-weight: 400;
  transition: color var(--duration-normal) var(--ease-out),
              background-color var(--duration-normal) var(--ease-out),
              filter var(--duration-normal) var(--ease-out);
  position: relative;
  overflow: hidden;
  justify-content: center;  /* 折叠态居中图标 */
}

/* 折叠态：固定 40×40 方块，仅图标 */
.app-sidebar--collapsed .sidebar__nav-item {
  width: 40px;
  height: 40px;
  margin-left: auto;
  margin-right: auto;
  padding: 0;
}

.sidebar__nav-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 0;
  background: var(--accent);
  transition: width var(--duration-normal) var(--ease-out);
  z-index: 0;
}

.sidebar__nav-item > * {
  position: relative;
  z-index: 1;
}

.sidebar__nav-item:hover {
  color: var(--accent);
  background: var(--bg-inset);
  /* 方案 4.2：导航项 hover 时冷金色光晕（drop-shadow 不影响布局） */
  filter: drop-shadow(0 0 8px var(--accent-glow));
}

.sidebar__nav-item:hover::before {
  width: 3px;
}

.sidebar__nav-item--active {
  background: var(--bg-inset);
  color: var(--accent);
  font-weight: 500;
}

.sidebar__nav-item--active::before {
  width: 3px;
}

.sidebar__nav-item__icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.sidebar__nav-item__label {
  white-space: nowrap;
}

/* 折叠态：隐藏所有 label（logo-text / nav-label / theme-btn-label） */
.app-sidebar--collapsed .app-sidebar__logo-text,
.app-sidebar--collapsed .sidebar__nav-item__label,
.app-sidebar--collapsed .sidebar__theme-btn__label {
  display: none;
}

/* ─── 侧边栏底部外观切换 ─── */
.sidebar__bottom {
  padding: var(--space-md);
  border-top: 1px solid var(--border-default);
}

.sidebar__theme-btn {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  width: 100%;
  padding: var(--space-md);
  background: transparent;
  border: none;
  color: var(--text-secondary);
  font-size: var(--text-base);
  font-family: inherit;
  cursor: pointer;
  border-radius: var(--radius-md);
  transition: background-color var(--duration-normal) var(--ease-out),
              color var(--duration-normal) var(--ease-out);
  text-align: left;
  justify-content: center;  /* 折叠态居中图标 */
}

.sidebar__theme-btn:hover {
  background: var(--bg-inset);
  color: var(--accent);
}

.sidebar__theme-btn__icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.sidebar__theme-btn__label {
  white-space: nowrap;
}

.sidebar__theme-btn:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

/* ─── 无障碍：减少动画偏好下取消光晕与宽度过渡（方案 6.4） ─── */
@media (prefers-reduced-motion: reduce) {
  .app-sidebar,
  .sidebar__nav-item,
  .app-sidebar__collapse-btn,
  .sidebar__theme-btn {
    transition: none;
  }

  .sidebar__nav-item:hover {
    filter: none;
  }
}

/* ─── 移动端：底部 tab bar（不参与桌面端折叠逻辑，label 强制可见） ─── */
@media (max-width: 768px) {
  .app-sidebar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    width: 100%;
    height: 72px;
    flex-direction: row;
    padding: var(--space-md) 0;
    border-right: none;
    border-top: 1px solid var(--border-default);
    background: var(--bg-surface);
    z-index: 999;
    overflow: visible;
  }

  /* 移动端隐藏 logo 区与折叠按钮，只保留底部 nav */
  .app-sidebar__logo,
  .app-sidebar__collapse-btn,
  .sidebar__bottom {
    display: none;
  }

  .sidebar__nav {
    display: flex;
    flex-direction: row;
    justify-content: space-around;
    padding: 0;
  }

  .sidebar__nav-item {
    flex-direction: column;
    padding: var(--space-sm);
    margin: 0;
    gap: var(--space-xs);
    font-size: var(--text-xs);
    width: auto;
    height: auto;
    justify-content: center;
  }

  /* 移动端强制显示 label（覆盖折叠态的 display:none） */
  .app-sidebar--collapsed .sidebar__nav-item__label {
    display: inline;
  }

  .sidebar__nav-item__icon {
    width: 24px;
    height: 24px;
  }

  /* 移动端不显示 hover 光晕（触摸设备无 hover 语义） */
  .sidebar__nav-item:hover {
    filter: none;
  }
}
</style>
