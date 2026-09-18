"""
配置管理：不同环境使用不同的配置
"""
import os

from dotenv import load_dotenv
from sqlalchemy.pool import StaticPool

load_dotenv()

# backend 目录的绝对路径（config.py 位于 backend/app/ 下）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Config:
    """
    基础配置（所有环境公用）
    """

    # Flask
    # 从环境变量中获取密钥，如果环境变量不存在那么就使用后面这个默认值
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    APP_NAME = os.getenv('APP_NAME', '餐饮管理系统')

    # 数据库
    # 模板默认值仅作示例，正式项目请在 backend/.env 中配置真实连接
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'mysql+pymysql://root:password@localhost:3306'
                                                        '/restaurant_system')
    # 是否追踪对象变化，设为True会消耗额外内存
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # 数据库连接池大小，避免高并发时连接不够，请求排队
    SQLALCHEMY_POOL_SIZE = 10
    # 等待数据库连接的超时时间，避免连接池满了，请求一直等待
    SQLALCHEMY_POOL_TIMEOUT = 30

    # Redis(缓存)
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    # 跨域：允许哪些前端来源访问 /api/*（逗号分隔），开发时填 Vite dev server 地址
    FRONTEND_ORIGINS = [
        o.strip()
        for o in os.getenv('FRONTEND_ORIGINS', 'http://localhost:5173').split(',')
        if o.strip()
    ]

    # 日志：目录（默认 backend/logs）和级别
    LOG_DIR = os.getenv('LOG_DIR', os.path.join(BASE_DIR, 'logs'))
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

    # Session
    # 表示Cookie是否只在HTTPS下传输， 生产环境必须开启，防止中间人攻击
    # 括号中的false是默认值，当环境变量不存在时使用
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    # JavaScript能否读取Cookie，开启后防止XSS攻击偷Cookie
    SESSION_COOKIE_HTTPONLY = True
    # 防止CSRF跨站攻击，网站之间的请求安全隔离
    SESSION_COOKIE_SAMESITE = 'Lax'

    # CSRF token 的有效期：**不单独计时，跟着 session 走**
    #
    # signed token 里带的那个时间戳，是 Flask-WTF 默认拿来判 1 小时过期的
    # （`validate_csrf` 里 `s.loads(data, max_age=time_limit)`）。
    #
    # 现在 `set_csrf_cookie` **每个响应都重新签一次**，时间戳永远是新的，
    # 所以这个限制基本轮不到触发。设成 None 是为了另一种情况：
    # **页面长时间挂着没发过请求**（收银台一开就是 8 小时），
    # cookie 里那个 signed 早就超过 1 小时了，默认配置下这时候会 400——
    # 前端虽然会换一个自动重试，但没必要让这件事发生。
    #
    # （以前这里是为了绕开一个 bug 才设成 None：signed 被缓存在 session 里重复发，
    # 时间戳冻住了，一小时后就一直发过期的出去。病根已经修掉，见 __init__.py。）
    WTF_CSRF_TIME_LIMIT = None

    # 小程序 token 的有效期（秒），默认 7 天
    #
    # 比网页端的 session 长得多，因为场景不一样：收银台的网页是「开一天」，
    # 服务员的小程序是「揣兜里」，每天上班先登一次会烦死人。
    # 到期就必须重新输密码——这中间如果账号被停用、角色被改，**下一条请求就生效**
    # （token 里只放「你是谁」，权限每次现查，见 utils/token.py）
    MP_TOKEN_MAX_AGE = int(os.getenv('MP_TOKEN_MAX_AGE', 7 * 24 * 3600))

    # 密码加密强度（2的12次方次计算），数值越高越安全，但登录越慢
    BCRYPT_ROUNDS = int(os.getenv('BCRYPT_ROUNDS', 12))

    # 管理员初始账号（manage.py create-admin 命令使用）
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'Admin123!')
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@example.com')

    # 分页
    DEFAULT_PAGE_SIZE = int(os.getenv('DEFAULT_PAGE_SIZE', 10))

    # 退款审批限额：超过这个金额的退款需要 refund:approve:large 权限
    # （值班经理能批限额内的，大额要店长或老板批——设计文档里的角色区分就落在这个数上）
    REFUND_APPROVE_LIMIT = float(os.getenv('REFUND_APPROVE_LIMIT', '200'))

    # API 文档（Swagger UI 页面 /apidocs/ + OpenAPI JSON /api/docs/openapi.json）
    # 测试环境强制关闭（见 app/__init__.py 的 register_api_docs）；生产如不想对外暴露可置 false
    ENABLE_API_DOCS = os.getenv('ENABLE_API_DOCS', 'true').lower() == 'true'


class DevelopmentConfig(Config):
    """
    开发环境配置
    """
    DEBUG = True  # 显示错误详情
    SQLALCHEMY_ECHO = True  # 显示SQL日志
    # 开发环境使用HTTP就行
    SESSION_COOKIE_SECURE = False
    CACHE_TYPE = 'RedisCache'
    CACHE_REDIS_URL = 'redis://localhost:6379/0'
    CACHE_DEFAULT_TIMEOUT = 300


class ProductionConfig(Config):
    """
    生产环境配置
    """
    DEBUG = False
    SQLALCHEMY_ECHO = False
    # 生产环境强制使用HTTPS
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'true').lower() == 'true'
    # 这里是**默认要 HTTPS、但允许关掉**：只有公网 IP、没有域名和证书的演示环境
    # 很常见，写死 True 的话 cookie 标着 Secure 发出去，浏览器在 http 下不回传，
    # 表现是「登录点了没反应」（POST 明明返回 200，下一个请求却是未登录）。
    # docker-compose.yml 里那句 SESSION_COOKIE_SECURE: "false" 就是调这个开关的——
    # 写死的时候它是个死开关，谁改都不生效
    # 代表“记住我”功能的Cookie是否只在HTTPS下传输
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE


class TestingConfig(Config):
    """
    测试环境配置
    """
    # 启用测试模式
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    # 测试不依赖 Redis，用进程内缓存
    CACHE_TYPE = 'SimpleCache'
    # 内存数据库用 StaticPool 固定单连接，保证 create_all 和请求用同一个库
    SQLALCHEMY_ENGINE_OPTIONS = {
        'poolclass': StaticPool,
        'connect_args': {'check_same_thread': False},
    }
    # 关闭CSRF保护，每次测试时不用带token
    WTF_CSRF_ENABLED = False
