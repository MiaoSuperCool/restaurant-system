import uni from '@dcloudio/vite-plugin-uni'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [uni()],
  server: {
    // 5173 被 web-staff 占着，这里错开
    port: 5174,
    proxy: {
      // H5 开发时走代理，避免跨域（后端的 CORS 只放行了 5173）。
      // 小程序端不走这个代理——它没有同源概念，直接请求完整地址，
      // 见 src/api/request.ts
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
    },
  },
})
