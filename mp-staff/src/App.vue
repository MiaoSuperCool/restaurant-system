<script setup lang="ts">
import { onLaunch } from '@dcloudio/uni-app'

onLaunch(() => {
  // 启动时只做一个判断：**本地有没有 token**。
  //
  // 有就直接进首页，不在这里验它还有没有效——首页那一个请求（`/index`）
  // 会把结果告诉我们：有效就正常渲染，过期了 `request.ts` 会清掉 token 跳登录页。
  // 在这儿再单独发一次校验请求，等于让每次冷启动都多等一个来回。
  const token = uni.getStorageSync('mp_staff_token')
  if (!token) {
    uni.reLaunch({ url: '/pages/login/login' })
  }
})
</script>

<style>
/* 全局样式（App.vue 的 style 不带 scoped，对所有页面生效） */
page {
  background-color: #f5f5f5;
  color: #1f1f1f;
  font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Helvetica,
    'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
}

/* 小程序里 image 默认有宽高，重置掉免得撑出布局 */
image {
  display: block;
}
</style>