/** 金额显示：后端返回的是 number，统一格式化成两位小数带 ¥ */
export function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `¥${value.toFixed(2)}`
}

/**
 * 时间显示：后端返回 ISO 字符串，这里转成「2026-09-12 14:03」这种给人看的格式
 *
 * 用字符串切而不是 new Date()：后端的 created_at 是 UTC 存储、序列化时
 * 不带时区后缀，用 Date 解析会被当成本地时间，差 8 小时。
 * 等真正需要跨时区显示时再统一处理（那会儿该让后端返回带时区的 ISO）。
 */
export function formatTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  return iso.slice(0, 16).replace('T', ' ')
}
