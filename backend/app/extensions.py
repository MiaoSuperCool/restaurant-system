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

# ========== 创建扩展实例 ==========
db = SQLAlchemy()
migrate = Migrate()
cache = Cache()
cors = CORS()
csrf = CSRFProtect()
login_manager = LoginManager()

# ========== LoginManager 特殊配置 ==========
login_manager.login_view = 'auth.login'  # 未登录时跳转
login_manager.login_message = '请先登录'
login_manager.login_message_category = 'warning'
# 控制 Flash 消息的 CSS 样式类别。warning 对应 Bootstrap 的黄色警告框

# ========== 用户加载器 ==========
@login_manager.user_loader
def load_user(user_id):
    """根据用户ID加载用户对象"""
    from .models.user import User
    return db.session.get(User, int(user_id))


# ========== 未登录处理器 ==========
@login_manager.unauthorized_handler
def unauthorized():
    """未登录访问受保护接口时返回 401 JSON（而不是 302 跳转到登录页 HTML）"""
    from flask import jsonify

    from backend.app.utils.api_response import api_response
    return jsonify(api_response(success=False, message='请先登录')), 401
