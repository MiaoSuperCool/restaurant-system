from flask import current_app, jsonify
from flask_login import login_required
from flask_smorest import Blueprint

from backend.app.schemas.query_schema import PageQuerySchema
from backend.app.services.audit_service import AuditService
from backend.app.utils.api_response import api_response
from backend.app.utils.decorators import admin_required

bp = Blueprint('audit', __name__, url_prefix='/api/audit')

@bp.get('')
@bp.response(200, description='日志数组（data.logs）+ 分页信息（data.pagination）')
# 告诉文档"这接口会返回200，大致是什么"，顺带在 UI 上把各状态码列出来
@login_required
@admin_required
@bp.arguments(PageQuerySchema, location='query')
# 请求进来先拿 PageQuerySchema 校验 query字符串，变成干净 dict 作为 params传进函数
def index(params):
    """审计日志列表（分页 + 关键字搜索，仅管理员）

    日志由 services 层在业务操作成功后自动记录（登录/登出/用户增删改），失败也留痕
    """
    per_page = params.get('per_page') or current_app.config.get('DEFAULT_PAGE_SIZE', 10)

    pagination = AuditService.get_paginated_logs(
        params['page'], per_page, params.get('search') or ''
    )

    return jsonify(api_response(
        success=True,
        data={
            'logs': [log.to_dict() for log in pagination.items],
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages,
            }
        }
    ))


@bp.get('/<int:log_id>')
@bp.response(200, description='单条日志（含变更前后 old_value / new_value）')
@login_required
@admin_required
def detail(log_id):
    """审计日志详情（仅管理员）：查看单条日志的完整变更数据"""
    log = AuditService.get_log_by_id(log_id)
    # 不存在的话 service 抛 NotFoundError → 全局返回 404
    return jsonify(api_response(
        success=True,
        data=log.to_dict()
    ))
