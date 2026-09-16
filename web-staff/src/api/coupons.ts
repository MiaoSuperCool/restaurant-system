import { request } from './request'
import type { CouponTemplate, Pagination, UserCoupon } from './types'

/** 券模板列表接口返回的 data */
export interface CouponTemplateListData {
  templates: CouponTemplate[]
  pagination: Pagination
}

/** 会员券包接口返回的 data */
export interface MemberCouponListData {
  coupons: UserCoupon[]
  pagination: Pagination
}

/** 券的「这单能用哪些券」接口返回的 data（每张券多一个 discount） */
export interface UsableCouponListData {
  coupons: UserCoupon[]
}

/** 建/改券模板的请求体（对应 CouponTemplateCreateSchema / UpdateSchema） */
export interface CouponTemplatePayload {
  name?: string
  type?: string
  value?: number
  min_amount?: number
  /** UTC ISO；null = 不限（valid_from 为空 = 立即生效） */
  valid_from?: string | null
  valid_to?: string | null
  total_quantity?: number | null
  status?: string
  /** 空数组 = 全公司通用 */
  store_ids?: number[]
}

/** 券模板列表（coupon:manage；搜索券名、按状态筛） */
export function getCouponTemplates(params: {
  search?: string
  status?: string
  page?: number
}) {
  return request<CouponTemplateListData>({ url: '/coupons/templates', method: 'get', params })
}

/** 新建券模板（coupon:manage） */
export function createCouponTemplate(data: CouponTemplatePayload) {
  return request<CouponTemplate>({ url: '/coupons/templates', method: 'post', data })
}

/** 修改券模板（coupon:manage）。**动了模板会影响还没发的券**，已发出去的不受影响 */
export function updateCouponTemplate(id: number, data: CouponTemplatePayload) {
  return request<CouponTemplate>({ url: `/coupons/templates/${id}`, method: 'put', data })
}

/** 删除券模板（coupon:manage）。**发出去过的删不掉**，只能停用 */
export function deleteCouponTemplate(id: number) {
  return request<null>({ url: `/coupons/templates/${id}`, method: 'delete' })
}

/**
 * 给一批会员发券（coupon:issue）
 *
 * 和管模板是**两个权限码**：能设计券的人不一定该能随便发（发出去就是成本）。
 */
export function issueCoupons(data: {
  template_id: number
  member_ids: number[]
  count?: number
  remark?: string
}) {
  return request<{ total: number }>({ url: '/coupons/issue', method: 'post', data })
}

/**
 * 某个会员的券包（member:balance:view 或 coupon:verify）
 *
 * `status` 传 unused / used / expired / not_started——后两个是**算出来的**。
 */
export function getMemberCoupons(
  memberId: number,
  params: { status?: string; page?: number; per_page?: number } = {}
) {
  return request<MemberCouponListData>({
    url: `/coupons/members/${memberId}`,
    method: 'get',
    params,
  })
}

/**
 * 这一单能用哪些券（按能抵多少倒序）
 *
 * 要传门店和金额——「适用门店」和「满多少」两个条件得靠它们判。
 * **用不了的不会出现在结果里**，所以拿到就能直接给收银员看。
 */
export function getUsableCoupons(
  memberId: number,
  params: { store_id: number; amount: number }
) {
  return request<UsableCouponListData>({
    url: `/coupons/members/${memberId}/usable`,
    method: 'get',
    params,
  })
}