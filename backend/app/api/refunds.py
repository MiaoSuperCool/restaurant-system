from flask import current_app, jsonify
from flask_login import current_user, login_required
from flask_smorest import Blueprint

from backend.app.schemas.refund_schema import (
    RefundApproveSchema,
    RefundCreateSchema,
    RefundQuerySchema,
    RefundSettleSchema,
)
from backend.app.services import RefundService
from backend.app.utils.api_response import api_response
from backend.app.utils.decorators import permission_required

bp = Blueprint('refunds', __name__, url_prefix='/api/refunds')

# 退款是四步，权限也分四级：
#   发起   refund:apply           收银员及以上
#   审批   refund:approve         值班经理及以上（限额内）
#          refund:approve:large   超过 REFUND_APPROVE_LIMIT 才需要，只有店长/老板有
#   打款   refund:approve         钱出去是审批人点头的结果，不另外开权限
#   查看   refund:view            财务、店长、老板


@bp.get('')
@bp.response(200, description='退款单列表（data.refunds + data.pagination）')
@login_required
@permission_required('refund:view')
@bp.arguments(RefundQuerySchema, location='query')
def index(params):
    """退款单列表（分页 + 按退款单号/订单号搜索 + 按门店和状态筛选）

    数据范围：店长只看得到本店订单的退款单。
    """
    per_page = params.get('per_page') or current_app.config.get('DEFAULT_PAGE_SIZE', 10)

    pagination = RefundService.get_paginated_refunds(
        params['page'], per_page, params.get('search') or '',
        store_ids=current_user.accessible_store_ids(),
        store_id=params.get('store_id'),
        status=params.get('status'),
    )

    return jsonify(api_response(
        success=True,
        data={
            'refunds': [refund.to_dict(with_txns=True) for refund in pagination.items],
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages,
            }
        }
    ))


@bp.post('/orders/<int:order_id>')
@bp.response(201, description='申请已提交，等待审批')
@login_required
@permission_required('refund:apply')
@bp.arguments(RefundCreateSchema, location='json')
def create(data, order_id):
    """对某个订单发起退款申请

    这一步**只产生流程，钱一分没动**。要等审批通过、再确认退款，钱才真的出去。

    金额超过订单的可退金额 → 400（会说明还剩多少可退）；
    订单不存在 → 404；超出数据范围 → 403。
    """
    refund = RefundService.create_refund(order_id, data)
    return jsonify(api_response(
        success=True,
        message=f'退款申请已提交（{refund.refund_no}），等待审批',
        data=refund.to_dict()
    )), 201


@bp.post('/<int:refund_id>/approve')
@bp.response(200, description='已批准，等打款')
@login_required
@permission_required('refund:approve')
@bp.arguments(RefundApproveSchema, location='json')
def approve(data, refund_id):
    """批准退款

    **批准 ≠ 钱退了**——还要再调一次「确认退款」记流水。

    超过 REFUND_APPROVE_LIMIT 的金额需要 refund:approve:large（这个判断在
    service 层，因为装饰器不知道金额）。不能审批自己发起的申请。
    """
    refund = RefundService.approve(refund_id, data.get('remark', ''))
    return jsonify(api_response(
        success=True,
        message=f'{refund.refund_no} 已批准，请确认打款',
        data=refund.to_dict()
    ))


@bp.post('/<int:refund_id>/reject')
@bp.response(200, description='已驳回')
@login_required
@permission_required('refund:approve')
@bp.arguments(RefundApproveSchema, location='json')
def reject(data, refund_id):
    """驳回退款（必须写原因）"""
    refund = RefundService.reject(refund_id, data.get('remark', ''))
    return jsonify(api_response(
        success=True,
        message=f'{refund.refund_no} 已驳回',
        data=refund.to_dict()
    ))


@bp.post('/<int:refund_id>/settle')
@bp.response(200, description='退款完成，已记流水')
@login_required
@permission_required('refund:approve')
@bp.arguments(RefundSettleSchema, location='json')
def settle(data, refund_id):
    """确认退款完成：钱真的出去了

    线上退款这一步会去调微信退款接口（一期是模拟的）；
    线下补录是「确认现金已经给顾客了」。两种都会记一条退款流水。
    """
    refund = RefundService.settle(refund_id, data)
    return jsonify(api_response(
        success=True,
        message=f'{refund.refund_no} 已退款',
        data=refund.to_dict(with_txns=True)
    ))
