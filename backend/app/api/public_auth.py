"""顾客端登录：手机号 + 验证码

挂在 `/api/public` 下面，因为它服务的还是顾客那头；但**登录本身不能要求登录**，
所以和 `api/public.py` 一样没有 `@login_required`。

和员工那条通道的关系：员工在 `/api/auth/token` 用账号密码换 token，顾客在这里用
手机号 + 验证码换 token。**换出来的东西长得一样（都是 Bearer token），载荷里的
`typ` 不一样**——顾客的 token 拿去调员工接口会被拒，反之亦然。
"""
from flask import jsonify
from flask_smorest import Blueprint

from backend.app.extensions import csrf
from backend.app.schemas.public_member_schema import MemberCodeSchema, MemberLoginSchema
from backend.app.services.member_auth_service import MemberAuthService
from backend.app.utils.api_response import api_response
from backend.app.utils.token import member_token_max_age

bp = Blueprint('public_auth', __name__, url_prefix='/api/public/auth')

# 顾客端不用 cookie，CSRF 防的那个前提不存在（详见 api/public.py 里的说明）
csrf.exempt(bp)


@bp.post('/code')
@bp.response(200, description='验证码已「发送」（演示环境直接回显在 data.code 里）')
@bp.arguments(MemberCodeSchema, location='json')
def send_code(data):
    """发验证码

    **「发送」这一步是模拟的**——真发短信要网关，这里只写日志 + 开发环境回显。

    但发送周围那些限制都是真的，它们才是防刷的关键：同一手机号 60 秒才能重发一次、
    验证码 5 分钟过期、用一次就作废、连输 5 次错就作废。
    """
    return jsonify(api_response(
        success=True,
        message='验证码已发送',
        data=MemberAuthService.send_code(data['mobile']),
    ))


@bp.post('/token')
@bp.response(200, description='登录成功（新手机号会顺手建档），返回 token')
@bp.arguments(MemberLoginSchema, location='json')
def login(data):
    """验证码换 token——**登录即注册**

    手机号在库里没有就顺手建一个 `Member`，不单独做注册页。真实小程序就是这样：
    顾客不会为了点个单先填一遍注册表单。返回里的 `is_new` 让前端决定要不要
    说一句「欢迎新会员」。

    业务错误约定：
      手机号格式不对 → 400 · 没要过验证码 → 400 · 验证码过期/用过/错太多次 → 400
      验证码不对 → 400（会在文案里说还剩几次）· 账号已停用 → 400
    """
    member, token, is_new = MemberAuthService.login(data['mobile'], data['code'])
    return jsonify(api_response(
        success=True,
        message='欢迎回来' if not is_new else '欢迎加入',
        data={
            'token': token,
            'expires_in': member_token_max_age(),
            'is_new': is_new,
            'member': member.to_dict(),
        },
    ))
