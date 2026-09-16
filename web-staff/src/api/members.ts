import { request } from './request'
import type { BalanceTxn, Member, MemberBalance, Pagination } from './types'

/** 会员列表接口返回的 data */
export interface MemberListData {
  members: Member[]
  pagination: Pagination
}

/** 余额流水接口返回的 data */
export interface BalanceTxnListData {
  txns: BalanceTxn[]
  pagination: Pagination
}

/**
 * 会员列表（按手机号或昵称搜）
 *
 * 收银台那一幕：顾客报手机号 → 搜出人 → 看余额 → 决定能不能抵这单。
 */
export function getMembers(params: { search?: string; page?: number }) {
  return request<MemberListData>({ url: '/members', method: 'get', params })
}

/** 会员详情（带储值余额；没有「查看储值余额」权限时 balance 是 null） */
export function getMember(id: number) {
  return request<Member>({ url: `/members/${id}`, method: 'get' })
}

/** 余额流水（倒序） */
export function getBalanceTxns(id: number, params: { page?: number } = {}) {
  return request<BalanceTxnListData>({
    url: `/members/${id}/balance/txns`,
    method: 'get',
    params,
  })
}

/** 建档（员工代客办卡）。手机号和微信 openid 至少填一个 */
export function createMember(data: { mobile?: string; nickname?: string }) {
  return request<Member>({ url: '/members', method: 'post', data })
}

/**
 * 储值充值——**支持充送结合**
 *
 * `principal` 是顾客真掏的钱（能退），`bonus` 是送的（不退）。
 * 两个数分开传，后端会记成两条流水：本金是收入、赠送是营销成本。
 */
export function rechargeBalance(
  id: number,
  data: { principal: number; bonus?: number; remark?: string }
) {
  return request<MemberBalance>({
    url: `/members/${id}/balance/recharge`,
    method: 'post',
    data,
  })
}