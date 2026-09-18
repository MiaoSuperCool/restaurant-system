# ============================================
# 多阶段构建：前端 Vite 产物 + Flask 后端 → 单镜像
# 构建上下文是项目根目录：docker build -t restaurant-system .
# ============================================

# ---------- 阶段1：构建内部人员网页端 ----------
FROM node:20-alpine AS web-staff-builder
# 以 node 官方 20 版的 alpine镜像为起点，给这个阶段起名web-staff-builder，供后面引用
WORKDIR /app/web-staff
# 接下来都在这个目录下操作，相当于cd，目录不存在会自动创建，之后的 COPY、RUN都以它为相对路径基准
COPY web-staff/package.json web-staff/package-lock.json ./
RUN npm ci
# ci=clean install，它的作用是：在镜像里从零全新安装一遍依赖，保证装出来的结果 100% 可复现、确定
COPY web-staff/ ./
# 把全部前端源码拷进去，执行 npm run build，产出静态文件到 web-staff/dist/
RUN npm run build

# ---------- 阶段2/3：两个小程序端的 H5 产物 ----------
# 小程序端是 uni-app 一套代码两种产物：微信小程序（要正式 AppID，装不了真机）
# 和 H5。线上给别人看的是 H5 这一份，所以镜像里也要有。
#
# **H5_BASE 是构建参数，不是运行参数**：路径前缀要写死在产物里的资源引用上
# （见各自 vite.config.ts），和后端 /customer/、/staff/ 两条路由对应。
# 写成 ARG 而不是 ENV：只有这一条 RUN 用得上，没必要留在镜像的环境变量里
FROM node:20-alpine AS mp-customer-builder
WORKDIR /app/mp-customer
COPY mp-customer/package.json mp-customer/package-lock.json ./
RUN npm ci
COPY mp-customer/ ./
RUN H5_BASE=/customer/ npm run build:h5
# 产物在 dist/build/h5（uni-app 的约定，中间那层 build 区分 build/dev）

FROM node:20-alpine AS mp-staff-builder
WORKDIR /app/mp-staff
COPY mp-staff/package.json mp-staff/package-lock.json ./
RUN npm ci
COPY mp-staff/ ./
RUN H5_BASE=/staff/ npm run build:h5

# ---------- 阶段4：后端运行环境 ----------
FROM python:3.12-slim
# 以 python 3.12 的slim（精简版）镜像为基底。前面 stage 1 那台"装了Node 的临时机器"使命完成不要了——这就是多阶段构建省体积的关键
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
# PYTHONDONTWRITEBYTECODE=1：别生成__pycache__/*.pyc 缓存文件，镜像里少垃圾文件；
# PYTHONUNBUFFERED=1：Python输出不缓冲。日志立刻打出来，否则 docker logs会半天看不到输出（等缓冲写满才显示），像网页没刷新一样

# 安装依赖（gunicorn 仅在 Linux 容器中安装，不进 requirements.txt）
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt gunicorn
# -no-cache-dir：pip的下载缓存不留在镜像里，减体积（和 alpine、slim的选型同一目的——镜像越小，传输和启动越快）
# gunicorn 单独装、不进requirements.txt：因为它是生产环境 Web服务器，本地开发用的是 flask run，不需要它。容器是生产形态，所以在这单独装

# 后端代码 + 前端构建产物
# 前端产物必须放在 /app/web-staff/dist（backend/app/__init__.py 的 FRONTEND_DIST 按相对路径计算）
COPY backend/ ./backend/
COPY --from=web-staff-builder /app/web-staff/dist ./web-staff/dist
# 两个小程序端的 H5 产物：目录名要和后端里的 CUSTOMER_DIST / STAFF_DIST 对上
COPY --from=mp-customer-builder /app/mp-customer/dist/build/h5 ./mp-customer/dist/build/h5
COPY --from=mp-staff-builder /app/mp-staff/dist/build/h5 ./mp-staff/dist/build/h5

WORKDIR /app/backend
EXPOSE 5000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "wsgi:app"]
# gunicorn是Python 的生产级 Web服务器,平时开发用的 flask run 是 Flask自带的开发服务器——单进程、性能差、调试用
# 生产环境用 gunicorn接收 HTTP 请求、调用你的 Flask 应用处理、再把响应发回去
# 用 gunicorn 起 4 个工作进程(-w 4)，监听0.0.0.0:5000(-b意思是bind)，wsgi:app 告诉gunicorn "去哪个模块找哪个应用"
# 注意必须写0.0.0.0（所有网卡）而不是 127.0.0.1，否则容器外（宿主机、其他容器）访问不到
