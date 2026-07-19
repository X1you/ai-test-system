import { createRouter, createWebHistory } from 'vue-router'

const routes = [
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

router.afterEach((to) => {
  document.title = to.meta.title
    ? `${to.meta.title} — AI 测试系统`
    : 'AI 测试用例生成系统'
})

export default router
