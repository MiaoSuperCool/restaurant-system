# mp-customer —— 顾客小程序端

顾客扫码进店点单用的。技术栈是 **uni-app（Vue3 + Vite + TypeScript）**——
一套代码同时编译到微信小程序和 H5。

## 功能

```
选门店 → 浏览菜单 → 选规格 → 购物车 → 下单 → 支付 → 凭令牌查订单
```

一期**全程不需要登录**——会员和微信登录属于二期（设计文档就是这么分的）。
所以订单的 `member_id` 是空的，「我的订单」靠本地存的单号 + 查询令牌。

## 跑起来

后端要先起（见根目录 README），然后：

```bash
npm install

# H5 版（浏览器里看，开发调试用）
npm run dev:h5        # → http://localhost:5174，/api 代理到后端 5000

# 微信小程序版
npm run dev:mp-weixin # 编译到 dist/dev/mp-weixin，用开发者工具导入这个目录
```

### 用微信开发者工具打开

1. 打开微信开发者工具 → **导入项目**
2. **目录**选 `mp-customer/dist/dev/mp-weixin`（改了代码会热更新）
   - 想跑稳定版就 `npm run build:mp-weixin`，然后导入 `dist/build/mp-weixin`
3. **AppID** 可以留空用「测试号」，也可以填自己注册的
4. 确认 **详情 → 本地设置 → 不校验合法域名** 是勾上的

> 为什么必须勾那个：微信小程序只能请求「已备案的 HTTPS 域名 + 后台配了白名单的域名」，
> 而本地后端是 `http://localhost:5000`。`manifest.json` 里已经设了
> `urlCheck: false`，但这个开关最终以开发者工具里的勾选为准。

### 真机预览

手机上打开要改一处地址——**手机上的 `localhost` 指向手机自己**，连不到你的电脑：

`src/api/request.ts` 里的 `baseUrl` 改成电脑的内网 IP：

```ts
let baseUrl = 'http://192.168.1.5:5000'   // 换成你自己的内网 IP（ipconfig 查）
```

手机和电脑要在同一个局域网，开发者工具里的「不校验合法域名」也要勾着。

## 后端地址是怎么切的

`src/api/request.ts` 里用条件编译分了两种：

- **H5**：留空，走 Vite 的 dev server 代理（见 `vite.config.ts`），
  这样开发时不跨域
- **小程序**：写完整地址（小程序没有「同源」这个概念）

## 没有对接微信支付

顾客端的「立即支付」调的是后端的 `/api/public/orders/<单号>/pay`，
**它只是把「钱付了」记下来**，流水号带 `MOCK` 前缀。

真实的微信支付要走的链路：

```
服务端调统一下单拿 prepay_id
  → 小程序 wx.requestPayment 调起收银台
  → 微信异步回调到我们的接口
  → 验签 → 才认这笔钱
```

**协议那一层已经写好了**（`backend/app/services/wechat_pay.py`，含签名、验签、
AES-GCM 解密，配一个模拟网关跑通了）。差的是把它接到业务流程里 + 一个真商户号。

## 一期的两个已知缺口

- **顾客不登录**，所以换手机或清缓存之后「我的订单」就没了——这正是二期要做会员的原因
- **没有限流和防重复提交**：后端公开接口对任何人开放，手抖连点也可能下两单
  （记在 `backend/app/schemas/public_schema.py` 末尾）
