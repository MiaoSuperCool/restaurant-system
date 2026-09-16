"""储值账户 + 余额流水（会员资产域）

**余额绝不能用「一个数字字段」糊弄**——设计文档「必须守住的 6 条」第 1 条。
那 80 万要一分不差，全靠流水能对得上。

本金和赠送为什么分开存
----------------------

充 100 送 20 是餐饮的常规操作。但如果只记一个「余额 120」：

    顾客用掉一半不想用了，该退多少？60 还是 50？

通常规则是**本金能退、赠送不退**。要回答这个问题，账上就必须分得清「顾客真掏的
钱」和「公司送的钱」——所以账户存两列，流水也记两列。

扣款顺序：先扣赠送，再扣本金
----------------------------

对顾客友好（先花掉不能退的那部分，本金留着随时能退），而且**结束时状态干净**——
赠送先清零，剩下的全是能退的本金。反过来先扣本金的话，会出现「本金花完了、
赠送还剩一堆」的状态，那时候退款规则就很尴尬。

扣款要锁住那一行
----------------

不能用「读出来 → 比较 → 写回去」：两个收银台同时给同一个会员扣余额时，两边各自
读到 100、各自以为够，提交后余额成了 -20。

所以变动前先 `SELECT ... FOR UPDATE` 把这一行锁住（见 `BalanceService._load`），
后来的请求得排队。**不锁的话，账面上的「变动后余额」也会错**——你以为自己是在
100 的基础上扣的，其实中间已经被别人扣过一笔了。

（另一种写法是「带条件的 UPDATE + 看 rowcount」，但「先扣赠送再扣本金」是两步，
用条件写会很绕。行锁更直白，也是银行扣款的标准做法。）
"""
from sqlalchemy.ext.hybrid import hybrid_property

from backend.app.extensions import db
from backend.app.models.base import BaseModel


class Balance(BaseModel):
    """储值账户：一个会员一个

    不存「余额」这一个数，而是分成本金和赠送两列——理由见模块开头。
    """
    __tablename__ = 'balance'

    # RESTRICT：会员还有储值就不能删。但正常情况下会员是停用（is_active=False），
    # 不删——历史订单还得认得这个人
    member_id = db.Column(
        db.Integer, db.ForeignKey('member.id', ondelete='RESTRICT'),
        nullable=False, unique=True, index=True,
    )
    member = db.relationship('Member', backref=db.backref('balance', uselist=False))

    # 本金：顾客真掏的钱，**能退**
    principal = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    # 赠送：充值送的，**不退**。扣款时它先花掉
    bonus = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    @property
    def total(self):
        """账上还能花多少"""
        return self.principal + self.bonus

    def to_dict(self):
        return {
            'member_id': self.member_id,
            'principal': float(self.principal),
            'bonus': float(self.bonus),
            'total': float(self.total),
        }


class BalanceTxn(BaseModel):
    """余额流水：每一笔变动都留一条

    设计文档要求流水记「变动后余额」——**对账时能一眼看出是哪一笔不对，
    不用把全部流水重算一遍。** 这里因为是本金/赠送分开的，所以记两个。
    """
    __tablename__ = 'balance_txn'

    # ---------- 类型 ----------
    TYPE_RECHARGE = 'recharge'    # 充值（进本金）
    TYPE_BONUS = 'bonus'          # 充值送的（进赠送）
    TYPE_CONSUME = 'consume'      # 余额支付（扣）
    TYPE_REFUND = 'refund'        # 订单退款，钱退回余额（加）
    TYPE_MIGRATE = 'migrate'      # 老系统迁移导入
    TYPE_ADJUST = 'adjust'        # 财务手工调整（补偿、纠错）
    TYPE_LABELS = {
        TYPE_RECHARGE: '充值',
        TYPE_BONUS: '充值赠送',
        TYPE_CONSUME: '余额消费',
        TYPE_REFUND: '退款退回余额',
        TYPE_MIGRATE: '老系统迁移',
        TYPE_ADJUST: '手工调整',
    }

    member_id = db.Column(
        db.Integer, db.ForeignKey('member.id', ondelete='RESTRICT'),
        nullable=False, index=True,
    )
    member = db.relationship('Member', backref=db.backref('balance_txns', lazy='dynamic'))

    type = db.Column(db.String(20), nullable=False, index=True)

    # ---------- 变动 ----------
    # 本金和赠送**各记各的**：退款要按原路退回（扣的时候扣了多少本金，
    # 退的时候就退多少本金），所以必须分得清
    principal_delta = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    bonus_delta = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    # 变动后的余额快照——对账的锚点
    principal_after = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    bonus_after = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    # ---------- 关联 ----------
    # 消费/退回时挂着订单；充值没有订单
    order_id = db.Column(
        db.Integer, db.ForeignKey('order.id', ondelete='RESTRICT'),
        nullable=True, index=True,
    )
    order = db.relationship('Order', backref=db.backref('balance_txns', lazy='dynamic'))

    # 老系统单号：迁移过来的流水要能追回源头
    legacy_no = db.Column(db.String(64), nullable=False, default='')

    remark = db.Column(db.String(255), nullable=False, default='')

    @hybrid_property
    def amount(self):
        """这笔变动的总额（正负号有意义）

        用 hybrid_property 而不是存一列：Python 里当属性用、SQL 里当表达式用
        （`SUM(BalanceTxn.amount)` 能直接写），省一列冗余数据，也就不会出现
        「金额和两个明细对不上」的情况
        """
        return self.principal_delta + self.bonus_delta

    def to_dict(self):
        return {
            'id': self.id,
            'member_id': self.member_id,
            'type': self.type,
            'type_label': self.TYPE_LABELS.get(self.type, self.type),
            'amount': float(self.amount),
            'principal_delta': float(self.principal_delta),
            'bonus_delta': float(self.bonus_delta),
            'principal_after': float(self.principal_after),
            'bonus_after': float(self.bonus_after),
            'order_id': self.order_id,
            'legacy_no': self.legacy_no,
            'remark': self.remark,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
