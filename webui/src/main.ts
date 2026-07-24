import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { useTheme } from './composables/useTheme'
import './styles/globals.css'
import './styles/buttons.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)

// 初始化主题
useTheme().initTheme()

app.mount('#app')
