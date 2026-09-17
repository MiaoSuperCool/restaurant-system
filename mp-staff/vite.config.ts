import uni from '@dcloudio/vite-plugin-uni'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [uni()],
  server: {
    // 5173 = 内部人员网页端、5174 = 顾客小程序，这里接着错开
    port: 5175,
    proxy: {
      // H5 开发时走代理，避开跨域：后端的 CORS 只放行了 5173，
      // 所以 H5 版必须走代理。小程序端不走这里——它没有同源概念，
      // 直接请求完整地址，见 src/api/request.ts
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      // 首页那个接口挂在 /index 上，**不在 /api 下面**（项目早期的约定，
      // 网页端的 vite 配置里也单独转发了这一条）。漏了它 H5 版进首页就是 404
      '/index': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
    },
  },
})