"""团购券核销

路径放在 /api 下而不是挂在 orders 蓝图里：核销记录本身是一个独立的资源，
月底要拿去和美团/抖音对账，不属于「订单管理」那一摊。
"""
from flask import current_app, jsonify
from flask_login import current_user, login_required
from flask_smorest import Blueprint

from backend.app.schemas.groupon_schema import GrouponVerifySchema
from backend.app.schemas.query_schema import PageQuerySchema
from backend.app.services import GrouponService
from backend.app.utils.api_response import api_response
from backend.app.utils.decorators import permission_required

bp = Blueprint('groupon', __name__, url_prefix='/api')


@bp.post('/orders/<int:order_id>/vouchers')
@bp.response(201, description='核销成功，返回核销记录和更新后的订单')
@login_required
@permission_required('coupon:verify')
@bp.arguments(GrouponVerifySchema, location='json')
def verify(data, order_id):
    """核销一张团购券（coupon:verify）

    核销会做两件事：记一条核销记录（给对账用）+ 记一笔团购券收款。

    **同一张券码不能核销两次**——先查一次给友好提示，真正的保证是
    groupon_voucher.code 的唯一约束（两个收银员同时核销时前者挡不住）。

    券码已核销 → 400；券面额超过未付部分 → 400（券只能抵扣，不找零）；
    订单不存在 → 404；超出数据范围 → 403。
    """
    voucher, order = GrouponService.verify(order_id, data)
    return jsonify(api_response(
        success=True,
        message=f'已核销 {voucher.PLATFORM_LABELS.get(voucher.platform)} 券 '
                f'¥{voucher.amount:.2f}',
        data={'voucher': voucher.to_dict(), 'order': order.to_dict()}
    )), 201


@bp.get('/groupon-vouchers')
@bp.response(200, description='核销记录列表（data.vouchers + data.pagination）')
@login_required
@permission_required('coupon:verify', 'finance:view')
@bp.arguments(PageQuerySchema, location='query')
def index(params):
    """核销记录列表（分页 + 按券码/订单号搜索）

    给财务对账用：月底按平台拉一段时间内核销了多少张、多少钱。
    数据范围：店长只看得到本店的核销记录。
    """
    per_page = params.get('per_page') or current_app.config.get('DEFAULT_PAGE_SIZE', 10)

    pagination = GrouponService.get_paginated_vouchers(
        params['page'], per_page, params.get('search') or '',
        store_ids=current_user.accessible_store_ids(),
    )

    return jsonify(api_response(
        success=True,
        data={
            'vouchers': [voucher.to_dict() for voucher in pagination.items],
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages,
            }
        }
    ))
