"""团购券核销

核销这件事有两面：对顾客是「我这单用团购券抵掉」，对门店是「这张券用掉了，
月底要拿去和美团对账」。所以它同时产生一条核销记录和一笔收款记录。
"""
from datetime import datetime, timezone
from decimal import Decimal

from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from backend.app.errors import BusinessError, NotFoundError
from backend.app.extensions import db
from backend.app.models import GrouponVoucher, Order, Payment
from backend.app.services.audit_service import AuditService

RESOURCE = 'groupon_voucher'


class GrouponService:
    @staticmethod
    def find_by_code(code):
        return GrouponVoucher.query.filter_by(code=code).first()

    @staticmethod
    def verify(order_id, data):
        """核销一张团购券：记核销 + 记一笔 groupon 收款"""
        try:
            order = db.session.get(Order, order_id)
            if not order:
                raise NotFoundError('订单不存在')

            allowed = current_user.accessible_store_ids()
            if allowed is not None and order.store_id not in allowed:
                raise BusinessError('无权操作其他门店的订单', status_code=403)

            if order.status == Order.STATUS_CANCELLED:
                raise BusinessError('订单已取消，不能核销')

            code = data['code'].strip()

            # 第一道防线：先查一次，给一句人能看懂的提示。
            # 真正防重复的是下面的唯一约束——两个收银员同时核销同一张券时，
            # 「先查再插」挡不住，数据库能
            existing = GrouponService.find_by_code(code)
            if existing:
                raise BusinessError(
                    f'券码 {code} 已经核销过了'
                    f'（{existing.verified_by_name} 于 '
                    f'{existing.verified_at:%Y-%m-%d %H:%M} 在订单 {existing.order.order_no} 核销）'
                )

            amount = Decimal(data['amount'])
            remaining = order.payable_amount - order.paid_amount
            if amount > remaining:
                raise BusinessError(
                    f'券面额 ¥{amount:.2f} 超过未付部分（还剩 ¥{remaining:.2f}）；'
                    f'团购券只能抵扣，不找零'
                )

            # 收款流水号用券码：对账时一眼能对上
            payment = Payment(
                order_id=order.id,
                method=Payment.METHOD_GROUPON,
                amount=amount,
                payment_no=f'{order.order_no}-P{len(order.payments) + 1:02d}',
            )
            payment.mark_success(
                transaction_no=code,
                operator_id=current_user.id,
                operator_name=current_user.real_name or current_user.username,
            )
            order.payments.append(payment)
            order.paid_amount = order.paid_amount + amount
            db.session.flush()

            voucher = GrouponVoucher(
                code=code,
                platform=data['platform'],
                amount=amount,
                order_id=order.id,
                payment_id=payment.id,
                verified_by_id=current_user.id,
                verified_by_name=current_user.real_name or current_user.username,
                verified_at=datetime.now(timezone.utc),
            )
            db.session.add(voucher)
            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='VERIFY_GROUPON',
                resource=RESOURCE,
                status='success',
                new_value=voucher.to_dict(),
            )
            return voucher, order
        except IntegrityError as err:
            # 唯一约束兜住了并发：另一个收银员抢先核销了同一张券。
            # from err 保留原始异常链——如果不是「撞券码」而是别的约束问题，
            # 日志里还能看出真正的原因
            db.session.rollback()
            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='VERIFY_GROUPON',
                resource=RESOURCE,
                status='failed',
            )
            raise BusinessError(f'券码 {data["code"]} 已经被核销了（并发提交）') from err
        except Exception:
            db.session.rollback()
            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='VERIFY_GROUPON',
                resource=RESOURCE,
                status='failed',
            )
            raise

    @staticmethod
    def get_paginated_vouchers(page=1, per_page=10, search=None, store_ids=None):
        """核销记录列表——月底拿去和美团/抖音对账用"""
        query = GrouponVoucher.query.join(Order, GrouponVoucher.order_id == Order.id)

        if store_ids is not None:
            query = query.filter(Order.store_id.in_(store_ids))
        if search:
            query = query.filter(db.or_(
                GrouponVoucher.code.ilike(f'%{search}%'),
                Order.order_no.ilike(f'%{search}%'),
            ))

        return (query
                .order_by(GrouponVoucher.id.desc())
                .paginate(page=page, per_page=per_page, error_out=False))
