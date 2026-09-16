"""积分账户 + 积分流水（会员资产域）

设计文档「必须守住的 6 条」第 1 条把余额和积分并列：**都得有流水账**。
理由和储值一样——只存一个数字，出了事谁也说不清是怎么少的。

和储值最大的不同：积分不分本金和赠送
------------------------------------

储值要拆成本金/赠送，是因为其中有「顾客真掏的钱」（退款时要能分出来）。
**积分全是送的**——消费返的、活动给的，没有一分是顾客掏钱买的，所以
只有一列 `balance`，不用拆。

扣积分也不用挑先后（没有"先花掉不能退的那部分"这回事）。

积分是整数，不是钱
------------------

`balance` 用 `Integer` 而不是 `Numeric`——积分的最小单位就是"1 分"，
没有半分。**到"抵扣多少钱"那一步才换成钱**（换算比例在 PointsService 里）。
"""
from backend.app.extensions import db
from backend.app.models.base import BaseModel


class Points(BaseModel):
    """积分账户：一个会员一个"""
    __tablename__ = 'points'

    member_id = db.Column(
        db.Integer, db.ForeignKey('member.id', ondelete='RESTRICT'),
        nullable=False, unique=True, index=True,
    )
    member = db.relationship('Member', backref=db.backref('points', uselist=False))

    # 积分余额（整数）。不像储值那样拆两列——积分全是送的，没有"本金"
    balance = db.Column(db.Integer, nullable=False, default=0)

    def to_dict(self):
        return {
            'member_id': self.member_id,
            'balance': self.balance,
        }


class PointsTxn(BaseModel):
    """积分流水：每一笔变动都留一条"""
    __tablename__ = 'points_txn'

    # ---------- 类型 ----------
    TYPE_EARN = 'earn'          # 消费返积分
    TYPE_REDEEM = 'redeem'      # 用积分抵扣（扣）
    TYPE_ADJUST = 'adjust'      # 员工手工调整（补偿、纠错）
    TYPE_REVOKE = 'revoke'      # 退款扣回（把当初**返的**扣回来）
    TYPE_RESTORE = 'restore'    # 退款返还（把当初**抵扣用的**还回去）
    TYPE_MIGRATE = 'migrate'    # 老系统迁移导入
    TYPE_LABELS = {
        TYPE_EARN: '消费返积分',
        TYPE_REDEEM: '积分抵扣',
        TYPE_ADJUST: '手工调整',
        TYPE_REVOKE: '退款扣回',
        TYPE_RESTORE: '退款返还',
        TYPE_MIGRATE: '老系统迁移',
    }

    member_id = db.Column(
        db.Integer, db.ForeignKey('member.id', ondelete='RESTRICT'),
        nullable=False, index=True,
    )
    member = db.relationship('Member', backref=db.backref('points_txns', lazy='dynamic'))

    type = db.Column(db.String(20), nullable=False, index=True)

    # 变动（正负号有意义）和变动后的余额——「变动后」是对账的锚点，
    # 一眼看出是哪一笔不对，不用把全部流水重算一遍
    delta = db.Column(db.Integer, nullable=False, default=0)
    after = db.Column(db.Integer, nullable=False, default=0)

    order_id = db.Column(
        db.Integer, db.ForeignKey('order.id', ondelete='RESTRICT'),
        nullable=True, index=True,
    )
    order = db.relationship('Order', backref=db.backref('points_txns', lazy='dynamic'))

    legacy_no = db.Column(db.String(64), nullable=False, default='')
    remark = db.Column(db.String(255), nullable=False, default='')

    def to_dict(self):
        return {
            'id': self.id,
            'member_id': self.member_id,
            'type': self.type,
            'type_label': self.TYPE_LABELS.get(self.type, self.type),
            'delta': self.delta,
            'after': self.after,
            'order_id': self.order_id,
            'legacy_no': self.legacy_no,
            'remark': self.remark,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
