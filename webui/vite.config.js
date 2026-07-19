import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // 开发期：所有 /api 请求代理到后端
      '/api': {
        target: 'http://127.0.0.1:8090',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:8090',
        changeOrigin: true,
      },
    },
  },
  build: {
    // 构建产物输出到后端静态目录，供 SPA fallback 使用
    outDir: '../web/static/dist',
    emptyOutDir: true,
  },
})
