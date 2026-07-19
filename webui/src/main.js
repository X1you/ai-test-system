import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('./views/Home.vue'),
    },
    {
      path: '/knowledge',
      name: 'knowledge',
      component: () => import('./views/KnowledgeConfig.vue'),
    },
    {
      path: '/pipelines',
      name: 'pipelines',
      component: () => import('./views/PipelineList.vue'),
    },
  ],
})

const app = createApp(App)
app.use(router)
app.mount('#app')
