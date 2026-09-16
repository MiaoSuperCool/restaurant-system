# 餐饮多门店系统

面向连锁餐饮的经营管理后端 + 内部人员网页端。跑通的业务闭环是：

```
老板配菜单 → 各店定自己的价 → 下单 → 门店接单 → 收款 → 完成
```

一套 Flask 后端 + 三个客户端（内部人员网页端 Vue3、内部人员小程序端 uni-app、顾客小程序端 uni-app），
三端共用同一套业务逻辑和权限体系。目前 **后端 + 内部人员网页端** 已完成一期主体。

<img src="docs/screenshots/dashboard.png" width="820" alt="首页看板" />

## 快速开始

需要 MySQL 8 和 Node 20+。四条命令：

```bash
# 1. 后端依赖
python -m venv .venv
source .venv/Scripts/activate          # Windows（Linux/macOS 用 .venv/bin/activate）
pip install -r backend/requirements.txt

# 2. 配置数据库并建库
cp backend/.env.example backend/.env   # 改里面的 DATABASE_URL 为你的 MySQL 账号密码
python create_db.py                    # 自动创建 .env 里指定的库

# 3. 建表 → 灌权限 → 灌演示数据
cd backend
flask db upgrade
python manage.py seed-rbac             # 38 个权限码 + 8 个预置角色
python manage.py seed-demo             # 6 家门店、15 道菜、9 个账号、12 笔订单

# 4. 起服务
flask run --debug                      # 后端 :5000
cd ../web-staff && npm install && npm run dev   # 内部人员网页端 :5173
cd ../mp-customer && npm install && npm run dev:h5   # 顾客小程序（H5 版）:5174
```

> 顾客小程序端的详细说明（怎么用微信开发者工具打开、真机预览要改什么）
> 见 [mp-customer/README.md](mp-customer/README.md)。

浏览器打开 http://localhost:5173，用下面的账号登录。接口文档在 http://localhost:5000/apidocs/。

> **`flask` 命令必须在 `backend/` 目录下运行。** Flask 靠当前目录里的 `wsgi.py` 找应用，
> 在项目根目录跑会报 `Error: Could not locate a Flask application`。
> 不想切目录的话，用 `flask --app backend.wsgi run --debug`。
> （`python manage.py ...` 没有这个限制，它自己会把项目根加进 `sys.path`。）

> **`seed-rbac` 和 `seed-demo` 只能用 `python manage.py` 跑，不能用 `flask`。**
> 它们定义在 `manage.py` 的 `FlaskGroup` 里，而 `flask` 命令从 `wsgi.py` 找应用——
> 那个应用上只有 `db` 这类内置命令，`flask seed-rbac` 会报 `No such command`。

> 第 3 步的 `flask db upgrade` 只是建表；**没有 `seed-rbac` 的话所有角色都没有权限**，
> 除了超级管理员谁都干不了活。

## 演示账号

密码统一是 `Demo123!`。**换个账号登录，看到的菜单和按钮都不一样**——这是权限体系最直观的演示：

| 账号 | 角色 | 登录后能看到 |
| --- | --- | --- |
| `laoban` | 老板 | 全部菜单，含门店管理、员工管理、审计日志 |
| `yunying` | 运营主管 | 菜单管理（菜品/分类/门店菜单）、门店查看；**看不到**员工、订单和审计 |
| `caiwu` | 财务 | 订单、门店；**碰不了菜单**，也没有点单入口 |
| `dianzhang` | 店长 | 点单、本店订单、本店菜单定价、本店员工、角色矩阵；**看不到别家店**，也进不了公司级的菜品/分类页 |
| `zhiban` | 值班经理 | 点单、订单（含取消）；**批不了大额退款** |
| `shouyin` | 收银员 | 点单、订单（接单/收款）；**没有取消订单的权限** |
| `fuwuyuan` | 服务员 | 点单、订单；只能代客点单，不能收款 |
| `gongyong` | 服务员（公用账号） | 同上——注意演示数据里它的订单记的是「实际操作人」而不是账号本身 |
| `houcu` | 后厨 | 只有订单，用来看单出餐（**没有点单**——后厨不点菜） |

用 `shouyin` 和 `dianzhang` 对照着登一遍，权限和数据范围的区别一眼就能看出来。

