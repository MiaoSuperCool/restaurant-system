from flask import current_app, jsonify
from flask_login import current_user, login_required
from flask_smorest import Blueprint

from backend.app.schemas.query_schema import PageQuerySchema
from backend.app.schemas.store_schema import StoreCreateSchema, StoreUpdateSchema
from backend.app.services import StoreService
from backend.app.utils.api_response import api_response
from backend.app.utils.decorators import permission_required

bp = Blueprint('stores', __name__, url_prefix='/api/stores')


@bp.get('')
@bp.response(200, description='门店列表（data.stores 数组 + data.pagination 分页信息）')
@login_required
@permission_required('store:view')
@bp.arguments(PageQuerySchema, location='query')
def index(params):
    """门店列表（分页 + 关键字搜索）

    搜索命中 编码 / 名称 / 地址。
    数据范围：店长等「本店」角色只返回自己归属的门店，运营主管/财务/老板返回全部。
    """
    per_page = params.get('per_page') or current_app.config.get('DEFAULT_PAGE_SIZE', 10)

    pagination = StoreService.get_paginated_stores(
        params['page'], per_page, params.get('search') or '',
        store_ids=current_user.accessible_store_ids(),
    )

    return jsonify(api_response(
        success=True,
        data={
            'stores': [store.to_dict() for store in pagination.items],
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages
            }
        }
    ))


@bp.get('/options')
@bp.response(200, description='门店下拉选项（不分页，供各处表单选择归属门店）')
@login_required
@permission_required('store:view')
def options():
    """门店下拉选项：只返回 id/编码/名称/营业状态，供表单选择器使用

    同样受数据范围限制——店长在表单里只能选到自己那家店。
    """
    stores = StoreService.get_all_stores(store_ids=current_user.accessible_store_ids())
    return jsonify(api_response(
        success=True,
        data={
            'stores': [
                {
                    'id': store.id,
                    'code': store.code,
                    'name': store.name,
                    'business_status': store.business_status,
                    'business_status_label': store.STATUS_LABELS.get(
                        store.business_status, store.business_status
                    ),
                }
                for store in stores
            ]
        }
    ))


@bp.post('')
@bp.response(201, description='创建成功，返回新门店')
@login_required
@permission_required('store:manage')
@bp.arguments(StoreCreateSchema, location='json')
def create(data):
    """创建门店（store:manage——按设计文档是老板专属）

    门店编码或名称已存在 → 400（业务冲突，message 说明具体字段）
    """
    store = StoreService.create_store(data)
    return jsonify(api_response(
        success=True,
        message=f'门店「{store.name}」创建成功',
        data=store.to_dict()
    )), 201


@bp.put('/<int:store_id>')
@bp.response(200, description='修改成功，返回修改后的门店')
@login_required
@permission_required('store:manage')
@bp.arguments(StoreUpdateSchema, location='json')
def edit(data, store_id):
    """修改门店（只传需要改的字段）

    门店不存在 → 404；编码/名称与他人冲突 → 400；超出数据范围 → 403
    """
    store = StoreService.update_store(store_id, data)
    return jsonify(api_response(
        success=True,
        message=f'门店「{store.name}」修改成功',
        data=store.to_dict()
    ))


@bp.delete('/<int:store_id>')
@bp.response(200, description='删除成功')
@login_required
@permission_required('store:manage')
def delete(store_id):
    """删除门店

    门店不存在 → 404；超出数据范围 → 403。
    门店一旦有订单/员工等业务数据就删不掉（会返回 400 并说明有多少条），
    这时该走「已停业」（business_status=closed）而不是删记录。
    """
    StoreService.delete_store(store_id)
    return jsonify(api_response(
        success=True,
        message='门店删除成功'
    ))
