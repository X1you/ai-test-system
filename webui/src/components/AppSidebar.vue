<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Zap, BookOpen, Settings, Sun, Moon } from 'lucide-vue-next'
import { useTheme } from '@/composables/useTheme'
import { usePipelineStore } from '@/stores/pipeline'
import { useToastStore } from '@/composables/useToast'

const route = useRoute()
const router = useRouter()
const { currentTheme, toggleTheme } = useTheme()
const pipelineStore = usePipelineStore()
const toast = useToastStore()

// 移动端抽屉开关（由 App.vue 控制）
defineProps<{ mobileOpen?: boolean }>()
const emit = defineEmits<{ close: [] }>()

const activeActionCount = computed(
  () => pipelineStore.tasksByStatus.action.length
)

// lucide 图标组件映射（替换原 emoji，符合标杆图标体系）
// 「待处理队列」入口已移除：与工作台默认 Tab 视图完全冗余，
// 且 ?filter=action 参数从未被 TaskList 消费（死链）。
// 待处理计数通过「测试工作台」项的 badge 体现。
const navItems = [
  { path: '/workbench', label: '测试工作台', icon: Zap, group: 'core', badge: true },
  { path: '/knowledge', label: '知识库 (RAG)', icon: BookOpen, group: 'secondary' },
  { path: '/settings', label: '偏好设置', icon: Settings, group: 'secondary' },
]

function isActive(item: typeof navItems[0]): boolean {
  return route.path === item.path
}

function navigate(path: string) {
  if (path.includes('?')) {
    const [p, q] = path.split('?')
    const params = new URLSearchParams(q)
    router.push({ path: p, query: Object.fromEntries(params) })
  } else {
    router.push(path)
  }
  // 移动端导航后关闭抽屉
  emit('close')
}
</script>

<template>
  <aside class="sidebar" :class="{ 'mobile-open': mobileOpen }">
    <!-- 品牌区 -->
    <a href="#" class="brand-mark" @click.prevent="navigate('/')">
      <div class="brand-logo" :style="{ width: '28px', height: '28px' }">
        <svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
          <mask id="sidebarLogoMask">
            <rect width="100" height="100" fill="white" />
            <path d="M 22 50 L 37 65 L 59 40" stroke="black" stroke-width="7" stroke-linecap="square" stroke-linejoin="miter" fill="none" />
            <circle cx="59" cy="40" r="8" fill="black" />
          </mask>
          <path d="M 25 12 H 58 C 74 12 85 22 85 36 C 85 46 73 50 62 50 C 76 50 88 56 88 72 C 88 84 74 88 58 88 H 25 Z" fill="currentColor" mask="url(#sidebarLogoMask)" />
        </svg>
      </div>
      <span class="brand-name">Bard</span>
    </a>

    <!-- 导航分组 -->
    <div class="side-section">
      <div class="side-section-label">核心工作区</div>
      <a
        v-for="item in navItems.filter(i => i.group === 'core')"
        :key="item.path"
        href="#"
        class="side-link"
        :class="{ active: isActive(item) }"
        :aria-current="isActive(item) ? 'page' : undefined"
        @click.prevent="navigate(item.path)"
      >
        <component :is="item.icon" class="side-icon" aria-hidden="true" :size="18" />
        <span>{{ item.label }}</span>
        <span v-if="item.badge && activeActionCount > 0" class="badge-num">{{ activeActionCount }}</span>
      </a>
    </div>

    <div class="side-section">
      <div class="side-section-label">其他</div>
      <a
        v-for="item in navItems.filter(i => i.group === 'secondary')"
        :key="item.path"
        href="#"
        class="side-link"
        :class="{ active: isActive(item) }"
        :aria-current="isActive(item) ? 'page' : undefined"
        @click.prevent="navigate(item.path)"
      >
        <component :is="item.icon" class="side-icon" aria-hidden="true" :size="18" />
        <span>{{ item.label }}</span>
      </a>
    </div>

    <!-- 底部 -->
    <div class="side-footer">
      <button
        class="theme-toggle"
        :aria-label="currentTheme === 'dark' ? '切换到亮色主题' : '切换到暗色主题'"
        @click="toggleTheme"
      >
        <Sun v-if="currentTheme === 'dark'" aria-hidden="true" :size="18" />
        <Moon v-else aria-hidden="true" :size="18" />
      </button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: var(--sidebar-width);
  flex-shrink: 0;
  background: var(--muted);
  border-right: 1px solid var(--border);
  padding: 1.25rem 0.85rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  height: 100vh;
  overflow-y: auto;
  position: sticky;
  top: 0;
}

.brand-mark {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.2rem 0.25rem;
  color: var(--fg);
}
.brand-logo {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.brand-logo svg {
  width: 100%;
  height: 100%;
}
.brand-name {
  font-weight: var(--weight-black);
  font-size: var(--text-xl);
  letter-spacing: -0.04em;
  line-height: var(--leading-tight);
}

.side-section {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
.side-section-label {
  font-size: var(--text-xs);
  text-transform: uppercase;
  letter-spacing: 0.15em;
  color: var(--muted-fg);
  padding: 0.25rem 0.5rem;
  font-weight: var(--weight-bold);
  font-family: var(--font-mono);
}
.side-link {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.6rem 0.75rem;
  font-size: var(--text-sm);
  font-weight: var(--weight-semibold);
  color: var(--muted-fg);
  border: 1px solid transparent;
  /* 最小点击区域 44px（WCAG 2.5.8） */
  min-height: 44px;
  transition: all var(--duration-fast) var(--ease);
}
.side-link:hover {
  color: var(--fg);
  background: var(--hover-bg);
  border-color: var(--border-light);
}
.side-link.active {
  color: var(--bg);
  background: var(--fg);
  border-color: var(--fg);
  font-weight: var(--weight-bold);
}
.side-icon {
  flex-shrink: 0;
}
.badge-num {
  margin-left: auto;
  font-size: var(--text-xs);
  font-family: var(--font-mono);
  padding: 0.1rem 0.4rem;
  background: var(--panel-bg);
  color: var(--fg);
  border: 1px solid var(--border);
  font-weight: var(--weight-bold);
}
.side-link.active .badge-num {
  background: var(--bg);
  color: var(--fg);
  border-color: var(--bg);
}

.side-footer {
  margin-top: auto;
  border-top: 1px solid var(--border);
  padding-top: 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
}
.theme-toggle {
  /* 44×44px 触摸标准（WCAG 2.5.8） */
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border);
  background: var(--panel-bg);
  color: var(--fg);
  transition: all var(--duration-fast);
}
.theme-toggle:hover {
  border-color: var(--fg);
}

/* 移动端：< 768px 侧边栏变固定抽屉，默认隐藏 */
@media (max-width: 767px) {
  .sidebar {
    position: fixed;
    top: 0;
    left: 0;
    z-index: 55;
    transform: translateX(-100%);
    transition: transform 0.25s var(--ease);
    box-shadow: 2px 0 12px rgba(0, 0, 0, 0.1);
  }
  .sidebar.mobile-open {
    transform: translateX(0);
  }
}

/* reduced-motion 降级：抽屉滑动瞬时 */
@media (prefers-reduced-motion: reduce) {
  .sidebar {
    transition: none;
  }
}
</style>
