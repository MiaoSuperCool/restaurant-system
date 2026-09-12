"""支付记录

**为什么单开一张表，而不是在订单上放个「已支付」字段**

一个订单可能有**多笔支付**：
- 组合支付——储值付一部分、现金付一部分
- 先付定金、取餐时付尾款
- 线上支付失败重试

而且支付有**资金属性**：第三方流水号（微信支付单号）、支付时间、支付方式。
**财务对账全靠这些**——月底要拿微信账单和我们的记录逐笔核，订单上一个布尔
字段根本对不上。

一张支付记录 = 一笔真实的钱进来了。退出去的钱记在退款流水（refund_txn）里，
两者对称：支付记进账，退款流水记出账。
"""
from datetime import datetime, timezone

from backend.app.extensions import db
from backend.app.models.base import BaseModel


class Payment(BaseModel):
    __tablename__ = 'payment'

    # ---------- 支付方式 ----------
    METHOD_WECHAT = 'wechat'          # 微信支付
    METHOD_CASH = 'cash'              # 现金
    METHOD_BALANCE = 'balance'        # 会员储值（二期）
    METHOD_GROUPON = 'groupon'        # 团购券核销
    METHOD_LABELS = {
        METHOD_WECHAT: '微信支付',
        METHOD_CASH: '现金',
        METHOD_BALANCE: '储值',
        METHOD_GROUPON: '团购券',
    }

    # ---------- 状态 ----------
    STATUS_PENDING = 'pending'        # 发起中（线上支付等回调）
    STATUS_SUCCESS = 'success'        # 成功
    STATUS_FAILED = 'failed'          # 失败（可以再发起一笔，所以失败也要留痕）
    STATUS_LABELS = {
        STATUS_PENDING: '支付中',
        STATUS_SUCCESS: '支付成功',
        STATUS_FAILED: '支付失败',
    }

    # RESTRICT：订单被支付记录引用后不能删（对账要留痕）
    order_id = db.Column(
        db.Integer, db.ForeignKey('order.id', ondelete='RESTRICT'),
        nullable=False, index=True,
    )

    method = db.Column(db.String(20), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_SUCCESS, index=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)

    # 我们自己的支付流水号（每笔支付一个，和订单号一样可读）
    payment_no = db.Column(db.String(32), unique=True, nullable=False, index=True)
    # 第三方流水号：微信支付单号、团购券核销码等。
    # 现金没有第三方流水号，留空。**对账靠这个字段和渠道账单逐笔核**
    transaction_no = db.Column(db.String(64), nullable=False, default='', index=True)

    # 收款人（员工）。线上自助支付时为空
    operator_id = db.Column(
        db.Integer, db.ForeignKey('staff.id', ondelete='SET NULL'), nullable=True,
    )
    operator_name = db.Column(db.String(50), nullable=False, default='')

    paid_at = db.Column(db.DateTime, nullable=True)

    def mark_success(self, transaction_no='', operator_id=None, operator_name=''):
        self.status = self.STATUS_SUCCESS
        self.transaction_no = transaction_no or self.transaction_no
        self.operator_id = operator_id
        self.operator_name = operator_name or self.operator_name
        self.paid_at = datetime.now(timezone.utc)

    def to_dict(self):
        return {
            'id': self.id,
            'order_id': self.order_id,
            'method': self.method,
            'method_label': self.METHOD_LABELS.get(self.method, self.method),
            'status': self.status,
            'status_label': self.STATUS_LABELS.get(self.status, self.status),
            'amount': float(self.amount),
            'payment_no': self.payment_no,
            'transaction_no': self.transaction_no,
            'operator_id': self.operator_id,
            'operator_name': self.operator_name,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