## 已经能跑通的

- **门店管理** —— 6 家店的档案、营业状态、灰度切换模式（老系统/新系统）；删除有引用保护
- **员工账号** —— 角色分配、门店归属、全职/兼职、公用账号
- **权限体系** —— 38 个权限码 × 8 个预置角色 × 数据范围（本店/全部），后端强制、前端按权限渲染
- **菜单管理** —— 菜品分类（含适用门店）、菜品、规格组/选项（份量/辣度/加料，单选多选必选）
- **多店定价** —— 同一道菜各店不同价、各店独立上下架、每日限量
- **点单收银** —— 点单界面（分类浏览、规格选择、购物车）、接单、完成、取消、收款（支持组合支付）

<img src="docs/screenshots/pos.png" width="820" alt="点单界面" />

<img src="docs/screenshots/orders.png" width="820" alt="订单列表" />

- **退款审批流** —— 申请 → 审批 → 确认打款三步走，**审批通过不等于钱退了**；
  线下退款也要补录留痕；超过限额的退款要更高权限

<img src="docs/screenshots/refunds.png" width="820" alt="退款单列表" />

- **团购券核销** —— 扫码核销美团/抖音团购券，券码**全局唯一**（同一张券核销第二次会被拒）；
  核销记录按平台留着，月底拿去对账
- **打小票** —— 80mm 热敏纸版式的预结单/小票，可直接调起浏览器打印

<img src="docs/screenshots/receipt.png" width="420" alt="小票" />

- **顾客小程序** —— 扫码进店 → 浏览菜单 → 选规格 → 下单 → 支付 → 查订单，
  **全程不需要登录**（会员是二期）。uni-app 一套代码编译到微信小程序 + H5。
  查订单要「单号 + 随机令牌」——单号是可读可猜的，光凭单号能查到别人的订单

<img src="docs/screenshots/mp-menu.png" width="300" alt="小程序点单" />
<img src="docs/screenshots/mp-picker.png" width="300" alt="规格选择" />
- **会员 + 储值**（二期第一块）—— 会员全公司通用；储值**本金和赠送分开记**，
  余额支付接进了收款流程（一单最多扣一笔），退款能按原消费的比例退回储值

  三条规则值得单独说：
  **① 余额必须有流水账**，不能只存一个数字——那 80 万要一分不差，全靠流水对得上
  **② 充 100 送 20 要记两条流水**：本金是收入、赠送是营销成本，报表上是两回事
  **③ 扣款先扣赠送再扣本金**：先花掉不能退的那部分，本金留着随时能退

- **审计日志** —— 改价、上下架、发券、开停账号等关键动作自动留痕，含变更前后值
- **角色权限矩阵** —— 8 个角色 × 38 个权限码的全貌，一眼看出谁能在哪些门店做什么

## 几个设计上的取舍

这部分是这个项目里最值得看的东西——每个决定都有具体的理由，不是随手写的。
完整版（16 条）在 **[docs/设计决策.md](docs/设计决策.md)**，下面挑四条讲。

### 一、权限分两层：能不能干 vs 能碰哪些数据

餐饮门店最容易踩的坑，是以为「能不能干」和「能碰哪些数据」是一回事。

比如 `dish:price:edit`（改价）这个权限，**店长和运营主管都有**。区别不在能不能改，
而在**能改哪些**：店长只能改自己那家店的价，运营主管能改全公司的。

所以权限模型是两层的：

| 层 | 挂在哪 | 管什么 |
| --- | --- | --- |
| 权限码 | 角色 | 能不能干这件事（`store:view` / `order:refund`） |
| 数据范围 | 角色 | 能碰哪些数据（`store` 本店 / `all` 全部） |

**数据范围必须挂在角色上，不能挂在权限码上**——一旦把范围写进权限码，就得为每个
角色各造一套权限码（`dish:price:edit:store`、`dish:price:edit:all`……），组合爆炸。

权限码目录（`backend/app/rbac.py`）是**代码而不是数据库里的数据**，`python manage.py seed-rbac`
幂等同步。这样「谁把收银员的核销权限去掉了」能查 git blame，改乱了也能一键还原。

全貌长这样（8 个角色 × 38 个权限码，数据范围单独一行）：

<img src="docs/screenshots/roles.png" width="820" alt="角色权限矩阵" />

