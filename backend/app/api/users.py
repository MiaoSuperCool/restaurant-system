from flask import current_app, jsonify
from flask_login import login_required
from flask_smorest import Blueprint

from backend.app.schemas.query_schema import PageQuerySchema
from backend.app.schemas.user_schema import UserCreateSchema, UserUpdateSchema
from backend.app.services.user_service import UserService
from backend.app.utils.api_response import api_response
from backend.app.utils.decorators import admin_required

bp = Blueprint('users', __name__, url_prefix='/api/users')

@bp.get('')
@bp.response(200, description='用户列表（data.users 数组 + data.pagination 分页信息）')
@login_required
@admin_required
@bp.arguments(PageQuerySchema, location='query')
def index(params):
    """用户列表（分页 + 关键字搜索，仅管理员）

    未登录 → 401；普通用户访问 → 403（前端隐藏菜单只是体验层，后端才是权限边界）
    """
    per_page = params.get('per_page') or current_app.config.get('DEFAULT_PAGE_SIZE', 10)

    pagination = UserService.get_paginated_users(
        params['page'], per_page, params.get('search') or ''
    )

    return jsonify(api_response(
        success=True,
        data={
            'users': [user.to_dict() for user in pagination.items],
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages
            }
        }
    ))


@bp.post('')
@bp.response(201, description='创建成功，返回新用户')
@login_required
@admin_required
@bp.arguments(UserCreateSchema, location='json')
def create(data):
    """创建用户（仅管理员）

    用户名/邮箱/手机号已存在 → 400（业务冲突，message 说明具体字段）
    """
    user = UserService.create_user(data)
    return jsonify(api_response(
        success=True,
        message=f'用户{user.username}创建成功',
        data=user.to_dict()
    )), 201


@bp.put('/<int:user_id>')
@bp.response(200, description='修改成功，返回修改后的用户')
@login_required
@admin_required
@bp.arguments(UserUpdateSchema, location='json')
def edit(data, user_id):
    """修改用户（仅管理员）：只传需要改的字段

    用户不存在 → 404；用户名/邮箱/手机号与他人冲突 → 400
    """
    user = UserService.update_user(user_id, data)
    return jsonify(api_response(
        success=True,
        message=f'用户{user.username}修改成功',
        data=user.to_dict()
    ))


@bp.delete('/<int:user_id>')
@bp.response(200, description='删除成功')
@login_required
@admin_required
def delete(user_id):
    """删除用户（仅管理员，不能删除自己）

    该用户的历史审计日志保留（user_id 置空，见 audit_log 的 SET NULL 外键）
    """
    UserService.delete_user(user_id)
    return jsonify(api_response(
        success=True,
        message='用户删除成功'
    ))
