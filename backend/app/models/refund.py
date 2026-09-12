"""退款申请单 / 退款流水

**为什么退款要独立成单，而不是订单上一个状态字段**

三件事一个状态字段装不下：

1. **有审批流**——谁申请、谁批、批没批。值班经理能批限额内的，
   大额要店长或老板批。一个 `refunded` 布尔值记不下这些
2. **线下退款也要补录留痕**——客户明确要求「口头商量好的退款，事后必须补录」，
   补录的单子同样要有人批、要有理由
3. **一个订单可能退多次**——部分退款（退一道菜的钱）、分次退

**申请单和流水的区别（这条最容易混）**

    退款申请单 refund      = 流程：谁、什么时候、要退多少、批没批
    退款流水   refund_txn  = 钱：金额、时间、退到哪、流水号

**批了 ≠ 钱退了。** 审批通过只是"同意退"，钱真正出去是打款那一刻，
那才是流水。中间可能隔着几分钟（线上调微信退款接口），也可能隔着几天
（线下要等财务去银行取现）。两件事分开记，对账才对得上。

和支付对称：支付记「进账」，退款流水记「出账」。
"""
from backend.app.extensions import db
from backend.app.models.base import BaseModel


class Refund(BaseModel):
    __tablename__ = 'refund'

    # ---------- 类型 ----------
    TYPE_ONLINE = 'online'      # 线上退款：原路退回（微信支付等）
    TYPE_OFFLINE = 'offline'    # 线下补录：钱已经用现金退了，事后补录留痕
    TYPE_LABELS = {
        TYPE_ONLINE: '线上退款',
        TYPE_OFFLINE: '线下补录',
    }

    # ---------- 状态 ----------
    STATUS_PENDING = 'pending'      # 待审批
    STATUS_APPROVED = 'approved'    # 已批准，等打款
    STATUS_REJECTED = 'rejected'    # 已驳回
    STATUS_SETTLED = 'settled'      # 已退款（钱出去了，有流水）
    STATUS_LABELS = {
        STATUS_PENDING: '待审批',
        STATUS_APPROVED: '已批准（待打款）',
        STATUS_REJECTED: '已驳回',
        STATUS_SETTLED: '已退款',
    }
    STATUS_FLOW = {
        STATUS_PENDING: (STATUS_APPROVED, STATUS_REJECTED),
        STATUS_APPROVED: (STATUS_SETTLED,),
        STATUS_REJECTED: (),
        STATUS_SETTLED: (),
    }

    # 退款单号：挂在原订单号后面，一眼看出是哪一单的第几次退款
    refund_no = db.Column(db.String(40), unique=True, nullable=False, index=True)

    order_id = db.Column(
        db.Integer, db.ForeignKey('order.id', ondelete='RESTRICT'),
        nullable=False, index=True,
    )
    order = db.relationship('Order', backref=db.backref('refunds', lazy='dynamic'))

    amount = db.Column(db.Numeric(10, 2), nullable=False)
    reason = db.Column(db.String(255), nullable=False, default='')
    type = db.Column(db.String(20), nullable=False, default=TYPE_ONLINE)
    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING, index=True)

    # ---------- 流程上的两个人 ----------
    # 发起人：收银员/店长点了「申请退款」
    applicant_id = db.Column(
        db.Integer, db.ForeignKey('staff.id', ondelete='SET NULL'), nullable=True,
    )
    applicant_name = db.Column(db.String(50), nullable=False, default='')

    # 审批人：批准或驳回的人。审批意见也要留，否则驳回了不知道为什么
    approver_id = db.Column(
        db.Integer, db.ForeignKey('staff.id', ondelete='SET NULL'), nullable=True,
    )
    approver_name = db.Column(db.String(50), nullable=False, default='')
    approve_remark = db.Column(db.String(255), nullable=False, default='')
    approved_at = db.Column(db.DateTime, nullable=True)

    txns = db.relationship(
        'RefundTxn', backref='refund',
        order_by='RefundTxn.id',
        cascade='all, delete-orphan',
    )

    def can_transition_to(self, status):
        return status in self.STATUS_FLOW.get(self.status, ())

    @property
    def settled_amount(self):
        """实际退出去的钱（可能有退款流水才说明钱真的出去了）"""
        return sum((txn.amount for txn in self.txns), 0)

    def to_dict(self, with_txns=False):
        data = {
            'id': self.id,
            'refund_no': self.refund_no,
            'order_id': self.order_id,
            'order_no': self.order.order_no if self.order else None,
            'amount': float(self.amount),
            'reason': self.reason,
            'type': self.type,
            'type_label': self.TYPE_LABELS.get(self.type, self.type),
            'status': self.status,
            'status_label': self.STATUS_LABELS.get(self.status, self.status),
            'applicant_name': self.applicant_name,
            'approver_name': self.approver_name,
            'approve_remark': self.approve_remark,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if with_txns:
            data['txns'] = [txn.to_dict() for txn in self.txns]
        return data


class RefundTxn(BaseModel):
    """退款流水：钱真的退出去那一刻的记录

    审批通过不等于钱退了（见模块开头）。这张表存在的意义就是回答
    「这笔钱到底出去没有、什么时候出去的、退到哪了」——财务对账问的就是这个。
    """

    __tablename__ = 'refund_txn'

    METHOD_ORIGINAL = 'original'   # 原路退回（微信退款）
    METHOD_CASH = 'cash'           # 现金
    METHOD_BALANCE = 'balance'     # 退到储值账户（二期）
    METHOD_LABELS = {
        METHOD_ORIGINAL: '原路退回',
        METHOD_CASH: '现金',
        METHOD_BALANCE: '退到储值',
    }

    # CASCADE：流水从属于申请单
    refund_id = db.Column(
        db.Integer, db.ForeignKey('refund.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    # 冗余一份 order_id：财务要「按订单看所有资金进出」，
    # 从退款流水连回订单很常用，不值得每次 join 两层
    order_id = db.Column(
        db.Integer, db.ForeignKey('order.id', ondelete='RESTRICT'),
        nullable=False, index=True,
    )

    amount = db.Column(db.Numeric(10, 2), nullable=False)
    method = db.Column(db.String(20), nullable=False, default=METHOD_ORIGINAL)
    # 第三方退款单号（微信退款单号）。现金没有，留空
    transaction_no = db.Column(db.String(64), nullable=False, default='', index=True)

    operator_id = db.Column(
        db.Integer, db.ForeignKey('staff.id', ondelete='SET NULL'), nullable=True,
    )
    operator_name = db.Column(db.String(50), nullable=False, default='')
    settled_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'refund_id': self.refund_id,
            'order_id': self.order_id,
            'amount': float(self.amount),
            'method': self.method,
            'method_label': self.METHOD_LABELS.get(self.method, self.method),
            'transaction_no': self.transaction_no,
            'operator_name': self.operator_name,
            'settled_at': self.settled_at.isoformat() if self.settled_at else None,
        }