角色与权限之间用的是纯关联表（`db.Table` 而非建模成类）：关联本身没有额外属性，
而**复合主键能在数据库层挡住重复关联**——同一个员工同一个角色物理上不可能出现两条。

### 二、多店定价：菜品和门店解耦

设计里最容易做错的一件事，是在菜品表上放一个 `price` 字段然后到处覆盖。

这里的做法是拆成两层：

```
dish（菜品基础）        名称、图片、描述、分类、基础价   ← 全公司一套
  └── store_dish        覆盖价格、是否上架、每日限量      ← 每家店一行
```

**关键约定：没有行 = 用默认值。** 不是每家店每道菜都有一行，而是「这家店对这道菜
做了特殊设置」才有一行；没有行就是基础价、可售、不限量。

不这么做的话：6 家店 × 50 道菜 = 300 行，运营每加一道菜要手动上架 6 次。

代价是「查某道菜在某店的价格」要合并两层，所以有 `effective_price` 和 `_merge()`
把这件事收在一处，调用方不用自己判断 `price` 是不是 `None`。

界面长这样——西溪印象城店把红烧牛肉面调到 ¥35（基础价 ¥32 划掉）、限量 30 份，
其他店不受影响：

<img src="docs/screenshots/store-menu.png" width="820" alt="门店菜单：多店定价" />

### 三、订单：快照和引用，两个都要

订单明细里的菜名和单价，**必须存快照**——运营明天把「牛肉面」改名成「红烧牛肉面」、
涨价到 ¥40，历史订单要还原成下单当时的样子，否则月底对账时「这单到底卖了多少钱」说不清。

但只存文本快照又不行：设计里要求「统计加蛋卖了多少份」「控加牛肉的库存」，
纯文本做不到。所以明细里**同时**保留 `dish_id` 和 `dish_option_id` 的引用。

**快照负责还原，引用负责统计。**

同理，支付没有做成订单上的一个「已支付」布尔字段，而是单开一张 `payment` 表：

- 一个订单可能有**多笔支付**：组合支付（储值付一部分 + 现金付一部分）、先定金后尾款
- 支付有**资金属性**：第三方流水号、支付时间——**财务对账全靠它**

以及一条业务规则：**已收款的订单不能直接取消**。钱得先退回去，退款走独立的审批单。
否则就会出现「订单取消了但钱还在我们账上」。

### 四、删除保护：扫外键，而不是手写清单

每个实体删除前都要检查「还有没有别的东西在引用我」。手写「要检查哪些表」的清单迟早会漏，
所以反过来扫 SQLAlchemy metadata 里所有指向目标主键的外键——新表只要建了外键就自动覆盖。

其中 **`ondelete='CASCADE'` 的外键会被跳过**：CASCADE 表示「从属/关联」
（规格选项属于菜品、角色绑定属于员工），父记录删了子记录跟着走，不算阻塞；
只有 RESTRICT / SET NULL 才是真正的「外部还在引用」。

这里有个细节：`ondelete` 这个参数**本身就已经表达了「从属还是引用」**，
所以检查逻辑不需要再手工维护一份「哪些表算从属」的名单——直接读它。建模时的意图，
被复用成了运行时的判断依据。

## 技术栈

**后端** Flask 3 · SQLAlchemy · Flask-Migrate(Alembic) · Flask-Login · Flask-WTF(CSRF) ·
Marshmallow / flask-smorest（schema 即接口文档）· MySQL

**前端** Vue 3 + TypeScript · Vite · Vue Router · Pinia · Element Plus · Axios

## 项目结构

