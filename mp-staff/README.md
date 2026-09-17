# mp-staff —— 员工小程序端

门店一线用的。技术栈和顾客端一样：**uni-app（Vue3 + Vite + TypeScript）**，
一套代码同时编译到微信小程序和 H5。

## 功能

只放门店一线用得上的三件事：

```
代客点单   服务员在桌边帮顾客下单（order:create）
接单/出单  看本店还没做的单，接单、完成（order:view + order:receive）
团购券核销 美团/抖音买的券，抵这一单的钱（coupon:verify）
```

**菜单、员工、报表那些不在这儿**。手机屏幕塞不下，硬塞进去只会让每件事都变难用——
那些是电脑上的活。首页上也是这么写的。

每个入口和按钮都按登录的人有没有那个权限码来渲染，登录不同账号能看到的东西不一样：

| 账号 | 登录后能看到 |
| --- | --- |
| `shouyin` 收银员 | 三样都有：点单、接单出单、核销 |
| `fuwuyuan` 服务员 | 只有「代客点单」（他没有 `order:receive`） |
| `houcu` 后厨 | 只有「看单」——**他连接单都点不了**，见下面那节 |

## 认证：token，不是 cookie

这是设计文档第 2 条「认证双轨」里说的那条第二条通道：

| | 网页端（web-staff） | 小程序端（这里） |
| --- | --- | --- |
| 凭据 | session cookie | `Authorization: Bearer <token>` |
| 谁来带 | 浏览器自动带 | 自己存、每次放进请求头 |
| CSRF | 要（防止别的站点借用 cookie） | 不要（没有 cookie 可借） |

**两条通道在后端下游是同一个东西**。后端用 `login_manager.request_loader`
从 Bearer 头里认出人，于是 `current_user`、`@permission_required`、
数据范围、审计日志一行都不用改——不是把业务代码写两遍。

token 有效期 7 天（`MP_TOKEN_MAX_AGE`），登出和改密码会让这个人的**所有**
旧 token 一起失效（`Staff.token_version`）。停用账号下一条请求就进不来。

## 跑起来

后端要先起（见根目录 README），然后：

```bash
npm install

# H5 版（浏览器里看，开发调试用）
npm run dev:h5        # → http://localhost:5175，/api 代理到后端 5000

# 微信小程序版
npm run dev:mp-weixin # 编译到 dist/dev/mp-weixin，用开发者工具导入这个目录
```

三个前端的端口是错开的：**5173** 内部人员网页端、**5174** 顾客小程序、**5175** 这里。

用微信开发者工具打开、真机预览要改 `baseUrl` 成内网 IP——
步骤和 `mp-customer/README.md` 里写的一模一样，这里不重复。

## 后厨为什么是只读的

**后厨只有 `order:view`，没有 `order:receive`**，所以这一页对他来说是只读的，
界面上如实写着「只读」。

这不是漏了权限，是后端 RBAC 现在的定义就这么分的：

```
收银员 / 值班经理 / 店长   能接单、能完成（order:receive）
后厨 / 服务员              只能看（order:view）
```

按现在的分工，后厨的职责是「把单子看清楚、把菜做出来」，
接单和完成是前厅的动作，完成之后还要到电脑上收款。

**如果想让后厨自己在小票屏上点「已出餐」**（很多店确实是这么干的），
要加一个 `order:complete` 这样的权限码，单独给后厨——
不能直接把 `order:receive` 给后厨，那等于让他也能接单收款。
这件事记在 `docs/设计决策.md` 的「还没解决」里。