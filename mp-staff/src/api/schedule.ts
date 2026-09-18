import { request } from './request'
import type { MySchedule } from './types'

/**
 * 我接下来哪天上班
 *
 * **和网页端的排班页是两个接口**：网页端那个 `stores/<id>/week` 拿的是
 * 「这一周谁上什么班」（店长排班用的格子），这里拿的是「我哪天要来、几点来」。
 * 同一个后台，两种看法。
 *
 * `store_id` 不用传：后端查的是 token 里这个人自己的班
 * （本来就不该有「看别人的班表」这个入口）。
 */
export function getMySchedule(params: { days?: number } = {}) {
  return request<MySchedule>({
    url: '/api/schedule/me',
    method: 'GET',
    params: { days: params.days },
  })
}