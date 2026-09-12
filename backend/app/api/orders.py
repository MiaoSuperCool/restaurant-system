from flask import current_app, jsonify
from flask_login import current_user, login_required
from flask_smorest import Blueprint

from backend.app.schemas.order_schema import (
    OrderCreateSchema,
    OrderQuerySchema,
    PaymentCreateSchema,
)
from backend.app.services import OrderService
from backend.app.utils.api_response import api_response
from backend.app.utils.decorators import permission_required

bp = Blueprint('orders', __name__, url_prefix='/api/orders')


@bp.get('')
@bp.response(200, description='订单列表（data.orders 数组 + data.pagination）')
@login_required
@permission_required('order:view')
@bp.arguments(OrderQuerySchema, location='query')
def index(params):
    """订单列表（分页 + 按单号搜索 + 按门店/状态筛选）

    数据范围：店长只看得到本店订单，运营主管/财务/老板看全部。
    """
    per_page = params.get('per_page') or current_app.config.get('DEFAULT_PAGE_SIZE', 10)

    pagination = OrderService.get_paginated_orders(
        params['page'], per_page, params.get('search') or '',
        store_ids=current_user.accessible_store_ids(),
        store_id=params.get('store_id'),
        status=params.get('status'),
    )

    return jsonify(api_response(
        success=True,
        data={
            'orders': [order.to_dict() for order in pagination.items],
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages,
            }
        }
    ))


@bp.get('/<int:order_id>')
@bp.response(200, description='订单详情（含明细与支付记录）')
@login_required
@permission_required('order:view')
def detail(order_id):
    """订单详情：带明细、规格、支付记录

    退款单等二期做完退款审批流后再加进来。
    """
    order = OrderService.get_order_or_404(order_id)
    OrderService.assert_in_scope(order)
    return jsonify(api_response(success=True, data=order.to_dict(with_items=True)))


@bp.post('')
@bp.response(201, description='下单成功，返回订单（含明细）')
@login_required
@permission_required('order:create')
@bp.arguments(OrderCreateSchema, location='json')
def create(data):
    """下单（顾客自助点单、服务员代点、收银台下单都走这里）

    **只传菜品和数量，不传金额**——价格由后端按本店实际价 + 规格加价现算，
    前端传什么价格都不采信。

    菜品已停售 / 本店已下架 → 400；必选规格没选、单选组选了多个 → 400；
    门店或菜品不存在 → 404；超出数据范围 → 403。
    """
    order = OrderService.create_order(data)
    return jsonify(api_response(
        success=True,
        message=f'下单成功，单号 {order.order_no}',
        data=order.to_dict(with_items=True)
    )), 201


@bp.post('/<int:order_id>/accept')
@bp.response(200, description='接单成功')
@login_required
@permission_required('order:receive')
def accept(order_id):
    """接单：待接单 → 已接单"""
    order = OrderService.accept_order(order_id)
    return jsonify(api_response(
        success=True,
        message=f'订单 {order.order_no} 已接单',
        data=order.to_dict()
    ))


@bp.post('/<int:order_id>/complete')
@bp.response(200, description='已完成')
@login_required
@permission_required('order:receive')
def complete(order_id):
    """完成：已接单 → 已完成"""
    order = OrderService.complete_order(order_id)
    return jsonify(api_response(
        success=True,
        message=f'订单 {order.order_no} 已完成',
        data=order.to_dict()
    ))


@bp.post('/<int:order_id>/cancel')
@bp.response(200, description='已取消')
@login_required
@permission_required('order:cancel')
def cancel(order_id):
    """取消订单（需要 order:cancel——收银员没有，值班经理和店长有）

    已经收过钱的订单不能直接取消，要先走退款流程。
    """
    order = OrderService.cancel_order(order_id)
    return jsonify(api_response(
        success=True,
        message=f'订单 {order.order_no} 已取消',
        data=order.to_dict()
    ))


@bp.post('/<int:order_id>/payments')
@bp.response(201, description='收款已记录')
@login_required
@permission_required('pay:collect')
@bp.arguments(PaymentCreateSchema, location='json')
def collect(data, order_id):
    """记一笔收款

    一个订单可以多次调用：组合支付（储值 + 现金）、先定金后尾款。
    金额累加到订单的 paid_amount，收款额超过未付部分会被拒。
    """
    payment = OrderService.add_payment(order_id, data)
    order = OrderService.get_order_or_404(order_id)
    return jsonify(api_response(
        success=True,
        message=f'已收款 ¥{payment.amount:.2f}',
        data={
            'payment': payment.to_dict(),
            'order': order.to_dict(),
        }
    )), 201
