/** 金额显示：后端返回的是 number，统一格式化成两位小数带 ¥ */
export function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `¥${value.toFixed(2)}`
}

/**
 * 时间显示：后端返回的是 UTC，转成本地时间显示成「2026-09-12 14:03」
 *
 * 后端**一律存 UTC**（`BaseModel` 和各个 service 都用 `datetime.now(timezone.utc)`），
 * 序列化出来又不带时区后缀，所以得先补个 Z 再交给 `Date`——不补的话会被当成
 * 本地时间，白白差 8 小时。
 *
 * 这一版之前是把 UTC 当本地直接切的（`iso.slice(0, 16)`），券的到期时间一来就
 * 露馅了：同一张表里「有效期 20:55」和「领券 12:55」其实是两个差 8 小时的口径。
 * 索性按后端的事实统一转一次，全站（含小票）都跟着对了。
 */
export function formatTime(
  iso: string | null | undefined,
  withSeconds = false
): string {
  const local = toLocalInput(iso)
  if (!local) return '—'
  // 审计日志要精确到秒（同一分钟里能连着好几条操作），列表页到分钟就够
  return withSeconds ? local : local.slice(0, 16)
}

/**
 * 日期选择器选的本地时间 → 后端要的 UTC ISO
 *
 * 选择器给的是「选的人在墙上看到的时间」，后端要的是 UTC。不转换的话，
 * 运营设「10 月 1 日 00:00 到期」，券实际会撑到当天早上 8 点才失效。
 */
export function toUtcIso(local: string | null | undefined): string | null {
  if (!local) return null
  const at = new Date(local.replace(' ', 'T'))
  return Number.isNaN(at.getTime()) ? null : at.toISOString()
}

/** toUtcIso 的反向：后端返回的 UTC ISO → 本地时间字符串（带秒，回填选择器用） */
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
