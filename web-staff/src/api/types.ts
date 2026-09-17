/**
 * types.ts —— 接口层的"契约"
 * 字段与 backend/app/models/ 下的 to_dict() 一一对应
 */


/** 权限（对应 permission.py） */
export interface Permission {
  id: number
  /** 权限码，统一为「资源:动作」，如 order:refund */
  code: string
  name: string
  /** 按域分组，只影响展示 */
  group: string
  sort_order: number
}

/** 角色（对应 role.py）。权限和数据范围都挂在角色上 */
export interface Role {
  id: number
  code: string
  name: string
  description: string
  data_scope: string
  data_scope_label: string
  /** 预置角色：由后端 rbac.py 定义，界面上不能改 */
  is_builtin: boolean
  sort_order: number
  permission_codes: string[]
}

/** 员工身上带的角色（staff.to_dict() 里的精简形态） */
export interface StaffRoleBrief {
  id: number
  code: string
  name: string
}

/** 员工账号（对应 staff.py；password_hash 属于泄露字段，前端不定义也不使用） */
export interface Staff {
  id: number
  username: string
  real_name: string
  email: string
  mobile: string
  /** 归属门店；总部账号（运营主管/财务/老板）为 null */
  store_id: number | null
  store_name: string | null
  employment_type: string
  employment_type_label: string
  /** 公用账号：服务员共用设备登录，下单时要额外记录实际操作人 */
  is_shared: boolean
  is_active: boolean
  /** 超级管理员：绕过权限码检查（日常授权走角色） */
  is_admin: boolean
  /** 角色列表；权限和数据范围都由角色决定 */
  roles: StaffRoleBrief[]
  created_at: string | null
}

/** 审计日志（对应 audit_log.py） */
export interface AuditLog {
  id: number
  /** 操作人员工 id；删除员工后置空（外键 SET NULL） */
  operator_id: number | null
  operator_name: string
  action: string
  resource: string | null
  datetime: string | null
  status: string
  old_value: Record<string, unknown> | null
  new_value: Record<string, unknown> | null
}

/** 门店（对应 store.py） */
export interface Store {
  id: number
  /** 门店编码：老系统映射、ERP 对接、对账都靠它认店 */
  code: string
  name: string
  store_type: string
  /** 中文名由后端给（枚举常量定义在 store.py，前端不重复维护一份） */
  store_type_label: string
  address: string
  phone: string
  business_status: string
  business_status_label: string
  run_mode: string
  run_mode_label: string
  remark: string
  created_at: string | null
  updated_at: string | null
}

/** 门店菜品覆盖记录（对应 store_dish.py，设置接口的返回值） */
export interface StoreDish {
  id: number
  store_id: number
  dish_id: number
  /** 本店覆盖价；null 表示用菜品基础价 */
  price: number | null
  is_available: boolean
  daily_limit: number | null
  has_price_override: boolean
}

/** 门店下拉选项（/api/stores/options，表单选归属门店用） */
export interface StoreOption {
  id: number
  code: string
  name: string
  business_status: string
  business_status_label: string
}

/** 菜品分类（对应 category.py） */
export interface Category {
  id: number
  name: string
  /** 图标：emoji 或图片地址 */
  icon: string
  is_visible: boolean
  sort_order: number
  store_ids: number[]
  store_names: string[]
  /** 没指定门店 = 全公司通用 */
  is_all_stores: boolean
  created_at: string | null
  updated_at: string | null
}

/** 分类下拉选项（/api/categories/options） */
export interface CategoryOption {
  id: number
  name: string
  icon: string
}

/** 规格选项（大份 / 微辣 / 加蛋） */
export interface DishOption {
  id: number
  name: string
  /** 附加价；0 是有意义的取值（微辣和特辣同价） */
  extra_price: number
  sort_order: number
}

/** 规格组（份量 / 辣度 / 加料） */
export interface DishOptionGroup {
  id: number
  name: string
  selection_type: string
  selection_type_label: string
  /** 必选：单选组必选 = 必须选一个；多选组必选 = 至少要选一个 */
  is_required: boolean
  sort_order: number
  options: DishOption[]
}

/** 菜品（对应 dish.py） */
export interface Dish {
  id: number
  category_id: number
  category_name: string | null
  name: string
  image: string
  description: string
  base_price: number
  status: string
  status_label: string
  sort_order: number
  created_at: string | null
  updated_at: string | null
  /** 只有详情接口带（列表太重不带） */
  option_groups?: DishOptionGroup[]
}

/**
 * 门店菜单里的一行：菜品基础 + 本店覆盖合并后的结果
 *
 * 对应后端 store_dish_service._merge()。注意 price 是本店实际售价、
 * base_price 是公司基础价——两个都给你，是为了让界面能显示「改过的价格」。
 */
