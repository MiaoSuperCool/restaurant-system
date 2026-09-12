/**
 * 顾客端的 HTTP 出口
 *
 * 和 web-staff/src/api/request.ts 有几处关键不同，都是因为**环境不一样**：
 *
 * 1. 用 `uni.request`——小程序里没有 XMLHttpRequest/fetch
 * 2. **不带 cookie、不带 CSRF 头**。顾客端走的是公开接口，后端把 CSRF 豁免了
 *    （CSRF 防的是「带着 cookie 的浏览器请求」，顾客端不用 cookie，没有这个风险）
 * 3. H5 走 dev server 代理避开跨域；小程序直连后端，**必须是完整地址**
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
  data?: Record<string, unknown>
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

/**
 * 所有接口模块只用这一个函数发请求
 *
 * 和后端约定：**HTTP 状态码不区分业务结果，看信封里的 success**。
 * 所以这里不判 statusCode，直接看 body.success——后端返回的
 * 400/404 也是带着完整信封的 JSON。
 */
export function request<T = unknown>(options: RequestOptions): Promise<T> {
  return new Promise((resolve, reject) => {
    uni.request({
      url: API_BASE_URL + options.url + buildQuery(options.params),
      method: options.method || 'GET',
      data: options.data,
      header: { 'Content-Type': 'application/json' },
      timeout: 10000,
      success: (res) => {
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
