/**
 * types.ts —— 接口层的"契约"
 * 字段与 backend/app/models/ 下的 to_dict() 一一对应
 */


/** 用户（对应 user.py；password_hash 属于泄露字段，前端不定义也不使用） */
export interface User {
  id: number
  username: string
  real_name: string
  email: string
  mobile: string
  is_active: boolean
  is_admin: boolean
  created_at: string | null
}

/** 审计日志（对应 audit_log.py） */
export interface AuditLog {
  id: number
  /** 操作人 id；删除用户后置空（外键 SET NULL） */
  user_id: number | null
  user_name: string
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

/** 门店下拉选项（/api/stores/options，表单选归属门店用） */
export interface StoreOption {
  id: number
  code: string
  name: string
  business_status: string
  business_status_label: string
}

/** 标准分页信息 */
export interface Pagination {
  page: number
  per_page: number
  total: number
  pages: number
}