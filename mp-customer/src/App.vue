<script setup lang="ts">
import { onLaunch } from '@dcloudio/uni-app'

onLaunch(() => {
  // 一期顾客不登录（会员是二期），启动时不需要做什么。
  // 留着这个钩子是因为二期要在这里换成「静默登录拿 openid → 换 token」。
})
</script>

<style>
/* 全局样式（App.vue 的 style 不带 scoped，对所有页面生效） */
page {
  background-color: #f5f5f5;
  color: #1f1f1f;
  /* 和 web-staff 一致的字体栈：优先用系统字体，中文在各平台上都好看 */
  font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Helvetica,
    'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
}

/* 小程序里 image 默认有宽高，重置掉免得撑出布局 */
image {
  display: block;
}
</style>
