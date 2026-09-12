"""门店菜单：某家店卖哪些菜、卖多少钱、一天限几份

路径挂在门店下面（/api/stores/<id>/menu），因为它就是门店的子资源。
和 api/stores.py 用同一个 url_prefix 是可以的——Flask 只要求端点名唯一。
"""
from flask import jsonify
from flask_login import login_required
from flask_smorest import Blueprint

from backend.app.schemas.store_dish_schema import StoreDishUpdateSchema, StoreMenuQuerySchema
from backend.app.services import StoreDishService
from backend.app.utils.api_response import api_response
from backend.app.utils.decorators import permission_required

bp = Blueprint('store_menu', __name__, url_prefix='/api/stores')

# 数据范围在这里特别要紧：店长只能看和改自己店的菜单。
# 权限码（menu:view / menu:update）管「能不能碰菜单」，
# 范围由 service 层的 assert_in_scope 强制。


@bp.get('/<int:store_id>/menu')
@bp.response(200, description='门店菜单（菜品基础 + 本店覆盖，不分页）')
@login_required
@permission_required('menu:view')
@bp.arguments(StoreMenuQuerySchema, location='query')
def menu(params, store_id):
    """某门店的菜单

    返回的每一行是「菜品基础 + 本店覆盖」合并后的结果：
    price 是本店实际售价，is_available 是本店是否上架。
    没做过特殊设置的菜用默认值（基础价、可售、不限量）。

    只返回「在售」的菜品——已停售的全公司都不卖。
    """
    rows = StoreDishService.get_menu(
        store_id, params.get('category_id'), params.get('search')
    )
    return jsonify(api_response(success=True, data={'dishes': rows}))


@bp.put('/<int:store_id>/dishes/<int:dish_id>')
@bp.response(200, description='设置成功，返回该门店这道菜的最新设置')
@login_required
@permission_required('menu:update')
@bp.arguments(StoreDishUpdateSchema, location='json')
def set_dish(data, store_id, dish_id):
    """设置某门店对某道菜的覆盖（没有记录就建一条）

    - price 传 null = 取消本店覆盖、改回菜品基础价
    - daily_limit 传 null = 不限量
    - 改 price 另需 dish:price:edit，改 is_available 另需 dish:online
    - 门店或菜品不存在 → 404；超出数据范围 → 403
    """
    override = StoreDishService.upsert_override(store_id, dish_id, data)
    if override is None:
        # 一个字段都没传：本来就等于「用默认值」，不必建空记录
        return jsonify(api_response(
            success=True,
            message='没有要改的字段',
            data=None,
        ))
    return jsonify(api_response(
        success=True,
        message='设置成功',
        data=override.to_dict(),
    ))


@bp.delete('/<int:store_id>/dishes/<int:dish_id>')
@bp.response(200, description='已恢复默认')
@login_required
@permission_required('menu:update')
def reset_dish(store_id, dish_id):
    """清除本店对某道菜的覆盖，恢复成「用基础价、可售、不限量」

    删的是覆盖配置，不是菜品——菜品本身还在，只是这家店不再特殊对待它。
    """
    StoreDishService.delete_override(store_id, dish_id)
    return jsonify(api_response(success=True, message='已恢复默认设置'))
