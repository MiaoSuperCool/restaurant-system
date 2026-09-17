"""
拓展管理：统一初始化所有第三方拓展
"""
# 用户登录管理,管理 Session，处理登录、登出、记住我
from flask_caching import Cache

# 缓存支持,缓存数据，减少数据库查询，提升性能
from flask_cors import CORS

# 数据库版本管理,修改模型后自动生成迁移脚本，同步表结构
from flask_login import LoginManager

# 数据库 ORM	,用 Python 对象操作数据库，不用写 SQL
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

# 跨域支持,允许前端（如 Vue/React）调用 API
from flask_wtf.csrf import CSRFProtect

# CSRF 防护,防止跨站请求伪造攻击

class ApiCSRFProtect(CSRFProtect):
    """小程序那条通道上的请求不做 CSRF 校验

    CSRF 能成立，靠的是**浏览器会把 cookie 自动带上**——别的站点伪造一个表单，
    受害者的浏览器顺手把 session cookie 一起发过去，服务端就分不清是不是本人。

    小程序没有这个前提：它不带 cookie，token 存在自己的存储里，
    别的站点既读不到也没法让浏览器「自动带上」它。所以这两类请求上的 CSRF 校验
    挡的不是攻击，而是小程序自己：

    1. **带了 `Authorization: Bearer` 的**——登录之后的每一个请求
    2. **换 token 的那个登录接口**（`/api/auth/token`）——它还没有 token，
       但也没有 cookie，一样拿不到 csrf_token。不豁免的话小程序**连门都进不来**

    （登录接口豁免会不会被利用？登录 CSRF 的攻击场景是「让受害者的浏览器
    登进攻击者的账号」，可这个接口不发 cookie、响应也是跨域读不到的，
    攻击者拿不到任何东西。加上 /api/* 的 CORS 只放行了开发机的来源，
    别处发过来的请求连预检都过不了。）

    **带 cookie 的网页请求照常校验**——浏览器那一边的防护一点没少。
    """

    # 登录接口本身：它拿不到 csrf_token，只能整个豁免
    CSRF_FREE_PATHS = {'/api/auth/token'}

    def protect(self):
        from flask import request

        from backend.app.utils.token import bearer_token

        if request.path in self.CSRF_FREE_PATHS:
            return
        if bearer_token() is not None:
            return
        super().protect()


# ========== 创建扩展实例 ==========
db = SQLAlchemy()
migrate = Migrate()
cache = Cache()
cors = CORS()
csrf = ApiCSRFProtect()
login_manager = LoginManager()

# ========== LoginManager 特殊配置 ==========
login_manager.login_view = 'auth.login'  # 未登录时跳转
login_manager.login_message = '请先登录'
login_manager.login_message_category = 'warning'
# 控制 Flash 消息的 CSS 样式类别。warning 对应 Bootstrap 的黄色警告框

# ========== 用户加载器 ==========
@login_manager.user_loader
def load_user(user_id):
    """根据员工ID加载登录对象（web 端 session 认证用）"""
    from .models.staff import Staff
    return db.session.get(Staff, int(user_id))


@login_manager.request_loader
def load_user_from_request(request):
    """从 `Authorization: Bearer <token>` 认出人（小程序端 token 认证用）

    **有了它，两条认证通道在下游就是同一个东西**：`current_user` 一样、
    `@login_required` 一样、`@permission_required` 一样、service 层里
    `current_user.accessible_store_ids()` 一样、审计日志记的也一样——
    「怎么认出这个人」和「认出之后能干什么」被彻底分开了。

    这正是设计文档第 2 条那句「两条通道共用同一套 service 层和权限判断」的落地方式：
    **不是把业务代码写两遍，而是让 `current_user` 在两个场景下都成立。**
    """
    from backend.app.services.auth_service import AuthService
    from backend.app.utils.token import bearer_token

    token = bearer_token()
    if not token:
        return None
    return AuthService.resolve_token(token)


# ========== 未登录处理器 ==========
@login_manager.unauthorized_handler
def unauthorized():
    """未登录访问受保护接口时返回 401 JSON（而不是 302 跳转到登录页 HTML）"""
    from flask import jsonify

    from backend.app.utils.api_response import api_response
    return jsonify(api_response(success=False, message='请先登录')), 401
