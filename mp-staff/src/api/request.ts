/**
 * 员工端的 HTTP 出口
 *
 * 和 web-staff 那份（`web-staff/src/api/request.ts`）是同一个后端的两个客户端，
 * 差别都来自**环境不一样**：
 *
 * 1. 用 `uni.request`——小程序里没有 XMLHttpRequest/fetch
 * 2. **认证靠 `Authorization: Bearer <token>`，没有 cookie、没有 CSRF**
 *    （后端的 CSRF 只管浏览器那条路，见 `backend/app/extensions.py` 的
 *    `ApiCSRFProtect`；小程序这边没有「浏览器自动带 cookie」这个前提）
 * 3. H5 走 dev server 代理避开跨域；小程序直连后端，**必须是完整地址**
 * 4. 401 不能「跳登录页」了事——要清掉本地 token 再跳，否则会拿一个废 token 反复撞墙
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
// H5 开发时走 vite 代理（见 vite.config.ts），用相对路径就不会跨域
baseUrl = ''
// #endif

export const API_BASE_URL = baseUrl

/** token 存在本地存储里的 key */
export const TOKEN_KEY = 'mp_staff_token'

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
  /**
   * 请求体
   *
   * 用 `object` 而不是 `Record<string, unknown>`：**interface 没有隐式索引签名**，
   * 各个 api 模块里用 `interface XxxPayload` 定义的请求体会赋不进来
   * （TypeScript 的一个经典坑，type 别名就没这个问题）
   */
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

function getToken(): string {
  return uni.getStorageSync(TOKEN_KEY) || ''
}

/** 清掉 token 并回登录页。**只有一处**——散在各地迟早漏一个 */
function toLogin() {
  uni.removeStorageSync(TOKEN_KEY)
  // 已经在登录页就别再跳，否则会叠一堆页面
  const pages = getCurrentPages()
  const current = pages[pages.length - 1]
  if (current && current.route && current.route.includes('login')) return
  uni.reLaunch({ url: '/pages/login/login' })
}

/**
 * 所有接口模块只用这一个函数发请求
 *
 * 和后端约定：**HTTP 状态码不区分业务结果，看信封里的 success**。
 * 所以这里不判 statusCode，直接看 body.success——后端返回的 400/401/404
 * 也都是带着完整信封的 JSON。
 *
 * 例外是 401：那时信封里可能是「请先登录」，也可能是 token 过期。
 * 两种情况处理一样——**token 没用了，回登录页**。
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
        // 没登录时不带这个头，后端认不出来就返回 401，走到下面那个分支
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      timeout: 10000,
      success: (res) => {
        if (res.statusCode === 401) {
          toLogin()
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