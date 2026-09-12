"""接口层的权限装饰器

真正的权限边界在这里（后端），前端的菜单/按钮隐藏只是体验层。
"""
from functools import wraps

from flask_login import current_user

from backend.app.errors import BusinessError
from backend.app.rbac import permission_name


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
