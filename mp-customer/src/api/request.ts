/**
 * 顾客端的 HTTP 出口
 *
 * 和 web-staff/src/api/request.ts 有几处关键不同，都是因为**环境不一样**：
 *
 * 1. 用 `uni.request`——小程序里没有 XMLHttpRequest/fetch
 * 2. **不带 cookie、不带 CSRF 头**。顾客端走的是自己那条 token 通道，
 *    后端把那组蓝图整个豁免了 CSRF（CSRF 防的是「带着 cookie 的浏览器请求」，
 *    顾客端不用 cookie，没有这个风险）
 * 3. H5 走 dev server 代理避开跨域；小程序直连后端，**必须是完整地址**
 * 4. **401 不跳登录页**——这一端大部分接口（菜单、下单）根本不需要登录，
 *    一 401 就跳转会把正常浏览的人打断。清掉本地 token 就完事，
 *    要不要引导去登录由页面自己决定
 */

// 后端地址。
//
// 【小程序端】没有「同源」这个概念，必须写完整地址：
//   - 在微信开发者工具里调试：localhost 就行（工具跑在你这台机器上）
//   - **真机预览要改成电脑的内网 IP**（比如 http://192.168.1.5:5000）——
//     手机上的 localhost 指向手机自己，连不到你的电脑。
//     同时要在开发者工具里勾上「不校验合法域名」（详情 → 本地设置）
let baseUrl = 'http://localhost:5000'

// #ifdef H5
// H5 开发时走 vite 代理（见 vite.config.ts），用相对路径就不会跨域。
// H5 上线如果前后端不同域，这里要改成后端地址，并让后端放行那个来源。
baseUrl = ''
// #endif

export const API_BASE_URL = baseUrl

/** 顾客 token 在本地存储里的 key */
export const TOKEN_KEY = 'mp_customer_token'

/** 后端统一响应信封 */
interface ApiResponse<T> {
  success: boolean
  message: string
  data: T
  timestamp: string
}

interface RequestOptions {
  url: string
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  /** 请求体。用 `object` 不用 `Record<string, unknown>`——interface 没有隐式索引签名 */
  data?: object
  /** 查询参数（拼在 URL 后面） */
  params?: Record<string, string | number | undefined>
}

function buildQuery(params?: RequestOptions['params']): string {
  if (!params) return ''
  const parts = Object.entries(params)
    .filter(([, value]) => value !== undefined && value !== '')
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
  return parts.length ? `?${parts.join('&')}` : ''
}

export function getToken(): string {
  return uni.getStorageSync(TOKEN_KEY) || ''
}

/**
 * 所有接口模块只用这一个函数发请求
 *
 * 和后端约定：**HTTP 状态码不区分业务结果，看信封里的 success**。
 * 所以这里不判 statusCode，直接看 body.success——后端返回的
 * 400/404 也是带着完整信封的 JSON。
 *
 * 401 是唯一例外：它意味着手里那个 token 不作数了（过期、被停用、
 * 或者压根没有）。这时候**把本地的清掉**，然后照常走下面那套报错流程——
 * 页面自己决定是引导登录还是就当散客继续用。
 */
export function request<T = unknown>(options: RequestOptions): Promise<T> {
  return new Promise((resolve, reject) => {
    const token = getToken()
    uni.request({
      url: API_BASE_URL + options.url + buildQuery(options.params),
      method: options.method || 'GET',
      data: options.data,
      header: {
        'Content-Type': 'application/json',
        // 没登录时不带这个头。后端认不出来就返回 401，走到下面那个分支
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      timeout: 10000,
      success: (res) => {
        if (res.statusCode === 401) {
          uni.removeStorageSync(TOKEN_KEY)
          reject(new Error('登录已过期'))
          return
        }

        const body = res.data as ApiResponse<T>
        if (body && body.success) {
          resolve(body.data)
          return
        }
        const message = (body && body.message) || `请求失败（${res.statusCode}）`
        uni.showToast({ title: message, icon: 'none', duration: 2500 })
        reject(new Error(message))
      },
      fail: () => {
        uni.showToast({ title: '网络错误，请检查后端是否启动', icon: 'none', duration: 2500 })
        reject(new Error('网络错误'))
      },
    })
  })
}