import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // 业务 API 代理到后端（FastAPI 挂载在 /api/v1/*）
      '/api': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
      // 健康检查端点代理：后端 /health/* 挂载在根路径（非 /api/v1），
      // 供 k8s liveness/readiness 探针使用；前端"测试连接"需经此代理访问。
      '/health': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
