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

/**
 * 日期选择器选的本地时间 → 后端要的 UTC ISO
 *
 * 后端的 `valid_from` / `valid_to` 存的是 UTC，而日期选择器给的是「选的人在墙上
 * 看到的时间」。不转换的话，运营设「10 月 1 日 00:00 到期」，券实际会撑到当天
 * 早上 8 点才失效（UTC 和北京时间差 8 小时）。
 *
 * 注意这**和 formatTime() 不是一套做法**：那个是直接把 UTC 当本地显示（见它自己的
 * 注释，是已知的将就）。券的有效期是「顾客几点就不能用了」这种业务上要准的值，
 * 所以这里认真转一次。
 */
export function toUtcIso(local: string | null | undefined): string | null {
  if (!local) return null
  const at = new Date(local.replace(' ', 'T'))
  return Number.isNaN(at.getTime()) ? null : at.toISOString()
}

/** toUtcIso 的反向：后端返回的 UTC ISO → 日期选择器要的本地时间 */
export function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return ''
  // 后端序列化出来不带时区后缀，补个 Z 再交给 Date——不补的话会被当成本地时间
  const at = new Date(iso.endsWith('Z') ? iso : `${iso}Z`)
  if (Number.isNaN(at.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return (
    `${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())} ` +
    `${pad(at.getHours())}:${pad(at.getMinutes())}:${pad(at.getSeconds())}`
  )
}

/** 券有效期这类「时间点」的显示：UTC → 本地，精确到分钟 */
export function formatLocalTime(iso: string | null | undefined): string {
  const local = toLocalInput(iso)
  return local ? local.slice(0, 16) : '—'
}
