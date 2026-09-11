"""
应用工厂：负责创建和配置Flask应用实例
这是整个项目的"组装车间"
"""
import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, send_from_directory, session
from flask_wtf.csrf import generate_csrf

from backend.app.config import DevelopmentConfig, ProductionConfig, TestingConfig
from backend.app.errors import BusinessError
from backend.app.extensions import cache, cors, csrf, db, login_manager, migrate
from backend.app.utils.api_response import api_response

# 内部人员网页端的构建产物目录（backend/app/ 上两级 = 项目根/web-staff/dist）
# 注意：这里只管 web-staff 这一个前端；两个小程序端（mp-staff / mp-customer）
# 由微信客户端直接访问 API，不经过本函数托管
FRONTEND_DIST = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', '..', 'web-staff', 'dist'
)


def register_frontend_routes(app):
    """生产环境托管 Vue 构建产物：/ 和所有非接口路径都返回 index.html"""
    @app.route('/')
    def serve_index():
        return send_from_directory(FRONTEND_DIST, 'index.html')

    @app.route('/<path:path>')
    def serve_spa(path):
        # /api/* 不属于前端路由，返回 JSON 404（接口路径拼错时不返回 HTML）
        if path.startswith('api/'):
            return jsonify(api_response(success=False, message='资源不存在')), 404
        # 真实文件（如 /assets/*.js）直接返回；其余路径交给前端路由
        file_path = os.path.join(FRONTEND_DIST, path)
        if os.path.isfile(file_path):
            return send_from_directory(FRONTEND_DIST, path)
        return send_from_directory(FRONTEND_DIST, 'index.html')


def create_app(config_name=None):
    # ========== 第1步：创建Flask实例 ==========
    app = Flask(__name__)

    # ========== 第2步：加载配置 ==========
    # 作用是把不同环境的配置应用到Flask应用
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')

    config_map = {
        'development': DevelopmentConfig,
        'production': ProductionConfig,
        'testing': TestingConfig
    }

    app.config.from_object(config_map.get(config_name, DevelopmentConfig))

    # ========== 第3步：初始化扩展 ==========
    # 在extension文件中创建了拓展实例，但是还没有绑定到任何应用上
    # 这里初始化拓展的作用就是把它们都绑定到Flask应用（即这里的app），让拓展知道当前使用的是哪个应用
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    cache.init_app(app)
    cors.init_app(
        app,
        # 只对 /api/* 开放跨域：开发时允许 Vite dev server（5173）跨域调用
        # 生产环境同域托管前端时该配置不生效
        resources={r"/api/*": {"origins": app.config.get('FRONTEND_ORIGINS', [])}},
        supports_credentials=True,  # 允许携带 session cookie
    )
    csrf.init_app(app)


    # 托管前端（必须在蓝图之前注册：保证 / 返回 index.html，/api/* 和 /index 仍走接口）
    register_frontend_routes(app)

    # ========== 第4步：注册蓝图（路由） ==========
    register_blueprints(app)

    # ========== 第5步：注册错误处理器 ==========
    register_error_handlers(app)

    # ========== 第6步：注册上下文处理器 ==========
    register_context_processors(app)

    # ========== 第7步：配置日志 ==========
    configure_logging(app)

    # ========== 第8步：CSRF Token 写入 Cookie ==========
    @app.after_request
    def set_csrf_cookie(response):
        # 机制说明（Flask-WTF 的 CSRF 流程）：
        # - generate_csrf() 返回 signed token，同时把 raw token 存进 session['csrf_token']（校验用）
        # - 校验时：从请求头 X-CSRFToken 验签取出 raw token，与 session 里的 raw 比较
        # - 所以 cookie 里必须是 signed token，不能直接读 session['csrf_token']（那是 raw）
        token = session.get('csrf_token_signed')
        if not token:
            token = generate_csrf()
            session['csrf_token_signed'] = token  # 缓存 signed，避免每次响应换新 token 导致并发请求校验失败
        response.set_cookie('csrf_token', token, samesite='Lax')
        return response

    return app



def register_blueprints(app):
    """注册所有蓝图（flask-smorest 声明式：schema 同时用于校验和 OpenAPI 文档）"""
    from flask_smorest import Api

    from .api import audit, auth, main, stores, users

    # flask-smorest 配置：OpenAPI 3 文档 JSON 挂在 /api/docs/openapi.json
    app.config.setdefault('API_TITLE', f"{app.config.get('APP_NAME', 'Flask API')} API")
    app.config.setdefault('API_VERSION', '1.0.0')
    app.config.setdefault('OPENAPI_VERSION', '3.0.3')
    app.config.setdefault('OPENAPI_URL_PREFIX', '/api/docs')

    api = Api(app, spec_kwargs={
        'info': {
            'description': (
                '本模板的接口文档由 flask-smorest 从路由装饰器和 schema **自动生成**'
                '（非手写注释），接口真实结构即文档，不存在过期问题。\n\n'
                '**统一响应信封**：所有接口返回 {success, message, data, timestamp}。\n\n'
                '**错误状态码约定**：400 业务冲突 · 401 未登录/密码错误 · '
                '403 无管理员权限 · 404 资源不存在 · 422 参数校验失败。\n\n'
                '**认证**：登录成功后种 session cookie；Swagger UI 与后端同源，'
                'Try it out 前请先在一个页面完成登录（cookie 自动携带）。\n\n'
                '**CSRF**：写请求（POST/PUT/DELETE）需带 X-CSRFToken 头'
                '（值 = 浏览器 cookie 中 csrf_token）。真实前端由拦截器自动附加；'
                '在本页 Try it out 写接口时，可在 Authorize 里手动填入。'
            ),
        },
        'components': {
            'securitySchemes': {
                'X-CSRFToken': {
                    'type': 'apiKey',
                    'in': 'header',
                    'name': 'X-CSRFToken',
                    'description': '写请求（POST/PUT/DELETE）需要；GET 不需要。'
                                   '值 = 浏览器 cookie 里 csrf_token 的内容。',
                },
            },
        },
    })
    api.register_blueprint(auth.bp)   # /api/auth, /api/auth/logout
    api.register_blueprint(main.bp)   # /index, /health
    api.register_blueprint(users.bp)  # /api/users
    api.register_blueprint(audit.bp)  # /api/audit
    api.register_blueprint(stores.bp)  # /api/stores

    # Swagger UI 页面（依赖已注册的路由，必须放最后）
    register_api_docs(app)