export interface StoreMenuRow {
  dish_id: number
  name: string
  image: string
  description: string
  category_id: number
  category_name: string | null
  /** 公司基础价 */
  base_price: number
  /** 本店实际售价（有覆盖用覆盖价，没有就用基础价） */
  price: number
  has_price_override: boolean
  is_available: boolean
  daily_limit: number | null
  /** 这家店有没有对这道菜做过特殊设置 */
  has_override: boolean
  /** 规格组：点单界面用它渲染规格选择器 */
  option_groups: DishOptionGroup[]
}

/** 订单明细里选中的规格（对应 order_item_option） */
export interface OrderItemOption {
  id: number
  /** 保留的引用，供「加蛋卖了多少份」这类统计 */
  dish_option_id: number
  group_name: string
  name: string
  extra_price: number
}

/** 订单明细的一行（对应 order_item） */
export interface OrderItem {
  id: number
  dish_id: number
  /** 下单那一刻的快照：菜品改名后历史订单还是老名字 */
  dish_name: string
  unit_price: number
  quantity: number
  subtotal: number
  /** 规格文本快照，如「大份,特辣,加蛋」 */
  options_text: string
  options: OrderItemOption[]
}

/**
 * 团购券核销记录（对应 groupon_voucher.py）
 *
 * 和 Payment 的区别：核销记录管「这张券用掉了」（券码唯一、按平台对账），
 * 收款记录管「这一笔记了多少钱」。核销会同时产生两者。
 */
export interface GrouponVoucher {
  id: number
  /** 券码：全局唯一，同一张券不能核销两次 */
  code: string
  platform: string
  platform_label: string
  amount: number
  order_id: number
  order_no: string | null
  payment_id: number | null
  verified_by_name: string
  verified_at: string | null
}

/** 支付记录（对应 payment.py） */
export interface Payment {
  id: number
  order_id: number
  method: string
  method_label: string
  status: string
  status_label: string
  amount: number
  /** 我们自己的支付流水号，挂在订单号后面（xxx-P01） */
  payment_no: string
  /** 第三方流水号（微信支付单号等）；现金为空。对账靠它 */
  transaction_no: string
  operator_id: number | null
  operator_name: string
  paid_at: string | null
  created_at: string | null
}

/** 退款流水：钱真的退出去那一刻的记录（对应 refund_txn 表） */
export interface RefundTxn {
  id: number
  refund_id: number
  order_id: number
  amount: number
  method: string
  method_label: string
  /** 第三方退款单号（微信退款单号）；现金为空 */
  transaction_no: string
  operator_name: string
  settled_at: string | null
}

/**
 * 退款申请单（对应 refund 表）
 *
 * 注意它和 RefundTxn 的区别：申请单是**流程**（谁申请、谁批、批没批），
 * 流水是**钱**（真的退出去那一刻）。**批了不等于钱退了。**
 */
export interface Refund {
  id: number
  refund_no: string
  order_id: number
  order_no: string | null
  amount: number
  reason: string
  type: string
  type_label: string
  status: string
  status_label: string
  applicant_name: string
  approver_name: string
  approve_remark: string
  approved_at: string | null
  created_at: string | null
  /** 只有详情/列表接口带 */
  txns?: RefundTxn[]
}

/** 订单（对应 order.py） */
export interface Order {
  id: number
  order_no: string
  store_id: number
  store_name: string | null
  member_id: number | null
  source: string
  source_label: string
  status: string
  status_label: string
  total_amount: number
  discount_amount: number
  payable_amount: number
  /** 已收金额；可能分多笔累加 */
  paid_amount: number
  /** 已退金额 */
  refunded_amount: number
  /** 还能退多少 = 已收 − 已退 */
  refundable_amount: number
  is_paid: boolean
  operator_id: number | null
  /** 实际操作人（公用账号代点单时是选中的那个人，不是账号本身） */
  operator_name: string
  remark: string
  created_at: string | null
  /** 只有详情接口带 */
  items?: OrderItem[]
  payments?: Payment[]
  refunds?: Refund[]
}

/** 标准分页信息 */
export interface Pagination {
  page: number
  per_page: number
  total: number
  pages: number
}

/** 储值账户（对应 balance.py 的 Balance.to_dict） */
export interface MemberBalance {
  member_id: number
  /** 本金：顾客真掏的钱，**能退** */
  principal: number
  /** 赠送：充值送的，**不退**；扣款时它先花掉 */
  bonus: number
  /** 账上还能花多少 = 本金 + 赠送 */
  total: number
}

/** 积分账户（对应 points.py 的 Points.to_dict） */
export interface MemberPoints {
  member_id: number
  /** 积分余额（整数，不是钱）。**不拆本金/赠送**——积分全是送的 */
  balance: number
  /** 这些分能抵多少钱——后端用同一套换算算好的，前端别自己乘除 */
  amount?: number
}

/** 会员（对应 member.py 的 Member.to_dict） */
export interface Member {
  id: number
  /** 可能为空——微信登录不一定拿得到手机号 */
  mobile: string | null
  nickname: string
  avatar: string
  is_active: boolean
  created_at: string | null
  /** 只有详情接口带；没有「查看储值余额」权限时是 null（不是 0，是「看不到」） */
  balance?: MemberBalance | null
  /** 同上——没权限时是 null */
  points?: MemberPoints | null
}

