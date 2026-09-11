# 餐饮多门店系统

一套后端 + 三套前端的前后端分离架构：

| 目录 | 端 | 用户 | 技术栈 |
| --- | --- | --- | --- |
| `backend/` | 后端 API（一套） | — | Flask 3 / SQLAlchemy / MySQL |
| `web-staff/` | 内部人员网页端 | 收银员、店长、运营、财务、老板 | Vue3 + TS + Element Plus |
| `mp-staff/` | 内部人员小程序端 | 服务员代点单、后厨出单 | uni-app (Vue3 + TS) |
| `mp-customer/` | 顾客小程序端 | 到店/自取/外卖顾客 | uni-app (Vue3 + TS) |

本项目基于自建的 Flask + Vue3 脚手架模板起步（认证、用户管理、审计日志、黑白灰 UI 已开箱即用），
下面是模板自带的说明，其中"前端"均指 `web-staff/`。

## 内置功能

- 登录/登出（Flask-Login 会话认证 + CSRF 的 SPA 适配）
- 用户管理（管理员 CRUD、启用/禁用、角色切换）
- 审计日志（操作自动记录，管理员可查）
- 权限控制（后端 `admin_required` 兜底 + 前端路由守卫/菜单过滤）
- 自动接口文档（flask-smorest：schema 即文档，Swagger UI 在 `/apidocs`）
- 三栏布局 + 黑白灰极简风格（Element Plus 主题定制）

## 技术栈

后端：Flask 3 / SQLAlchemy / Flask-Migrate / Flask-Login / Flask-WTF / Marshmallow / MySQL
前端：Vue 3 + TypeScript / Vite / Vue Router / Pinia / Element Plus / Axios

## 目录结构

```
├── backend/                  # Flask 后端
│   ├── app/
│   │   ├── api/              # 蓝图路由（auth/users/audit/main）
│   │   ├── models/           # SQLAlchemy 模型（BaseModel 带公共时间戳）
│   │   ├── schemas/          # Marshmallow 输入校验
│   │   ├── services/         # 业务逻辑 + 审计记录
│   │   ├── utils/            # 统一响应、权限装饰器
│   │   └── config.py         # 多环境配置（development/production/testing）
│   ├── migrations/           # Alembic 迁移
│   ├── manage.py             # CLI：create-admin / reset-db
│   └── .env.example          # 环境变量模板
├── web-staff/                # 内部人员网页端（Vue3）
│   └── src/
│       ├── api/              # axios 封装 + 按领域拆分的接口模块
│       ├── layouts/          # 三栏主布局
│       ├── views/            # 页面（Login/Home/Users/Audit）
│       ├── components/       # Sidebar、UserCard、表单弹窗
│       ├── stores/           # Pinia（用户状态）
│       └── router/           # 路由 + 登录/角色守卫
├── Dockerfile                # 多阶段构建（前端产物 + 后端 gunicorn）
├── docker-compose.yml        # MySQL + Redis + 应用 一键启动
└── create_db.py              # 首次建库脚本（库名取自 .env）
```

## 从模板起步（本地开发）

1. 安装依赖：
   ```bash
   python -m venv .venv && .venv/Scripts/activate   # Windows（Linux/macOS 用 .venv/bin/activate）
   pip install -r backend/requirements.txt
   cd web-staff && npm install
   ```
2. 配置环境：`cp backend/.env.example backend/.env`，改 `DATABASE_URL` 的库名/账号密码
3. 建库：在项目根目录 `python create_db.py`（自动创建 .env 里指定的数据库）
4. 迁移建表 + 创建管理员：
   ```bash
   cd backend
   flask db upgrade                    # 应用迁移建表
   python manage.py create-admin       # 按提示创建管理员
   ```
5. 启动前后端：
   ```bash
   # 后端（backend 目录）：flask run --debug   （端口 5000）
   # 网页端（web-staff 目录）：npm run dev      （端口 5173，代理到 5000）
   ```
   浏览器打开 http://localhost:5173

## 接口文档

后端启动后浏览器打开 http://localhost:5000/apidocs/（Swagger UI）：

- 文档由 flask-smorest 从接口装饰器和 schema **自动生成**（OpenAPI JSON 在 `/api/docs/openapi.json`）——新增接口参数只需改 schema，文档自动同步，不会像手写注释那样过期
- 错误状态码约定：400 业务冲突 · 401 未登录/密码错误 · 403 无管理员权限 · 404 资源不存在 · 422 参数校验失败
- Try it out 写接口（POST/PUT/DELETE）会被 CSRF 拦：需在页面 Authorize 里填入 `X-CSRFToken`（值 = 浏览器 cookie 中 `csrf_token`）
- 生产环境不想暴露文档：`.env` 里设 `ENABLE_API_DOCS=false`

## Docker 一键部署

```bash
docker compose up -d --build
```

自动完成：启动 MySQL/Redis → 迁移建表 → 创建管理员 → gunicorn 托管前后端。
打开 http://localhost:5000，可用环境变量覆盖默认配置（`DB_PASSWORD`、`SECRET_KEY`、`ADMIN_PASSWORD` 等，见 docker-compose.yml 顶部注释）。

## 添加新业务模块（照"用户管理"示例）

后端：`models/xxx.py` → `schemas/xxx_schema.py`（schema 同时管请求校验和接口文档）→ `services/xxx_service.py` → `api/xxx.py`（flask-smorest Blueprint，请求参数用 `@bp.arguments(Schema, location='json')` 声明）→ 在 `backend/app/__init__.py` 的 `register_blueprints` 里 `api.register_blueprint(xxx.bp)` → `flask db migrate -m "xxx"` 生成迁移
前端：`api/xxx.ts` → `views/XxxView.vue` → `components/XxxFormDialog.vue` → router 加子路由（管理员页面加 `meta: { requiresAdmin: true }`）+ Sidebar 菜单加一项
首页统计：改 `backend/app/api/main.py` 的 `index()` 和 `web-staff/src/api/main.ts`

## 测试与代码规范

```bash
# 后端测试（backend 目录或项目根均可）
pytest                              # 运行全部测试
pytest --cov=app tests/             # 带覆盖率报告

# 后端代码规范
ruff check app tests                # 检查
ruff check --fix app tests          # 自动修复

# 前端
npm run typecheck                   # 类型检查（vue-tsc）
npm run lint                        # ESLint 检查
npm run test                        # 单元测试（vitest：stores/组件逻辑，测试在 web-staff/tests/）
npm run format                      # Prettier 格式化
```

## 新项目改名

全局替换三处：前端 `package.json` 的 `name`、前端 `src/stores/user.ts` 的 `USER_STORAGE_KEY`、后端 `.env` 的 `APP_NAME`（前端标题）。包名 `backend` 如需改名，同步修改所有 `backend.app` 导入路径。

## 注意事项

- 代码用 `backend.app` 绝对导入，`flask` 命令在 backend 目录运行；迁移目录默认 backend/migrations
- 本地 venv 需写入 site-packages 的 `.pth` 指向项目根（否则 flask 找不到 backend 包）
- 仪表盘接口在 `/index`（无 /api 前缀），部署时 Nginx 需同时反代 `/api` 和 `/index`；如需对外提供接口文档，再反代 `/apidocs` 和 `/api/docs`
- CSRF 用 cookie 携带 token + 前端拦截器自动加 `X-CSRFToken` 头，勿改回 session 原始值
- 生产环境必须设置强随机 `SECRET_KEY` 和 `SESSION_COOKIE_SECURE=true`