/**
 * request.ts —— 全前端唯一的 HTTP 出口
 *
 * 职责（对应后端的特点）：
 * 1. baseURL 用相对路径 /api，开发时由 Vite 代理转发给 Flask
 * 2. withCredentials：让浏览器携带 session cookie（Flask-Login 靠它识别登录）
 * 3. X-Requested-With：让 Flask-Login 未登录时返回 401 而不是 302 跳转
 * 4. CSRF：所有 POST/PUT/DELETE 自动带上 X-CSRFToken 头（后端 CSRF 保护是全局开启的）
 * 5. 统一拆开 {success, message, data, timestamp} 信封，只把 data 交给调用方
 * 6. 统一处理错误：401 跳登录页，其他错误弹出后端返回的 message
 */
import axios, { AxiosError, AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'

/** 后端统一响应信封的类型定义 */
export interface ApiResponse<T = unknown> {
  success: boolean
  message: string
  data: T
  timestamp: string
}

/** axios 实例：所有请求的公共配置 */
const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api', // 优先读 .env，没有就用 /api
  timeout: 10000, // 10 秒超时
  withCredentials: true, // 跨域/同源都携带 cookie
})

// 让 Flask-Login 对未登录的 API 请求返回 401（而不是 302 跳转）
// 没有这个头，未登录时后端会 302 到登录接口，而登录接口只收 POST，会变成 405
service.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest'

/* ================= CSRF 处理 ================= */

/** 从 cookie 里读取 csrf_token */
function getCsrfFromCookie(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/)
  return match ? decodeURIComponent(match[1]) : null
}

let csrfPromise: Promise<string | null> | null = null

/**
 * 确保拿到 csrf_token。
 * 后端在每次响应的 after_request 里设置 csrf_token cookie，
 * 但如果"第一个请求"就是登录 POST，cookie 还不存在，会被 CSRF 拦截。
 * 所以 cookie 缺失时，先向后端发一个 GET 预热，把 cookie 领回来。
 */
function ensureCsrfToken(): Promise<string | null> {
  const token = getCsrfFromCookie()
  if (token) return Promise.resolve(token)

  if (!csrfPromise) {
    // 用原生 axios 发预热请求，绕开本文件的拦截器，避免触发 401 跳转逻辑
    csrfPromise = axios
      .get('/index', {
        withCredentials: true,
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      })
      .catch(() => undefined) // 未登录返回 401 是正常的，只要 cookie 拿到就行
      .then(() => getCsrfFromCookie())
      .finally(() => {
        csrfPromise = null
      })
  }
  return csrfPromise
}

/* ================= 请求拦截器 ================= */

service.interceptors.request.use(async (config) => {
  const method = (config.method || 'get').toLowerCase()
  // 只有写请求需要 CSRF 头（GET 不需要）
  if (!['get', 'head', 'options'].includes(method)) {
    const token = await ensureCsrfToken()
    if (token) {
      config.headers.set('X-CSRFToken', token)
    }
  }
  return config
})

/* ================= 响应拦截器 ================= */

function redirectToLogin() {
  // 已经在登录页就不重复跳
  if (window.location.pathname !== '/login') {
    window.location.href = '/login'
  }
}

service.interceptors.response.use(
  // 2xx 直接放行，由下面的 request() 拆信封
  (response) => response,
  // 非 2xx 统一在这里处理
  (error: AxiosError<ApiResponse>) => {
    const status = error.response?.status
    const fullUrl = (error.config?.baseURL || '') + (error.config?.url || '')
    const serverMessage = error.response?.data?.message

    if (status === 401 && fullUrl !== '/api/auth') {
      // 登录过期/未登录 → 回登录页
      // 排除登录接口本身：登录时 401 是"密码错误"，不能跳转
      ElMessage.warning('登录已过期，请重新登录')
      redirectToLogin()
    } else if (status) {
      // 后端返回的业务错误（422 校验失败、403 无权限、401 密码错误……）
      ElMessage.error(serverMessage || `请求失败（${status}）`)
    } else {
      // 没有 response = 网络层错误（后端没启动、代理挂了等）
      ElMessage.error('网络错误，请确认后端服务已启动')
    }

    return Promise.reject(new Error(serverMessage || '请求失败'))
  }
)

/* ================= 类型化的请求函数 ================= */

/**
 * 所有接口模块只用这一个函数发请求。
 * 它把 axios 的响应拆开：{success, message, data, timestamp} → 直接返回 data
 * 用法：request<Book[]>({ url: '/books', method: 'get' })
 */
export function request<T = unknown>(config: AxiosRequestConfig): Promise<T> {
  return service.request<ApiResponse<T>>(config).then((res) => {
    const body = res.data
    if (!body.success) {
      return Promise.reject(new Error(body.message || '请求失败'))
    }
    return body.data
  })
}

export default service