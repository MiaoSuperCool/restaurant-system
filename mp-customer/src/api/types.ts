/**
 * 接口层的类型定义
 *
 * 字段照着后端 `to_dict()` 写——和 web-staff/src/api/types.ts 是同源的东西，
 * 但这里只保留顾客端用得上的那部分。后端改了字段，两边都要跟着改。
 */

/** 门店（顾客选店用，字段比内部端精简） */
export interface StoreBrief {
  id: number
  code: string
  name: string
  address: string
  phone: string
  store_type: string
  store_type_label: string
  /** 给顾客看的一句话介绍 */
  description: string
  /** 营业时间，如 09:00-22:00 */
  business_hours: string
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
  /** single 单选 / multiple 多选 */
  selection_type: string
  selection_type_label: string
  /** 必选：单选组必选 = 必须选一个；多选组必选 = 至少要选一个 */
  is_required: boolean
  sort_order: number
  options: DishOption[]
}

/** 菜单里的一行（菜品基础 + 本店覆盖合并后的结果） */
export interface MenuRow {
  dish_id: number
  name: string
  image: string
  description: string
  category_id: number
  category_name: string | null
  /** 公司基础价 */
  base_price: number
  /** 本店实际售价 */
  price: number
  has_price_override: boolean
  is_available: boolean
  option_groups: DishOptionGroup[]
}

/** 订单明细里选中的规格 */
export interface OrderItemOption {
  id: number
  dish_option_id: number
  group_name: string
  name: string
  extra_price: number
}

/** 订单明细 */
export interface OrderItem {
  id: number
  dish_id: number
  dish_name: string
  unit_price: number
  quantity: number
  subtotal: number
  options_text: string
  options: OrderItemOption[]
}

/** 支付记录 */
export interface Payment {
  id: number
  method: string
  method_label: string
  status: string
  status_label: string
  amount: number
  payment_no: string
  transaction_no: string
  paid_at: string | null
}

/** 订单 */
export interface Order {
  id: number
  order_no: string
  /** 查订单详情要带上的凭据——光有单号查不到（单号是可读可猜的） */
  query_token: string
  store_id: number
  store_name: string | null
  source: string
  source_label: string
  status: string
  status_label: string
  total_amount: number
  payable_amount: number
  paid_amount: number
  refunded_amount: number
  /** 还能退多少 = 已收 − 已退。顾客端用它判断「能不能自己取消」 */
  refundable_amount: number
  is_paid: boolean
  remark: string
  created_at: string | null
  /** 只有详情接口带 */
  items?: OrderItem[]
  payments?: Payment[]
}

/** 会员（对应 member.py 的 Member.to_dict） */
export interface Member {
  id: number
  mobile: string | null
  nickname: string
  avatar: string
  is_active: boolean
  created_at: string | null
}

/**
 * 我手里的一张券（对应 coupon.py 的 UserCoupon.to_dict）
 *
 * **`status` 有四个值，库里只存两个**：未使用 / 已使用是存进去的，
 * 已过期 / 未生效是每次现算的（见 models/coupon.py 开头）
 */
export interface MemberCoupon {
  id: number
  template_id: number
  template_name: string
  template_type: string
  template_type_label: string
  value: number
  min_amount: number
  status: string
  status_label: string
  valid_to: string | null
  received_at: string | null
  used_at: string | null
}

/**
 * 券中心里的一张券（券模板 + 「我领了几张」）
 *
 * `can_claim` / `blocked_reason` 是后端算好的——**领不了的券也列出来**，
 * 并说清楚为什么。
 */
export interface ClaimableCoupon {
  id: number
  name: string
  type: string
  type_label: string
  value: number
  min_amount: number
  valid_from: string | null
  valid_to: string | null
  total_quantity: number | null
  is_all_stores: boolean
  store_names: string[]
  issued_count: number
  claimed_count: number
  can_claim: boolean
  blocked_reason: string | null
}

/** 分页信封 */
export interface Pagination {
  page: number
  per_page: number
  total: number
  pages: number
}

/**
 * 结算时「这一单能用的一张券」
 *
 * 就是券包里的那张（`MemberCoupon`）**加上后端算好的能抵多少**。
 * 为什么 discount 要后端给：门槛、折扣率、封顶这几条规则都在后面算的，
 * 前端自己再算一遍迟早会和它漂移。
 */
export interface UsableCoupon extends MemberCoupon {
  /** 这一单能抵多少钱（后端算好的） */
  discount: number
}
