"""接口层的权限装饰器

真正的权限边界在这里（后端），前端的菜单/按钮隐藏只是体验层。
"""
from functools import wraps

from flask import g
from flask_login import current_user

from backend.app.errors import BusinessError
from backend.app.rbac import permission_name


def member_required(func):
    """要求请求带一个**顾客**的 token；认出来的会员放在 `g.member`

    和员工那条路（`@login_required` + `permission_required`）是**两套**，刻意不共用：

    - 员工走 Flask-Login 的 `current_user`，认出来的是 `Staff`，后面还要判权限码
    - 顾客不进权限体系（设计文档第 3 条），认出来的是 `Member`，
      只有「这条数据是不是你的」这一件事要判

    硬塞进 `current_user` 的话，`permission_required` 会去调一个会员根本没有的
    `has_any_permission`——而且两张表的 id 都是自增的，谁是谁迟早要出事。

    token 里带了 `typ`，所以拿**员工** token 调顾客接口会是 401，反之亦然。
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        from backend.app.services.member_auth_service import MemberAuthService
        from backend.app.utils.token import bearer_token

        token = bearer_token()
        member = MemberAuthService.resolve_token(token) if token else None
        if member is None:
            raise BusinessError('请先登录', status_code=401)

        g.member = member
        return func(*args, **kwargs)
    return wrapper


def permission_required(*codes):
    """要求当前登录员工至少拥有其中一个权限码

    用法（放在 @login_required 内层、@bp.arguments 外层）：
        @permission_required('store:manage')
        @permission_required('staff:manage', 'staff:manage:all')   # 任一即可

    权限码的合法取值见 backend/app/rbac.py 的 PERMISSIONS。

    注意：这里只管「能不能干这件事」。**能碰哪些数据**（本店 / 全部）
    是另一回事，由 service 层按 current_user.accessible_store_ids() 过滤——
    同一个 dish:price:edit，店长只能改本店的，运营主管能改全公司。
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                raise BusinessError('请先登录', status_code=401)
            if not current_user.has_any_permission(*codes):
                names = '」或「'.join(permission_name(code) for code in codes)
                raise BusinessError(f'没有「{names}」权限', status_code=403)
            return func(*args, **kwargs)
        return wrapper
    return decorator
