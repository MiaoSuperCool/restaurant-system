import { request } from './request'

/** 班次：店里约定俗成的那几个（早班 09:30-14:00） */
export interface Shift {
  id: number
  store_id: number
  name: string
  start_time: string
  end_time: string
  /** 「09:30-14:00」，列表和下拉里都用它，不用自己拼 */
  time_range: string
  is_active: boolean
  sort_order: number
}

/** 一条排班记录（格子里的一个班） */
export interface Assignment {
  id: number
  store_id: number
  staff_id: number
  staff_name: string
  shift_id: number
  shift_name: string
  shift_time_range: string
  work_date: string
  remark: string
}

/** 一周里的一天 */
export interface ScheduleDay {
  date: string
  weekday: string
  is_today: boolean
}

/** 班表里的一行 = 一个人 + 他那 7 个格子 */
export interface ScheduleRow {
  staff_id: number
  staff_name: string
  employment_type: string
  employment_type_label: string
  /** **和 `days` 按下标一一对应**：`assignments[2]` 就是周三那个格子 */
  assignments: Assignment[][]
}

export interface ScheduleWeek {
  store_id: number
  start: string
  end: string
  days: ScheduleDay[]
  /** **只有启用中的班次**——停用的排不了新班，下拉里不该出现 */
  shifts: Shift[]
  rows: ScheduleRow[]
}

/** 门店下拉里的一项（只有排班用得到的那几个字段） */
export interface ScheduleStore {
  id: number
  code: string
  name: string
}

/**
 * 我能在哪些门店排班（数据范围内）
 *
 * **不是 `/api/stores/options`**：那个要 `store:view`，服务员没有——
 * 他只有 `schedule:view`（得知道自己哪天上班），走那个接口会报「没有权限」
 */
export function getScheduleStores() {
  return request<{ stores: ScheduleStore[] }>({
    url: '/schedule/stores',
    method: 'get',
  })
}

export interface ShiftPayload {
  name: string
  start_time: string
  end_time: string
  sort_order?: number
}

/** 某家店这一周的班表。`day` 传这一周里的任意一天都行（会自动折到周一） */
export function getScheduleWeek(storeId: number, day?: string) {
  return request<ScheduleWeek>({
    url: `/schedule/stores/${storeId}/week`,
    method: 'get',
    params: day ? { day } : undefined,
  })
}

/** 这家店的班次（含停用的）——配置面板用 */
export function getShifts(storeId: number) {
  return request<{ shifts: Shift[] }>({
    url: `/schedule/stores/${storeId}/shifts`,
    method: 'get',
  })
}

export function createShift(storeId: number, data: ShiftPayload) {
  return request<Shift>({
    url: `/schedule/stores/${storeId}/shifts`,
    method: 'post',
    data,
  })
}

export function updateShift(shiftId: number, data: Partial<ShiftPayload> & { is_active?: boolean }) {
  return request<Shift>({ url: `/schedule/shifts/${shiftId}`, method: 'put', data })
}

export function deleteShift(shiftId: number) {
  return request<null>({ url: `/schedule/shifts/${shiftId}`, method: 'delete' })
}

/**
 * 排一个人一天的班
 *
 * `shiftIds` 是**这一天的完整答案**（不是增量）：这天要上的班全传上来，
 * 空数组 = 休息。后端按 id 对齐，多的删、少的加。
 */
export function setScheduleDay(storeId: number, data: {
  staff_id: number
  work_date: string
  shift_ids: number[]
}) {
  return request<{ assignments: Assignment[] }>({
    url: `/schedule/stores/${storeId}/assignments`,
    method: 'put',
    data,
  })
}