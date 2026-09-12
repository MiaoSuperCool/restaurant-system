"""角色接口

目前只有只读列表：员工表单要给员工分配角色，得先把可选角色拉出来。

不做角色的增删改——预置角色由 backend/app/rbac.py 定义、`flask seed-rbac` 落地，
改权限矩阵应该改那份代码而不是在界面上点。等三期「多角色管理」确实需要在界面上
配角色时，再补写接口，届时要注意别让老板把「老板」角色改废了。
"""
from flask import jsonify
from flask_login import login_required
from flask_smorest import Blueprint

from backend.app.models import Role
from backend.app.utils.api_response import api_response
from backend.app.utils.decorators import permission_required

bp = Blueprint('roles', __name__, url_prefix='/api/roles')


@bp.get('')
@bp.response(200, description='角色列表（含权限码与数据范围）')
@login_required
@permission_required('staff:manage', 'staff:manage:all')
def index():
    """角色列表：员工管理页分配角色时用

    带 permission_codes 是为了让前端能直接展示「这个角色有哪些权限」，
    不用再拉一次权限目录。
    """
    roles = Role.query.order_by(Role.sort_order).all()
    return jsonify(api_response(
        success=True,
        data={'roles': [role.to_dict() for role in roles]}
    ))
