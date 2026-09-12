from flask import current_app, jsonify
from flask_login import login_required
from flask_smorest import Blueprint

from backend.app.errors import NotFoundError
from backend.app.schemas.dish_schema import (
    DishCreateSchema,
    DishQuerySchema,
    DishUpdateSchema,
)
from backend.app.services import DishService
from backend.app.utils.api_response import api_response
from backend.app.utils.decorators import permission_required

bp = Blueprint('dishes', __name__, url_prefix='/api/dishes')

# 权限分两层：
# - 接口级的权限码决定「能不能干这件事」（menu:view / menu:create / ...）
# - 改价和上下架还有各自的权限码，由 service 层按「改了哪个字段」判断
#   （有 menu:update 不等于能改价格——门店里能改菜名的人不一定该能改价）
# - 菜品基础是全公司数据，写操作还要求「全部」数据范围，店长改的是门店菜品


@bp.get('')
@bp.response(200, description='菜品列表（data.dishes 数组 + data.pagination）')
@login_required
@permission_required('menu:view')
@bp.arguments(DishQuerySchema, location='query')
def index(params):
    """菜品列表（分页 + 按名称搜索 + 按分类筛选）

    列表不带规格组/选项（太重），要看完整结构用详情接口。
    """
    per_page = params.get('per_page') or current_app.config.get('DEFAULT_PAGE_SIZE', 10)

    pagination = DishService.get_paginated_dishes(
        params['page'], per_page, params.get('search') or '', params.get('category_id')
    )

    return jsonify(api_response(
        success=True,
        data={
            'dishes': [dish.to_dict() for dish in pagination.items],
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages,
            }
        }
    ))


@bp.get('/<int:dish_id>')
@bp.response(200, description='菜品详情（含规格组与选项）')
@login_required
@permission_required('menu:view')
def detail(dish_id):
    """菜品详情：带完整规格结构，编辑表单用它回填"""
    dish = DishService.get_dish_by_id(dish_id)
    if not dish:
        raise NotFoundError('菜品不存在')
    return jsonify(api_response(success=True, data=dish.to_dict(with_options=True)))


@bp.post('')
@bp.response(201, description='创建成功，返回新菜品')
@login_required
@permission_required('menu:create')
@bp.arguments(DishCreateSchema, location='json')
def create(data):
    """新增菜品（含规格组/选项，一次性提交）

    分类不存在 → 404；本店范围的角色 → 403（菜品基础是全公司数据）
    """
    dish = DishService.create_dish(data)
    return jsonify(api_response(
        success=True,
        message=f'菜品「{dish.name}」创建成功',
        data=dish.to_dict(with_options=True)
    )), 201


@bp.put('/<int:dish_id>')
@bp.response(200, description='修改成功，返回修改后的菜品')
@login_required
@permission_required('menu:update')
@bp.arguments(DishUpdateSchema, location='json')
def edit(data, dish_id):
    """修改菜品：只传需要改的字段

    - 传 option_groups 就按 id 对齐更新规格结构（不传表示不动）
    - 改 base_price 需要 dish:price:edit，改 status 需要 dish:online
    - 菜品不存在 → 404；分类不存在 → 404
    """
    dish = DishService.update_dish(dish_id, data)
    return jsonify(api_response(
        success=True,
        message=f'菜品「{dish.name}」修改成功',
        data=dish.to_dict(with_options=True)
    ))


@bp.delete('/<int:dish_id>')
@bp.response(200, description='删除成功')
@login_required
@permission_required('menu:delete')
def delete(dish_id):
    """删除菜品

    还在门店菜单里挂着（或已被订单引用）→ 400，请改用「已停售」。
    """
    DishService.delete_dish(dish_id)
    return jsonify(api_response(success=True, message='菜品删除成功'))