```
restaurant-system/
├── backend/
│   ├── app/
│   │   ├── models/        # 数据模型（BaseModel 带公共时间戳）
│   │   ├── schemas/       # Marshmallow 校验（同时生成 OpenAPI 文档）
│   │   ├── services/      # 业务逻辑 + 数据范围 + 审计
│   │   ├── api/           # 蓝图路由
│   │   ├── rbac.py        # 权限码目录 + 预置角色（权限体系的唯一事实来源）
│   │   ├── demo.py        # 演示数据定义
│   │   └── utils/         # 统一响应、权限装饰器、外键引用检查
│   ├── migrations/        # Alembic 迁移
│   └── tests/             # pytest（180 个）
├── web-staff/             # 内部人员网页端（Vue3）
│   └── src/
│       ├── api/           # axios 封装 + 按领域拆分的接口模块
│       ├── views/         # 页面
│       ├── components/    # 表单弹窗、详情弹窗
│       ├── stores/auth.ts # 登录态 + 权限
│       └── constants/     # 枚举选项（与后端模型常量一一对应）
├── mp-customer/           # 顾客小程序端（uni-app，编译到微信小程序 + H5）
│   └── src/
│       ├── api/           # uni.request 封装 + 顾客端接口
│       ├── pages/         # 选门店 / 点单 / 我的订单 / 订单详情
│       ├── stores/        # 购物车、本地订单记录（没用 Pinia，模块级 reactive 够）
├── docs/                  # 需求与设计文档
└── docker-compose.yml     # MySQL + Redis + 应用一键起
```

## 哪些是模拟的

做一个真实系统时会卡在别人手里的部分，这里**明确标出来**，而不是假装做完了：

| 能力 | 现状 |
| --- | --- |
| **微信支付** | 未对接。目前收款只是「记账」（记下方式、金额、第三方流水号），签名、回调验签、退款调用都还没写 |
| **团购券核销** | 券码是收银员手工输入的、平台手选的，**没有真的调美团/抖音的核销接口**。真对接时要加一步「调平台接口验证券码有效性」，面额也不该由人工填 |
| **积分 / 优惠券** | 二期范围，还没做 |
| **微信登录** | 会员表留了 `openid` / `unionid`，但没有真 AppID 接不了——所以现在只能员工代客办卡 |
| **退款的「打款」这一步** | 流程走通了（申请→审批→确认打款→记流水），但确认打款目前只是记账，没有真的调微信退款接口 |
| **ERP 对接 / 老系统数据迁移** | 属于二~四期，且不存在真实系统可对接 |
| **顾客小程序的支付** | 「立即支付」只是把「钱付了」记下来，流水号带 `MOCK` 前缀。**协议层已经写好并测过**（签名/验签/AES 解密 + 自建模拟网关），差的是接到业务流程里和一个真商户号 |
| **员工小程序** | 未开始（二期）。服务员代点单、后厨出单在网页端已经能用，小程序只是更顺手 |

## 开发

```bash
# 后端（在 backend/ 目录下）
cd backend
flask run --debug                      # 开发服务器 :5000
flask db upgrade                       # 应用迁移
python manage.py seed-rbac             # 同步权限码与角色（改了 rbac.py 之后跑）
python manage.py seed-demo             # 灌演示数据（--reset 清空重建）
python manage.py create-admin          # 创建超级管理员
pytest                                 # 全部测试
pytest --cov=app tests/                # 带覆盖率
ruff check . --fix                     # 代码规范

# 前端（在 web-staff/ 目录下）
cd web-staff
npm run dev                            # 开发服务器 :5173，代理到 5000
npm run typecheck                      # vue-tsc 类型检查
npm run lint                           # ESLint
npm run test                           # vitest 单元测试
npm run build                          # 生产构建
```

**新模块的固定流程**（以「加一个库存管理」为例）：

1. `models/xxx.py` → `schemas/xxx_schema.py` → `services/xxx_service.py` → `api/xxx.py`
2. 在 `app/__init__.py` 的 `register_blueprints` 里注册
3. `flask db migrate -m "xxx"` 生成迁移
4. 权限：在 `app/rbac.py` 的 `PERMISSIONS` 登记权限码 → 决定哪些角色拥有 → `python manage.py seed-rbac`
   （**改了 rbac.py 一定得跑这一步**：新码不落库的话，前端 `hasPermission` 就是 false，
   按钮不显示——不报错，只是"点不到"，很难往这上面想）
5. 接口挂 `@permission_required('xxx:yyy')`；**能碰哪些数据**另算，由 service 层按 `current_user.accessible_store_ids()` 过滤
6. 前端：`api/xxx.ts` → `views/XxxView.vue` → router 加子路由（`meta: { permissions: [...] }`）+ Sidebar 的 `ALL_MENUS` 加一项

## 关于这个项目

一个练习作品，用来把「多门店餐饮系统」这套业务从头到尾做一遍。
需求文档和设计决策都放在 `docs/` 下。
