import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'landing',
    component: () => import('@/views/LandingView.vue'),
  },
  {
    path: '/workbench',
    name: 'workbench',
    component: () => import('@/views/WorkbenchView.vue'),
  },
  {
    path: '/knowledge',
    name: 'knowledge',
    component: () => import('@/views/KnowledgeView.vue'),
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/views/SettingsView.vue'),
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// P2-4：已登录用户访问 / 自动跳转工作台，避免在管理后台中重复展示营销落地页。
// 使用 sessionStorage 标记（非持久化，关闭标签页即清），不引入 auth store 依赖。
router.beforeEach((to) => {
  if (to.path === '/' && sessionStorage.getItem('app_visited') === '1') {
    return { name: 'workbench' }
  }
  if (to.path === '/workbench') {
    sessionStorage.setItem('app_visited', '1')
  }
})

export default router
