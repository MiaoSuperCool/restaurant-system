from flask import current_app, jsonify
from flask_login import current_user, login_required
from flask_smorest import Blueprint

from backend.app.schemas.query_schema import PageQuerySchema
from backend.app.schemas.staff_schema import StaffCreateSchema, StaffUpdateSchema
from backend.app.services import StaffService
from backend.app.utils.api_response import api_response
from backend.app.utils.decorators import permission_required

bp = Blueprint('staff', __name__, url_prefix='/api/staff')

# 权限：staff:manage = 本店员工（店长），staff:manage:all = 全公司含店长/总部账号（老板）。
# 两者都通过才有必要再谈数据范围，范围由 service 层的 assert_can_manage 强制。


@bp.get('')
@bp.response(200, description='员工列表（data.staff 数组 + data.pagination 分页信息）')
@login_required
@permission_required('staff:manage', 'staff:manage:all')
@bp.arguments(PageQuerySchema, location='query')
def index(params):
    """员工列表（分页 + 关键字搜索）

    搜索命中 用户名 / 姓名 / 邮箱 / 手机号。
    数据范围：「本店」角色只看到本店员工，看不到总部账号。
    """
    per_page = params.get('per_page') or current_app.config.get('DEFAULT_PAGE_SIZE', 10)

    pagination = StaffService.get_paginated_staff(
        params['page'], per_page, params.get('search') or '',
        store_ids=current_user.accessible_store_ids(),
    )

    return jsonify(api_response(
        success=True,
        data={
            'staff': [member.to_dict() for member in pagination.items],
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages
            }
        }
    ))


@bp.post('')
@bp.response(201, description='创建成功，返回新员工')
@login_required
@permission_required('staff:manage', 'staff:manage:all')
@bp.arguments(StaffCreateSchema, location='json')
def create(data):
    """创建员工

    用户名/邮箱/手机号已存在 → 400；归属门店或角色不存在 → 404；超出数据范围 → 403
    """
    staff = StaffService.create_staff(data)
    return jsonify(api_response(
        success=True,
        message=f'员工 {staff.real_name} 创建成功',
        data=staff.to_dict()
    )), 201


@bp.put('/<int:staff_id>')
@bp.response(200, description='修改成功，返回修改后的员工')
@login_required
@permission_required('staff:manage', 'staff:manage:all')
@bp.arguments(StaffUpdateSchema, location='json')
def edit(data, staff_id):
    """修改员工：只传需要改的字段

    员工不存在 → 404；用户名/邮箱/手机号与他人冲突 → 400；超出数据范围 → 403。
    传 role_ids 就整体替换该员工的角色（不传表示不动）。
    """
    staff = StaffService.update_staff(staff_id, data)
    return jsonify(api_response(
        success=True,
        message=f'员工 {staff.real_name} 修改成功',
        data=staff.to_dict()
    ))


@bp.delete('/<int:staff_id>')
@bp.response(200, description='删除成功')
@login_required
@permission_required('staff:manage', 'staff:manage:all')
def delete(staff_id):
    """删除员工（不能删自己）

    该员工的历史审计日志保留（operator_id 置空，见 audit_log 的 SET NULL 外键），
    角色关联行由 staff_role 的 CASCADE 自动清掉。
    """
    StaffService.delete_staff(staff_id)
    return jsonify(api_response(
        success=True,
        message='员工删除成功'
    ))
