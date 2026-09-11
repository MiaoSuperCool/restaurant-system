from flask import current_app, jsonify
from flask_login import login_required
from flask_smorest import Blueprint

from backend.app.schemas.query_schema import PageQuerySchema
from backend.app.schemas.staff_schema import StaffCreateSchema, StaffUpdateSchema
from backend.app.services import StaffService
from backend.app.utils.api_response import api_response
from backend.app.utils.decorators import admin_required

bp = Blueprint('staff', __name__, url_prefix='/api/staff')

# 权限说明（临时）：员工账号管理目前用 admin_required 兜底。
# 权限码体系落地后换成 @permission_required('staff:manage')（本店员工）与
# 'staff:manage:all'（店长/总部账号）——按设计文档，店长只能管本店的收银/服务/后厨/兼职。


@bp.get('')
@bp.response(200, description='员工列表（data.staff 数组 + data.pagination 分页信息）')
@login_required
@admin_required
@bp.arguments(PageQuerySchema, location='query')
def index(params):
    """员工列表（分页 + 关键字搜索，仅管理员）

    未登录 → 401；非管理员访问 → 403（前端隐藏菜单只是体验层，后端才是权限边界）
    """
    per_page = params.get('per_page') or current_app.config.get('DEFAULT_PAGE_SIZE', 10)

    pagination = StaffService.get_paginated_staff(
        params['page'], per_page, params.get('search') or ''
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
@admin_required
@bp.arguments(StaffCreateSchema, location='json')
def create(data):
    """创建员工（仅管理员）

    用户名/邮箱/手机号已存在 → 400；归属门店不存在 → 404
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
@admin_required
@bp.arguments(StaffUpdateSchema, location='json')
def edit(data, staff_id):
    """修改员工（仅管理员）：只传需要改的字段

    员工不存在 → 404；用户名/邮箱/手机号与他人冲突 → 400
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
@admin_required
def delete(staff_id):
    """删除员工（仅管理员，不能删自己）

    该员工的历史审计日志保留（operator_id 置空，见 audit_log 的 SET NULL 外键）
    """
    StaffService.delete_staff(staff_id)
    return jsonify(api_response(
        success=True,
        message='员工删除成功'
    ))