def register_api_docs(app):
    """挂载 Swagger UI 页面（/apidocs/）

    flask-smorest 只负责生成 OpenAPI 3 的 JSON（/api/docs/openapi.json），
    页面渲染交给 flask-swagger-ui（自带静态资源，离线可用）。
    """
    if app.testing or not app.config.get('ENABLE_API_DOCS', True):
        return

    from flask_swagger_ui import get_swaggerui_blueprint

    app.register_blueprint(get_swaggerui_blueprint(
        '/apidocs',                    # UI 页面地址挂在哪个路径
        '/api/docs/openapi.json',      # 它要去哪个地址拉数据
        config={'app_name': f"{app.config.get('APP_NAME', '')} 接口文档"},
        # 页面顶栏标题
    ))


def register_error_handlers(app):
    """注册全局错误处理器"""
    # 作用是捕获应用中发生的异常，返回友好的错误页面或JSON
    @app.errorhandler(404)
    def not_found(error):
        return jsonify(api_response(success=False, message='资源不存在')), 404

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify(api_response(success=False, message='权限不足')), 403

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        # 回滚当前数据库事务，撤销之前未提交的所有操作
        # 但它只能捕获未被捕获的异常，也就是没有抛出ValueError的异常
        # 所以Service层需要有自己的rollback
        app.logger.error(f'500错误: {error}')
        # 报500的错需要记录日志是因为这个是代码有bug，需要开发者排查
        # 而其他的如404是用户访问了不存在的页面，403是用户权限不足，都不是代码问题
        return jsonify(api_response(success=False, message='服务器内部错误')), 500

    @app.errorhandler(BusinessError)
    def handle_business_error(e):
        return jsonify(api_response(success=False, message=e.message)), e.status_code

    def flatten_errors(errors, prefix=''):
        """把嵌套的字段错误 {json: {username: [...]}} 压平成可读文本，方便直接展示给用户"""
        messages = []
        for key, value in errors.items():
            if isinstance(value, dict):
                messages.extend(flatten_errors(value, f'{prefix}{key}：'))
            elif isinstance(value, list):
                messages.extend(f'{prefix}{key}：{item}' for item in value)
            else:
                messages.append(f'{prefix}{key}：{value}')
        return messages

    @app.errorhandler(422)
    def handle_validation_error(e):
        # flask-smorest 把 schema 校验失败包装成 HTTPException(422)（错误详情挂在 data 上），
        # 这里还原成模板的统一信封，前端拦截器只认 {success, message}
        data = getattr(e, 'data', None) or {}
        errors = data.get('errors') or data.get('messages') or {}
        return jsonify(api_response(success=False, message='；'.join(flatten_errors(errors)))), 422



def register_context_processors(app):
    """注册模板上下文处理器（全局变量）"""
    @app.context_processor
    def inject_global_variables():
        """所有模板都能使用的全局变量"""
        return {
            'app_name': app.config.get('APP_NAME', '餐饮管理系统'),
            'version': '1.0.0',
            'year': 2026
        }


def configure_logging(app):
    """配置日志系统"""
    # 开发环境直接输出到控制台（Flask默认），生产环境写入带轮转的文件
    # 测试环境也不写文件，避免测试运行时产生 logs 目录
    if app.debug or app.testing:
        return

    log_dir = app.config.get('LOG_DIR')
    os.makedirs(log_dir, exist_ok=True)

    # 文件处理器：单文件最大 10MB，保留 5 个备份，自动轮转
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'app.log'),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8',
    )
    file_handler.setLevel(logging.INFO)
    # 设置Handler级别（处理器级别）的日志级别，只记录 INFO 级别及以上的日志
    # DEBUG < INFO < WARNING < ERROR < CRITICAL

    # 日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    # 示例：
    # 2026-01-15 10:30:00,123 - app - ERROR - 500错误: division by zero

    file_handler.setFormatter(formatter)
    # ↑ 把格式应用到处理器

    # 添加到应用
    app.logger.addHandler(file_handler)
    # ↑ 把文件处理器添加到 Flask 的日志系统
    app.logger.setLevel(logging.INFO)
    # 设置Logger级别（应用级别）的日志级别，因为Logger和Handler各有自己的级别，两者都要设置
    app.logger.info('应用启动')
