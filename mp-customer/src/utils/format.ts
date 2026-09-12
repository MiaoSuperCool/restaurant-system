/** 金额显示：后端返回的是 number，统一格式化成两位小数带 ¥ */
export function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `¥${value.toFixed(2)}`
}

/**
 * 时间显示
 *
 * 后端返回的 ISO 字符串是 UTC 存储、不带时区后缀，用 `new Date()` 解析会被
 * 当成本地时间，差 8 小时。这里直接切字符串（和 web-staff 同一处理）。
 */
export function formatTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  return iso.slice(0, 16).replace('T', ' ')
}
