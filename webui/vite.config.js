import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'path'

/**
 * ════════════════════════════════════════════════════════════════
 *  Vite 构建配置 (Version 7 — Bard 吟游诗人 · 冷冽星空)
 * ════════════════════════════════════════════════════════════════
 *  关键策略：
 *    1. tailwindcss 插件置于 vue 之前（Tailwind v4 @tailwindcss/vite）
 *    2. manualChunks 拆分：vue / motion / lucide-icons 各自独立 vendor chunk
 *    3. cssCodeSplit：每个 view 一份 CSS，首屏更小
 *    4. target es2020：现代浏览器（覆盖率 >96%）
 *    5. terser 压缩 + drop_console：生产环境剥离 console
 *    6. 不开 sourcemap：减少 CI 体积，加快发布
 * ════════════════════════════════════════════════════════════════
 */
export default defineConfig({
  plugins: [tailwindcss(), vue()],

  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },

  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
    target: 'es2020',
    cssCodeSplit: true,
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true,
        drop_debugger: true,
        pure_funcs: ['console.info', 'console.debug'],
      },
    },
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-vue':        ['vue', 'vue-router'],
          'vendor-motion':     ['motion'],
          'vendor-icons':      ['lucide-vue-next'],
        },
        chunkFileNames: 'assets/[name]-[hash].js',
        entryFileNames:   'assets/[name]-[hash].js',
        assetFileNames:   'assets/[name]-[hash][extname]',
      },
    },
    chunkSizeWarningLimit: 600,
    reportCompressedSize: false,
  },

  server: {
    port: 5173,
    open: true,
    strictPort: false,

    // 开发模式 API 代理 — 将后端端点转发到 FastAPI (8080)
    // 生产模式由 FastAPI 直接服务 dist/ 静态文件，无需代理
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
      '/auth': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
    },
  },

  preview: {
    port: 4173,
  },
})
