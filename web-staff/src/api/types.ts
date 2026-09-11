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

/** 标准分页信息 */
export interface Pagination {
  page: number
  per_page: number
  total: number
  pages: number
}