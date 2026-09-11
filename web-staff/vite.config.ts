import { fileURLToPath, URL } from 'node:url'
 // 从 Node.js 内置的 url 模块引入两个工具函数，后面算"src 文件夹的绝对路径"要用
import { defineConfig } from 'vitest/config'
// 引入 Vite 的 defineConfig 辅助函数（vitest/config 是超集，额外支持下方 test 配置的类型提示）
import vue from '@vitejs/plugin-vue'
// 引入 Vue 插件。这是 Vite 和 Vue 之间的"翻译官"：没有它，Vite 不知道 .vue 文件是什么、怎么编译


export default defineConfig({
  //把配置对象导出给 Vite
  plugins: [vue()], //注册 Vue 插件
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  test: {
    // vitest 配置（npm run test 时生效，不影响 dev/build）
    environment: 'jsdom', // 模拟浏览器环境：localStorage / document 等
    include: ['tests/**/*.spec.ts'] // 测试文件放在 web-staff/tests/（不进 src，避免被 vue-tsc 类型检查）
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true
      },
      '/index': {
        target: 'http://localhost:5000',
        changeOrigin: true
      }
    }
  },
  build: {
    rollupOptions: {
      output: {
        // 把大体积依赖单独拆包，避免 index chunk 超 500kB
        manualChunks: {
          'element-plus': ['element-plus'],
          vue: ['vue', 'vue-router', 'pinia']
        }
      }
    }
  }
})