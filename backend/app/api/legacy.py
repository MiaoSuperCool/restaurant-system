"""老系统共存接口：ID 映射 + 同步记录 + 对账

**权限只有一个 `sync:view`**（财务和老板有），不拆读写的码。这一块的动作都不会
动到钱、也不会发出去东西：对账是个只读计算、重跑只是把结论覆盖一遍，
绑映射只是修一条对应关系。真出现有破坏性的动作（推数据给 ERP、
按对账结果自动改账）再单独给码——券那边分 `manage`/`issue` 是因为发出去就是成本。

迁移本身**没有接口**：它是 `python manage.py import-legacy`，
一次性、要能在没有登录用户的情况下跑（见那条命令的说明）。
"""
from flask import current_app, jsonify
from flask_login import login_required
from flask_smorest import Blueprint

from backend.app.schemas.legacy_schema import (
    LegacyMapCreateSchema,
    LegacyMapQuerySchema,
    LegacyResolveQuerySchema,
    ReconciliationQuerySchema,
    ReconciliationRunSchema,
    SyncRecordQuerySchema,
)
from backend.app.services import LegacyService, ReconciliationService
from backend.app.utils.api_response import api_response
from backend.app.utils.decorators import permission_required

bp = Blueprint('legacy', __name__, url_prefix='/api/legacy')

SYNC_VIEW = 'sync:view'


def _pagination(page_obj):
    return {
        'page': page_obj.page,
        'per_page': page_obj.per_page,
        'total': page_obj.total,
        'pages': page_obj.pages,
    }


def _per_page(params):
    return params.get('per_page') or current_app.config.get('DEFAULT_PAGE_SIZE', 10)


# ---------- ID 映射 ----------

@bp.get('/maps')
@bp.response(200, description='映射列表（data.maps + data.pagination）')
@login_required
@permission_required(SYNC_VIEW)
@bp.arguments(LegacyMapQuerySchema, location='query')
def list_maps(params):
    pagination = LegacyService.get_maps(
        page=params['page'], per_page=_per_page(params),
        target_type=params.get('target_type'), search=params.get('search'),
    )
    return jsonify(api_response(
        success=True,
        data={'maps': [m.to_dict() for m in pagination.items],
              'pagination': _pagination(pagination)},
    ))


@bp.get('/maps/resolve')
@bp.response(200, description='按老号查新对象；没迁过时 data.member 为 null')
@login_required
@permission_required(SYNC_VIEW)
@bp.arguments(LegacyResolveQuerySchema, location='query')
def resolve_map(params):
    """客服那个动作：拿老会员号查这是谁

    **查不到不是 404**——「这个号没迁过」是个正常的查询结果，
    返回 404 的话前端得把它和「接口挂了」区分开，没必要。
    """
    target = LegacyService.resolve(params['target_type'], params['legacy_id'])
    return jsonify(api_response(
        success=True,
        data={'found': target is not None,
              'target_type': params['target_type'],
              'legacy_id': params['legacy_id'],
              # 会员和储值账户都有 to_dict，储值那条会带上 member_id
              'target': target.to_dict() if target else None},
    ))


@bp.post('/maps')
@bp.response(201, description='记好了，返回这条映射')
@login_required
@permission_required(SYNC_VIEW)
@bp.arguments(LegacyMapCreateSchema, location='json')
def create_map(data):
    """手工补一条映射（迁移时漏掉的个别人）"""
    mapping = LegacyService.bind(
        data['target_type'], data['target_id'], data['legacy_id'],
        remark=data.get('remark', ''),
    )
    return jsonify(api_response(success=True, data=mapping.to_dict())), 201


@bp.delete('/maps/<int:map_id>')
@bp.response(200, description='已删除')
@login_required
@permission_required(SYNC_VIEW)
def delete_map(map_id):
    """删映射——**只在录错的时候用**，删之前会在审计里留一份"""
    LegacyService.unbind(map_id)
    return jsonify(api_response(success=True, message='已删除'))


# ---------- 同步记录 ----------

@bp.get('/sync-records')
@bp.response(200, description='同步记录（data.records + data.summary + data.pagination）')
@login_required
@permission_required(SYNC_VIEW)
@bp.arguments(SyncRecordQuerySchema, location='query')
def list_sync_records(params):
    pagination = LegacyService.get_sync_records(
        page=params['page'], per_page=_per_page(params),
        direction=params.get('direction'), target=params.get('target'),
        category=params.get('category'), status=params.get('status'),
    )
    return jsonify(api_response(
        success=True,
        data={'records': [r.to_dict() for r in pagination.items],
              # **汇总不跟着筛选走**，永远是全量：它回答的是「一共推了多少、
              # 几条没过」——这一个数字。跟着筛的话，筛「失败」时它会显示
              # 「成功 0、失败 3」，等于把筛选条件又念了一遍，没有信息
              'summary': LegacyService.sync_summary(),
              'pagination': _pagination(pagination)},
    ))


# ---------- 对账 ----------

@bp.get('/reconciliations')
@bp.response(200, description='对账记录（data.records + data.pagination）')
@login_required
@permission_required(SYNC_VIEW)
@bp.arguments(ReconciliationQuerySchema, location='query')
def list_reconciliations(params):
    pagination = ReconciliationService.get_records(
        page=params['page'], per_page=_per_page(params),
        category=params.get('category'), status=params.get('status'),
        store_id=params.get('store_id'), biz_date=params.get('biz_date'),
    )
    return jsonify(api_response(
        success=True,
        data={'records': [r.to_dict() for r in pagination.items],
              'pagination': _pagination(pagination)},
    ))


@bp.post('/reconciliations/run')
@bp.response(200, description='跑完了，返回这条对账记录（含差异明细）')
@login_required
@permission_required(SYNC_VIEW)
@bp.arguments(ReconciliationRunSchema, location='json')
def run_reconciliation(data):
    """跑一次对账

    页面上手工点一下是有的（查「刚才那笔到底记上没」），但**日结的常态是
    定时任务在跑**——`python manage.py reconcile`，那条路没有登录用户，
    操作人会记成「系统」。
    """
    store_id = data.get('store_id')
    if store_id is not None:
        # 先确认门店存在：不确认的话，门店 id 写错会算出「0 对 0、对得上」，
        # 比报错难查得多
        ReconciliationService.resolve_store(store_id)

    record = ReconciliationService.run(
        data['biz_date'], data['category'], store_id=store_id,
    )
    return jsonify(api_response(success=True, data=record.to_dict()))
