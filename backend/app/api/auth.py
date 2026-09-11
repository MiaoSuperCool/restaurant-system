from flask import jsonify
from flask_login import current_user, login_required, login_user, logout_user
from flask_smorest import Blueprint

from backend.app.schemas.auth_schema import LoginSchema
from backend.app.services.auth_service import AuthService
from backend.app.utils.api_response import api_response

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
    if current_user.is_authenticated:
        return jsonify(api_response(
            success=True,
            message='用户已登陆',
            data={'staff': current_user.to_dict()}
        ))

    staff = AuthService.login(data['username'], data['password'])
    login_user(staff, remember=True)
    return jsonify(api_response(
        success=True,
        message='登录成功',
        data={'staff': staff.to_dict()}
    ))


@bp.post('/logout')
@bp.response(200, description='已退出登录（清除 session）')
@login_required
def logout():
    """退出登录（需要已登录）"""
    AuthService.logout()
    logout_user()
    return jsonify(api_response(
        success=True,
        message='您已退出登录'
    ))
