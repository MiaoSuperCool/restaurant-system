from datetime import datetime, timezone
from decimal import Decimal

from flask import current_app
from flask_login import current_user

from backend.app.errors import BusinessError, NotFoundError
from backend.app.extensions import db
from backend.app.models import BalanceTxn, Order, Refund, RefundTxn
from backend.app.services.audit_service import AuditService
from backend.app.services.balance_service import BalanceService
from backend.app.services.points_service import PointsService

RESOURCE = 'refund'


class RefundService:
    # ---------- 查询 ----------

    @staticmethod
    def get_refund_or_404(refund_id):
        refund = db.session.get(Refund, refund_id)
        if not refund:
            raise NotFoundError('退款单不存在')
        return refund

    @staticmethod
    def assert_in_scope(refund):
        """数据范围走订单的门店——退款单本身没有门店，它挂在订单上"""
        allowed = current_user.accessible_store_ids()
        if allowed is not None and refund.order.store_id not in allowed:
            raise BusinessError('无权操作其他门店的退款单', status_code=403)

    @staticmethod
    def get_paginated_refunds(page=1, per_page=10, search=None, store_ids=None,
                              store_id=None, status=None):
        query = Refund.query.join(Order, Refund.order_id == Order.id)

        if store_ids is not None:
            query = query.filter(Order.store_id.in_(store_ids))
        if store_id:
            query = query.filter(Order.store_id == store_id)
        if status:
            query = query.filter(Refund.status == status)
        if search:
            query = query.filter(db.or_(
                Refund.refund_no.ilike(f'%{search}%'),
                Order.order_no.ilike(f'%{search}%'),
            ))

        return (query
                .order_by(Refund.id.desc())
                .paginate(page=page, per_page=per_page, error_out=False))

    # ---------- 校验 ----------

    @staticmethod
    def _in_flight_amount(order, exclude_refund_id=None):
        """已经申请出去、但钱还没退的金额

        算可退金额时必须把它扣掉，否则同一个订单连着提两笔申请、
        两笔加起来超过实收，批完就该倒贴了。
        """
        total = Decimal('0')
        for refund in order.refunds:
            if refund.id == exclude_refund_id:
                continue
            if refund.status in (Refund.STATUS_PENDING, Refund.STATUS_APPROVED):
                total += refund.amount
        return total

    @staticmethod
    def _assert_amount_available(order, amount, exclude_refund_id=None):
        available = (order.refundable_amount
                     - RefundService._in_flight_amount(order, exclude_refund_id))
        if Decimal(amount) > available:
            raise BusinessError(
                f'可退金额只剩 ¥{available:.2f}'
                f'（已收 ¥{order.paid_amount:.2f}，已退 ¥{order.refunded_amount:.2f}，'
                f'处理中 ¥{RefundService._in_flight_amount(order, exclude_refund_id):.2f}）'
            )

    @staticmethod
    def _assert_approve_limit(amount):
        """超过限额的退款要更高的权限

        设计文档里「值班经理是受限版店长：大额退款批不了」那句，
        落地就是这个判断。限额配在 REFUND_APPROVE_LIMIT。
        """
        limit = Decimal(str(current_app.config.get('REFUND_APPROVE_LIMIT', 200)))
        if Decimal(amount) > limit and not current_user.has_permission('refund:approve:large'):
            raise BusinessError(
                f'退款 ¥{amount:.2f} 超过审批限额 ¥{limit:.2f}，'
                f'需要「审批大额退款」权限',
                status_code=403,
            )

    @staticmethod
    def _next_refund_no(order):
        """退款单号挂在原订单号后面：一眼看出是哪一单的第几次退款"""
        seq = Refund.query.filter_by(order_id=order.id).count() + 1
        return f'{order.order_no}-R{seq:02d}'

    # ---------- 流程 ----------

    @staticmethod
    def create_refund(order_id, data):
        """发起退款申请。这一步只产生「流程」，钱一分没动"""
        try:
            order = db.session.get(Order, order_id)
            if not order:
                raise NotFoundError('订单不存在')

            allowed = current_user.accessible_store_ids()
            if allowed is not None and order.store_id not in allowed:
                raise BusinessError('无权操作其他门店的订单', status_code=403)

            if order.paid_amount <= 0:
                raise BusinessError('这单还没收过钱，没什么可退的')

            RefundService._assert_amount_available(order, data['amount'])

            refund = Refund(
                refund_no=RefundService._next_refund_no(order),
                order_id=order.id,
                amount=data['amount'],
                reason=data['reason'],
                type=data['type'],
                applicant_id=current_user.id,
                applicant_name=current_user.real_name or current_user.username,
            )
            db.session.add(refund)
            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='CREATE_REFUND',
                resource=RESOURCE,
                status='success',
                new_value=refund.to_dict(),
            )
            return refund
        except Exception:
            db.session.rollback()
            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='CREATE_REFUND',
                resource=RESOURCE,
                status='failed',
            )
            raise

    @staticmethod
    def approve(refund_id, remark=''):
        """批准退款。批准 ≠ 钱退了，还要再走一步「确认退款」"""
        try:
            refund = RefundService.get_refund_or_404(refund_id)
            RefundService.assert_in_scope(refund)

            if not refund.can_transition_to(Refund.STATUS_APPROVED):
                raise BusinessError(
                    f'退款单当前是「{refund.STATUS_LABELS[refund.status]}」，不能批准'
                )
            RefundService._assert_approve_limit(refund.amount)

            # 自己申请的自己批，等于没有审批
            if refund.applicant_id == current_user.id:
                raise BusinessError('不能审批自己发起的退款申请')

            old_value = refund.to_dict()
            refund.status = Refund.STATUS_APPROVED
            refund.approver_id = current_user.id
            refund.approver_name = current_user.real_name or current_user.username
            refund.approve_remark = remark
            refund.approved_at = datetime.now(timezone.utc)
            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='APPROVE_REFUND',
                resource=RESOURCE,
                status='success',
                old_value=old_value,
                new_value=refund.to_dict(),
            )
            return refund
        except Exception:
            db.session.rollback()
            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='APPROVE_REFUND',
                resource=RESOURCE,
                status='failed',
            )
            raise

    @staticmethod
    def reject(refund_id, remark=''):
        """驳回退款。必须写原因——不写的话发起人不知道为什么被拒"""
        try:
            refund = RefundService.get_refund_or_404(refund_id)
            RefundService.assert_in_scope(refund)

            if not remark.strip():
                raise BusinessError('驳回必须写原因')

            if not refund.can_transition_to(Refund.STATUS_REJECTED):
                raise BusinessError(
                    f'退款单当前是「{refund.STATUS_LABELS[refund.status]}」，不能驳回'
                )

            old_value = refund.to_dict()
            refund.status = Refund.STATUS_REJECTED
            refund.approver_id = current_user.id
            refund.approver_name = current_user.real_name or current_user.username
            refund.approve_remark = remark
            refund.approved_at = datetime.now(timezone.utc)
            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='REJECT_REFUND',
                resource=RESOURCE,
                status='success',
                old_value=old_value,
                new_value=refund.to_dict(),
            )
            return refund
        except Exception:
            db.session.rollback()
            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='REJECT_REFUND',
                resource=RESOURCE,
                status='failed',
            )
            raise

    @staticmethod
    def settle(refund_id, data):
        """确认退款完成：钱真的出去了，记一条退款流水

        线上退款这里会去调微信退款接口（一期是模拟的）；
        线下补录这里是"确认现金已经给顾客了"。

        把「申请单」和「流水」分开的理由就在这一步：审批通过之后，钱可能过几分钟
        （线上）也可能过几天（线下等财务取现）才真的出去。中间隔着的这段时间里，
        光看申请单是不知道钱到底出去没有的。
        """
        try:
            refund = RefundService.get_refund_or_404(refund_id)
            RefundService.assert_in_scope(refund)

            if not refund.can_transition_to(Refund.STATUS_SETTLED):
                raise BusinessError(
                    f'退款单当前是「{refund.STATUS_LABELS[refund.status]}」，不能确认退款；'
                    f'要先审批通过'
                )

            order = refund.order
            # 打款这一刻再校验一次：从申请到打款之间，可能又退过别的钱
            RefundService._assert_amount_available(order, refund.amount, refund.id)

            # 退款要把当初返的积分扣回来——按**退款金额**算，和返的时候用同一个
            # 换算。扣不满就扣到 0 为止（顾客可能早把积分花在别的单上了）
            if order.member_id:
                PointsService.revoke(order.member_id, refund.amount, order=order)

                # 还要把当初**抵扣用掉的**积分按比例还回去——全额退时正好全部还原。
                # 比例的分母是实付金额（`payable_amount` 是抵扣之后的值，不会变），
                # 所以分几次退加起来正好等于当初用的那些分
                if order.points_used and order.payable_amount > 0:
                    ratio = Decimal(refund.amount) / Decimal(order.payable_amount)
                    back = int(Decimal(order.points_used) * ratio)
                    if back > 0:
                        PointsService.restore(order.member_id, back, order=order)

            # 退到储值：钱不是「给出去」，是退回顾客自己的账户。
            # 必须挂在那笔储值消费流水上——退回的金额要按原消费的比例
            # 拆成本金和赠送（余额支付扣的时候就是这么扣的）
            if data['method'] == RefundTxn.METHOD_BALANCE:
                consume = BalanceTxn.query.filter_by(
                    order_id=order.id, type=BalanceTxn.TYPE_CONSUME
                ).first()
                if consume is None:
                    raise BusinessError('这单没用过储值支付，退不回储值')
                BalanceService.refund_to_balance(
                    consume, refund.amount, order=order,
                    remark=f'退款单 {refund.refund_no} 退回储值',
                )

            txn = RefundTxn(
                refund_id=refund.id,
                order_id=order.id,
                amount=refund.amount,
                method=data['method'],
                transaction_no=data.get('transaction_no', ''),
                operator_id=current_user.id,
                operator_name=current_user.real_name or current_user.username,
                settled_at=datetime.now(timezone.utc),
            )
            db.session.add(txn)

            refund.status = Refund.STATUS_SETTLED
            order.refunded_amount = order.refunded_amount + refund.amount
            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='SETTLE_REFUND',
                resource=RESOURCE,
                status='success',
                new_value={**refund.to_dict(with_txns=True),
                           'order_refunded_amount': float(order.refunded_amount)},
            )
            return refund
        except Exception:
            db.session.rollback()
            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='SETTLE_REFUND',
                resource=RESOURCE,
                status='failed',
            )
            raise
