"""角色接口

只读：预置角色由 backend/app/rbac.py 定义、`flask seed-rbac` 落地，
改权限矩阵应该改那份代码而不是在界面上点。

不做角色的增删改——等三期「多角色管理」确实需要在界面上配角色时再补，
届时要注意别让老板把「老板」角色改废了。
"""
from flask import jsonify
from flask_login import login_required
from flask_smorest import Blueprint

from backend.app.models import Permission, Role
from backend.app.utils.api_response import api_response
from backend.app.utils.decorators import permission_required

bp = Blueprint('roles', __name__, url_prefix='/api/roles')


@bp.get('')
@bp.response(200, description='角色列表 + 权限目录（一次给全，供权限矩阵页渲染）')
@login_required
@permission_required('staff:manage', 'staff:manage:all')
def index():
    """角色列表（含每个角色有哪些权限码）+ 完整权限目录

    权限目录一起返回是为了让前端能直接渲染「角色 × 权限」矩阵——
    分开两个请求的话，前端还得自己把权限码和中文名对齐，没必要。
    """
    roles = Role.query.order_by(Role.sort_order).all()
    permissions = Permission.query.order_by(Permission.sort_order).all()
    return jsonify(api_response(
        success=True,
        data={
            'roles': [role.to_dict() for role in roles],
            'permissions': [p.to_dict() for p in permissions],
        }
    ))
