import { createRouter, createWebHistory } from 'vue-router'
import { isAuthenticated } from '../composables/useAuth'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/Login.vue'),
    meta: { title: '登录', public: true },
  },
  {
    path: '/',
    name: 'dashboard',
    component: () => import('../views/Dashboard.vue'),
    meta: { title: '仪表盘' },
  },
  {
    path: '/pipeline/new',
    name: 'pipeline-new',
    component: () => import('../views/PipelineNew.vue'),
    meta: { title: '新建任务' },
  },
  {
    path: '/pipelines',
    name: 'pipeline-list',
    component: () => import('../views/PipelineList.vue'),
    meta: { title: '任务列表' },
  },
  {
    path: '/pipeline/:id',
    name: 'pipeline-detail',
    component: () => import('../views/PipelineDetail.vue'),
    meta: { title: '任务详情' },
  },
  {
    path: '/knowledge',
    name: 'knowledge',
    component: () => import('../views/Knowledge.vue'),
    meta: { title: '知识库' },
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('../views/Settings.vue'),
    meta: { title: '设置' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// ─── 路由守卫：未登录用户重定向到登录页 ───
router.beforeEach((to) => {
  // 公开路由（如登录页）不需要认证
  if (to.meta.public) {
    // 已登录用户访问登录页 → 重定向到首页
    if (to.name === 'login' && isAuthenticated.value) {
      return { name: 'dashboard' }
    }
    return true
  }

  // 受保护路由：未登录 → 重定向到登录页并携带 redirect
  if (!isAuthenticated.value) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  return true
})

router.afterEach((to) => {
  document.title = to.meta.title
    ? `${to.meta.title} — AI 测试系统`
    : 'AI 测试用例生成系统'
})

export default router
