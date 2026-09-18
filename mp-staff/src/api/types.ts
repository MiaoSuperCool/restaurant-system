/** 员工端用到的数据结构（字段名和后端 to_dict 一一对应） */

/** 登录返回的当前员工 */
export interface Staff {
  id: number
  username: string
  real_name: string
  mobile: string
  store_id: number | null
  store_name: string | null
  employment_type: string
  employment_type_label: string
  /** 公用账号：服务员共用一台设备登录，下单时得另外记实际操作人 */
  is_shared: boolean
  is_active: boolean
  is_admin: boolean
  roles: { id: number; code: string; name: string }[]
  created_at: string | null
}

/** POST /api/auth/token 返回的 data */
export interface LoginResult {
  token: string
  /** 秒数 */
  expires_in: number
  staff: Staff
  permissions: string[]
  /** store 本店 / all 全部 */
  data_scope: string
}

/** 门店菜单里的一道菜（对应 store_dish_service 的合并结果） */
export interface StoreMenuRow {
  dish_id: number
  name: string
  description: string
  image: string
  category_id: number
  category_name: string | null
  /** 本店实际价格（基础价和门店覆盖价合并之后） */
  price: number
  base_price: number
  is_available: boolean
  option_groups: DishOptionGroup[]
}

export interface DishOptionGroup {
  id?: number
  name: string
  selection_type: 'single' | 'multiple'
  is_required: boolean
  options: DishOption[]
}

export interface DishOption {
  id: number
  name: string
  extra_price: number
}

/** 订单里的一行明细 */
export interface OrderItem {
  id: number
  dish_id: number
  dish_name: string
  unit_price: number
  quantity: number
  subtotal: number
  options: { id: number; name: string; quantity: number; extra_price: number }[]
}

/** 订单（列表和详情共用，详情多了 items/payments） */
export interface Order {
  id: number
  order_no: string
  store_id: number
  store_name: string
  source: string
  source_label: string
  status: string
  status_label: string
  total_amount: number
  discount_amount: number
  points_discount: number
  payable_amount: number
  paid_amount: number
  refunded_amount: number
  remark: string
  member_id: number | null
  operator_name: string
  created_at: string | null
  is_paid: boolean
  items?: OrderItem[]
  payments?: { id: number; method: string; method_label: string; amount: number }[]
}

/** 团购券核销结果 */
export interface GrouponVoucher {
  id: number
  code: string
  platform: string
  platform_label: string
  amount: number
  order_id: number | null
  verified_by_name: string
  verified_at: string | null
}

/** 分页信封 */
export interface Pagination {
  page: number
  per_page: number
  total: number
  pages: number
}
/** 门店下拉选项（对应 /api/stores/options 返回的一项） */
export interface StoreOption {
  id: number
  code: string
  name: string
  business_status: string
  business_status_label: string
}

/** 经营报表：汇总 */
export interface ReportSummary {
  revenue: number
  order_count: number
  /** 客单价 = 营业额 ÷ 单量；单量为 0 时后端给 0，不是 NaN */
  avg_order_amount: number
  refund_amount: number
  cancelled_count: number
}

/** 经营报表：按天的一格。**没有单的日子也有一行** */
export interface ReportTrendRow {
  date: string
  revenue: number
  order_count: number
}

/** 经营报表：按门店的一格。店长只会看到自己一家 */
export interface ReportStoreRow {
  store_id: number
  store_name: string
  revenue: number
  order_count: number
}

/** 经营报表：支付方式构成的一格。只看成功的流水 */
export interface ReportMethodRow {
  method: string
  method_label: string
  count: number
  amount: number
}

/** 经营报表：菜品排行的一格（按份数，前 10） */
export interface ReportDishRow {
  dish_id: number
  dish_name: string
  quantity: number
  amount: number
}

/** 经营报表：时段分布的一格（本地时间的小时）。只返回有单的小时 */
export interface ReportHourRow {
  hour: number
  order_count: number
  revenue: number
}

/**
 * 经营概览
 *
 * **和电脑上那个报表页是同一份数据**——网页端有的这几块，手机上一样有。
 * 一开始只声明了 `summary/trend/by_store`（当时的判断是「手机上放不下，
 * 那些电脑上看」），后来发现那个判断不对：老板在饭桌上掏出手机，
 * 想知道的就是「今天微信收了多少」「哪道菜卖得好」。
 */
export interface ReportOverview {
  range: { start: string; end: string; days: number }
  summary: ReportSummary
  trend: ReportTrendRow[]
  by_hour: ReportHourRow[]
  by_store: ReportStoreRow[]
  by_method: ReportMethodRow[]
  top_dishes: ReportDishRow[]
}
