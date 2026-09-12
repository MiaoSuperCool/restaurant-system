from flask import current_app, jsonify
from flask_login import login_required
from flask_smorest import Blueprint

from backend.app.schemas.category_schema import CategoryCreateSchema, CategoryUpdateSchema
from backend.app.schemas.query_schema import PageQuerySchema
from backend.app.services import CategoryService
from backend.app.utils.api_response import api_response
from backend.app.utils.decorators import permission_required

bp = Blueprint('categories', __name__, url_prefix='/api/categories')


@bp.get('')
@bp.response(200, description='分类列表（data.categories 数组 + data.pagination）')
@login_required
@permission_required('menu:view')
@bp.arguments(PageQuerySchema, location='query')
def index(params):
    """菜品分类列表（分页 + 按名称搜索）

    分类里的 store_ids 表示「适用哪些门店」，空数组 = 全公司通用。
    """
    per_page = params.get('per_page') or current_app.config.get('DEFAULT_PAGE_SIZE', 10)

    pagination = CategoryService.get_paginated_categories(
        params['page'], per_page, params.get('search') or ''
    )

    return jsonify(api_response(
        success=True,
        data={
            'categories': [category.to_dict() for category in pagination.items],
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages,
            }
        }
    ))


@bp.get('/options')
@bp.response(200, description='分类下拉选项（不分页，供菜品表单选择分类）')
@login_required
@permission_required('menu:view')
def options():
    """分类下拉选项：只返回 id/名称/图标，供表单选择器使用"""
    return jsonify(api_response(
        success=True,
        data={
            'categories': [
                {'id': category.id, 'name': category.name, 'icon': category.icon}
                for category in CategoryService.get_all_categories()
            ]
        }
    ))


@bp.post('')
@bp.response(201, description='创建成功，返回新分类')
@login_required
@permission_required('menu:create')
@bp.arguments(CategoryCreateSchema, location='json')
def create(data):
    """创建分类

    分类名已存在 → 400；store_ids 里有不存在的门店 → 404
    """
    category = CategoryService.create_category(data)
    return jsonify(api_response(
        success=True,
        message=f'分类「{category.name}」创建成功',
        data=category.to_dict()
    )), 201


@bp.put('/<int:category_id>')
@bp.response(200, description='修改成功，返回修改后的分类')
@login_required
@permission_required('menu:update')
@bp.arguments(CategoryUpdateSchema, location='json')
def edit(data, category_id):
    """修改分类：只传需要改的字段

    传 store_ids 就整体替换适用范围（传空数组 = 改回全公司通用）。
    """
    category = CategoryService.update_category(category_id, data)
    return jsonify(api_response(
        success=True,
        message=f'分类「{category.name}」修改成功',
        data=category.to_dict()
    ))


@bp.delete('/<int:category_id>')
@bp.response(200, description='删除成功')
@login_required
@permission_required('menu:delete')
def delete(category_id):
    """删除分类

    分类下面还有菜品 → 400（会说明有多少道菜），请先把菜品挪到别的分类。
    """
    CategoryService.delete_category(category_id)
    return jsonify(api_response(success=True, message='分类删除成功'))
