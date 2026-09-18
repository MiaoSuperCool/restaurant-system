import uni from '@dcloudio/vite-plugin-uni'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [uni()],
  // 部署时的路径前缀：三个前端塞在同一个域名下，各占一段
  // （/ = 内部人员网页端、/customer/ = 这里、/staff/ = 员工端）。
  //
  // **只有生产构建才带前缀**：开发时 `npm run dev:h5` 还是 http://localhost:5174/，
  // 不用为了改一行代码去记一个前缀。Dockerfile 里构建时传 H5_BASE。
  base: process.env.H5_BASE || '/',
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
