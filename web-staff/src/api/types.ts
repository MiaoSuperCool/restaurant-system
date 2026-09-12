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
  is_paid: boolean
  operator_id: number | null
  /** 实际操作人（公用账号代点单时是选中的那个人，不是账号本身） */
  operator_name: string
  remark: string
  created_at: string | null
  /** 只有详情接口带 */
  items?: OrderItem[]
  payments?: Payment[]
}

/** 标准分页信息 */
export interface Pagination {
  page: number
  per_page: number
  total: number
  pages: number
}