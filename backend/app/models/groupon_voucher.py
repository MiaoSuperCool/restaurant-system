"""团购券核销记录

顾客在美团/抖音买了团购套餐，到店后由收银员核销。核销 = 确认这张券在本店用掉了，
它会作为一笔支付抵扣订单金额。

**为什么不复用 payment 表就够了**

核销有两个 payment 表达不了的东西：

1. **券码全局唯一**——同一张券不能核销两次，这必须在数据库层用唯一约束挡住，
   不能靠代码查一遍。顾客拿着同一张券跑两家店，是真实会发生的事
2. **按平台对账**——月底要和美团、抖音分别对账核销了多少张、多少钱

所以单开一张表记核销，payment 那边只留一笔 `method='groupon'` 的收款记录
（金额、时间），两边通过 payment_id 关联。

注意：目前**没有真的对接美团/抖音的核销接口**——券码是收银员手工输入的，
平台也是手选的。真对接时这里要加一步「调平台接口验证券码有效性」。
"""
from backend.app.extensions import db
from backend.app.models.base import BaseModel


class GrouponVoucher(BaseModel):
    __tablename__ = 'groupon_voucher'

    # ---------- 平台 ----------
    PLATFORM_MEITUAN = 'meituan'
    PLATFORM_DOUYIN = 'douyin'
    PLATFORM_OTHER = 'other'
    PLATFORM_LABELS = {
        PLATFORM_MEITUAN: '美团',
        PLATFORM_DOUYIN: '抖音',
        PLATFORM_OTHER: '其他',
    }

    # 券码全局唯一：同一张券不能核销两次。这是这张表存在的主要理由，
    # 靠代码「先查再插」在并发下挡不住，得让数据库来
    code = db.Column(db.String(64), unique=True, nullable=False, index=True)

    platform = db.Column(db.String(20), nullable=False, default=PLATFORM_MEITUAN, index=True)
    # 券面额：抵扣多少
    amount = db.Column(db.Numeric(10, 2), nullable=False)

    # RESTRICT：订单被核销记录引用后不能删（对账要留痕）
    order_id = db.Column(
        db.Integer, db.ForeignKey('order.id', ondelete='RESTRICT'),
        nullable=False, index=True,
    )
    order = db.relationship('Order', backref=db.backref('vouchers', lazy='dynamic'))

    # 对应的收款记录（method='groupon'）。SET NULL：支付记录被清掉时核销记录还在
    payment_id = db.Column(
        db.Integer, db.ForeignKey('payment.id', ondelete='SET NULL'),
        nullable=True, index=True,
    )

    # 谁核销的、什么时候——核销是设计文档点名的关键动作，必须留痕
    verified_by_id = db.Column(
        db.Integer, db.ForeignKey('staff.id', ondelete='SET NULL'), nullable=True,
    )
    verified_by_name = db.Column(db.String(50), nullable=False, default='')
    verified_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'platform': self.platform,
            'platform_label': self.PLATFORM_LABELS.get(self.platform, self.platform),
            'amount': float(self.amount),
            'order_id': self.order_id,
            'order_no': self.order.order_no if self.order else None,
            'payment_id': self.payment_id,
            'verified_by_name': self.verified_by_name,
            'verified_at': self.verified_at.isoformat() if self.verified_at else None,
        }
