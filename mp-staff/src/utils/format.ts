/** 金额显示：后端返回的是 number，统一格式化成两位小数带 ¥ */
export function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `¥${value.toFixed(2)}`
}

/**
 * 时间显示：后端返回的是 UTC，转成本地时间
 *
 * 和 `web-staff/src/utils/format.ts` 里那份**同一套做法**（那边有一段更长的说明）：
 * 库里存的是 UTC、序列化出来不带时区后缀，所以要手工补个 `Z` 再交给 `Date`，
 * 不然会被当成本地时间、白白差 8 小时。
 *
 * 小程序里 `Date` 的解析各家实现略有出入，所以这里**不用 Date 构造函数解析字符串**，
 * 而是按 ISO 的固定格式切开自己算——字符串格式是后端 `isoformat()` 定死的，
 * 比依赖各端的 `Date` 行为可靠。
 */
export function formatTime(iso: string | null | undefined, withSeconds = false): string {
  if (!iso) return '—'
  // 形如 2026-09-17T09:07:04 或 2026-09-17T09:07:04.123456
  const [datePart, timePart = '00:00:00'] = iso.replace('Z', '').split('T')
  const [y, m, d] = datePart.split('-').map(Number)
  const [hh, mm, ss] = timePart.split(':')
  // 先当成 UTC 算一个时间戳，再取出本地字段——这一步才是真正的转换
  const utcMs = Date.UTC(y, m - 1, d, Number(hh), Number(mm), Number(ss.slice(0, 2)))
  const at = new Date(utcMs)
  const pad = (n: number) => String(n).padStart(2, '0')
  const base =
    `${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())} ` +
    `${pad(at.getHours())}:${pad(at.getMinutes())}`
  return withSeconds ? `${base}:${pad(at.getSeconds())}` : base
}

/** 「3 分钟前」这种相对时间——出单页上「这单等了多久」比绝对时间更有用 */
export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return ''
  const [datePart, timePart = '00:00:00'] = iso.replace('Z', '').split('T')
  const [y, m, d] = datePart.split('-').map(Number)
  const [hh, mm, ss] = timePart.split(':')
  const created = Date.UTC(y, m - 1, d, Number(hh), Number(mm), Number(ss.slice(0, 2)))
  const minutes = Math.floor((Date.now() - created) / 60000)
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时前`
  return formatTime(iso)
}