/** 积分流水（对应 points.py 的 PointsTxn.to_dict） */
export interface PointsTxn {
  id: number
  member_id: number
  type: string
  type_label: string
  /** 变动（正负号有意义） */
  delta: number
  /** 变动后的积分——对账的锚点 */
  after: number
  order_id: number | null
  legacy_no: string
  remark: string
  created_at: string | null
}

/** 余额流水（对应 balance.py 的 BalanceTxn.to_dict） */
export interface BalanceTxn {
  id: number
  member_id: number
  type: string
  type_label: string
  /** 这笔变动的总额，正负号有意义 */
  amount: number
  principal_delta: number
  bonus_delta: number
  /** 变动后的余额快照——对账时的锚点 */
  principal_after: number
  bonus_after: number
  /** 消费/退回时挂着订单；充值没有 */
  order_id: number | null
  /** 老系统单号（迁移过来的流水才有） */
  legacy_no: string
  remark: string
  created_at: string | null
}

/** 券模板（对应 coupon.py 的 CouponTemplate.to_dict）——券的「规则」 */
export interface CouponTemplate {
  id: number
  name: string
  /** full_cut 满减 / discount 折扣 */
  type: string
  type_label: string
  /** 满减是「减多少钱」；折扣是**折扣率**（0.85 = 八五折），不是减多少 */
  value: number
  /** 门槛：满多少才能用；0 = 无门槛 */
  min_amount: number
  valid_from: string | null
  valid_to: string | null
  /** 发放总量；null = 不限量。只约束「发」，不约束「用」 */
  total_quantity: number | null
  status: string
  status_label: string
  store_ids: number[]
  store_names: string[]
  /** 没指定门店 = 全公司通用 */
  is_all_stores: boolean
  issued_count: number
  created_at: string | null
}

/**
 * 用户持券（对应 coupon.py 的 UserCoupon.to_dict）——某个会员手里的一张券
 *
 * **`status` 有四个值，库里只存两个**：未使用 / 已使用是存进去的，
 * 已过期 / 未生效是每次现算的（见 models/coupon.py 开头）。别拿它当库里的状态用。
 */
export interface UserCoupon {
  id: number
  template_id: number
  template_name: string
  template_type: string
  template_type_label: string
  value: number
  min_amount: number
  member_id: number
  /** unused / used / expired / not_started */
  status: string
  status_label: string
  valid_to: string | null
  received_at: string | null
  /** 谁发的；「演示数据」是种子数据发的，顾客自己领的为空 */
  issued_by_name: string
  used_at: string | null
  used_store_id: number | null
  /** 只有「这单能用哪些券」那个接口带：这张券实际能抵多少 */
  discount?: number
}

/** 老系统 ID ↔ 新系统 ID（对应 legacy.py 的 LegacyMap.to_dict） */
export interface LegacyMap {
  id: number
  /** member 会员 / balance 储值账户 */
  target_type: string
  target_type_label: string
  target_id: number
  /** 老系统那边的号，是字符串——老系统可能是自增数字，也可能是 'M0010086' */
  legacy_id: string
  remark: string
  created_at: string | null
}

/** 一次同步动作的记录（对应 legacy.py 的 SyncRecord.to_dict） */
export interface SyncRecord {
  id: number
  /** push 推出去 / pull 拉进来 */
  direction: string
  direction_label: string
  target: string
  target_label: string
  category: string
  category_label: string
  /** success / failed / pending */
  status: string
  status_label: string
  /** 这条同步的是哪一条数据（单号/会员号/日报） */
  ref: string
  /** 失败原因原样留着，不翻译 */
  message: string
  synced_at: string | null
}

/** 同步汇总（不跟着列表的筛选走，永远是全量） */
export interface SyncSummary {
  success: number
  failed: number
  pending: number
  total: number
}

/** 对账里的一条差异——会员那条带 member_*，订单那条带 order_* */
export interface ReconciliationDetail {
  member_id?: number
  member_name?: string
  order_id?: number
  order_no?: string
  expected: number
  actual: number
  diff: number
}

/**
 * 对账记录（对应 legacy.py 的 Reconciliation.to_dict）
 *
 * **`diff_amount` 和 `mismatch_count` 要分开看**：一个会员多 100、一个少 100，
 * 差异合计是 0，但这两处都是错的。状态由 `mismatch_count` 决定，
 * 不能只看金额
 */
export interface Reconciliation {
  id: number
  /** 业务日期（本地自然日），不是 UTC 日期 */
  biz_date: string | null
  store_id: number | null
  /** 储值对账不挂门店，这里会是「全公司」 */
  store_name: string
  /** order 订单 / balance 储值 */
  category: string
  category_label: string
  expected_amount: number
  actual_amount: number
  diff_amount: number
  /** matched 对得上 / mismatched 有差异 */
  status: string
  status_label: string
  mismatch_count: number
  detail: ReconciliationDetail[]
  checked_at: string | null
}