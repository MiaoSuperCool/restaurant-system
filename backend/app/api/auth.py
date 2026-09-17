from flask import jsonify
from flask_login import login_required, login_user, logout_user
from flask_smorest import Blueprint

from backend.app.schemas.auth_schema import LoginSchema
from backend.app.services.auth_service import AuthService
from backend.app.utils.api_response import api_response
from backend.app.utils.token import staff_token_max_age

bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@bp.post('')
@bp.response(200, description='登录成功（写入 session cookie），返回当前用户')
@bp.arguments(LoginSchema, location='json')
def login(data):
    """员工登录（内部人员网页端）：成功后服务端写入 session cookie，后续请求浏览器自动携带

    只给员工用。顾客走微信登录，是另一条通道（token），不经过这里。

    业务错误约定（全局统一信封 {success, message}）：
    用户不存在 → 404；密码错误 → 401；账号被禁用 → 400；参数校验失败 → 422
    """
    # 已登录时也照样校验新凭据并切换身份。
    #
    # 模板原来在这里直接返回当前会话，看着像个优化，其实是个坑：
    # 客户端带着新账号密码调过来，拿到 200 以为登录成功了，实际还是原来那个人。
    # 表现出来就是「换账号登录静默失败」——写这个项目的测试时踩了两次。
    staff = AuthService.login(data['username'], data['password'])
    login_user(staff, remember=True)
    return jsonify(api_response(
        success=True,
        message='登录成功',
        data=AuthService.session_payload(staff)
    ))


@bp.post('/token')
@bp.response(200, description='登录成功，返回 token（放进 Authorization: Bearer）')
@bp.arguments(LoginSchema, location='json')
def login_for_token(data):
    """员工登录（小程序端）：换成 token 下发，不发 session cookie

    和上面那个接口是**同一次校验，两种凭据**：账号密码都对，区别只在于
    网页端拿的是 HttpOnly 的 session cookie（浏览器自动带），
    小程序拿的是 token（自己存着、每次放进请求头）。

    小程序没有 cookie 那套机制，也不该有——cookie 是浏览器的东西。
    反过来在浏览器里 session 更安全：HttpOnly 天然挡住 XSS 偷 token。

    `permissions` 和 `data_scope` 一并返回，前端才知道该显示哪些菜单——
    但这**纯粹是体验层**，后端每个接口都会重新判权。
    """
    staff, token = AuthService.login_with_token(data['username'], data['password'])
    return jsonify(api_response(
        success=True,
        message='登录成功',
        data={
            'token': token,
            # 秒数，前端拿它算什么时候该重新登录
            'expires_in': staff_token_max_age(),
            **AuthService.session_payload(staff),
        }
    ))


@bp.post('/logout')
@bp.response(200, description='已退出登录')
@login_required
def logout():
    """退出登录（两个通道共用）

    网页端清 session，小程序端把 `token_version` +1 让旧 token 失效——
    具体怎么处理在 `AuthService.logout` 里，这里不需要分情况。
    """
    AuthService.logout()
    logout_user()
    return jsonify(api_response(
        success=True,
        message='您已退出登录'
    ))
