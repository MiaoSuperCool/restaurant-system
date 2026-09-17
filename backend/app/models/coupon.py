"""券模板 + 用户持券（营销域）

设计文档「必须守住的 6 条」第 2 条：**优惠券拆两张表**。

为什么不能合成一张
------------------

券模板是**规则**——「满 100 减 20」这一条，运营定义一次，发给多少人都是它。
用户持券是**实例**——张三手里那张券，有它自己的领取时间、使用时间、在哪家店用的。

合并的话两边都难受：改规则会动到已经发出去的券（发给别人的券凭什么跟着变），
改某张券的状态又要去动模板（那张模板是大家共用的）。

和「菜品 vs 门店菜品」「规格组 vs 规格选项」是同一个道理——**有各自的属性，
就得各占一张表**。

过期不写库
----------

`status` 只有两个值：未用 / 已用。**过期是算出来的**（`template.valid_to < 现在`），
不是写进库的一个状态。

好处：不会出现「该过期了但 status 还是 unused」的脏数据——那种要靠定时任务去扫，
任务挂了就烂在那儿，而且谁也说不清一条记录是什么时候变脏的。
代价：查「有效券」时每条都要带上时间判断（`UserCoupon.is_expired`）。

**券的过期本来就是「到点自然失效」，不是一个动作**，所以不写库反而更准。

----------------------------------------------------------------------

**没有券码。** 团购券（`GrouponVoucher`）有 `code` 是因为要防重复核销——那是
平台发出去的凭据；本店自己的券在会员的券包里，点一下就用，不需要报码。
代价是顾客没带手机就用不了（演示时无所谓，真要做是另一个功能）。
"""
from datetime import datetime, timezone
from decimal import Decimal

from backend.app.extensions import db
from backend.app.models.base import BaseModel


def _as_aware(moment):
    """库里存的是不带时区的 UTC，比之前补上，免得 naive/aware 相减报错

    有效期判断在模板和持券两边都要用（持券那边直接问模板），转换就这一处。
    """
    if moment is not None and moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment


# 券的适用门店（多对多，纯关联表）。
# 一行都没有 = 全公司通用（和分类的 `category_store` 一个语义）。
# 两边 CASCADE：这是「配置」不是「业务数据」，门店或券模板没了配置自然消失
coupon_template_store = db.Table(
    'coupon_template_store',
    db.Column('template_id', db.Integer,
              db.ForeignKey('coupon_template.id', ondelete='CASCADE'), primary_key=True),
    db.Column('store_id', db.Integer,
              db.ForeignKey('store.id', ondelete='CASCADE'), primary_key=True),
)


class CouponTemplate(BaseModel):
    """券模板：运营定义的一种券"""
    __tablename__ = 'coupon_template'

    # ---------- 类型 ----------
    TYPE_FULL_CUT = 'full_cut'      # 满减：满 min_amount 减 value 元
    TYPE_DISCOUNT = 'discount'      # 折扣：value 是折扣率（0.85 = 八五折）
    TYPE_LABELS = {
        TYPE_FULL_CUT: '满减',
        TYPE_DISCOUNT: '折扣',
    }

    # ---------- 状态 ----------
    STATUS_ACTIVE = 'active'        # 能发、能用
    STATUS_DISABLED = 'disabled'    # 停发；**已经发出去的还能用**（不能赖账）
    STATUS_LABELS = {
        STATUS_ACTIVE: '启用',
        STATUS_DISABLED: '停用',
    }

    name = db.Column(db.String(64), nullable=False)
    type = db.Column(db.String(20), nullable=False, default=TYPE_FULL_CUT)

    # 满减：减多少钱；折扣：折扣率（0.85）
    value = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    # 门槛：满多少才能用。0 = 无门槛
    min_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    # 有效期。两个都可空 = 长期有效
    valid_from = db.Column(db.DateTime, nullable=True)
    valid_to = db.Column(db.DateTime, nullable=True)

    # 发放总量；NULL = 不限量。只约束「发」，不约束「用」——
    # 发出去多少张是运营该管的，卡在用的那一步只会让顾客莫名其妙用不了
    total_quantity = db.Column(db.Integer, nullable=True)

    # 挂到券中心让顾客自己领。默认不挂——券默认是「运营圈了人才发」的东西，
    # 敞开让人领得是想清楚了才做的事
    is_claimable = db.Column(db.Boolean, nullable=False, default=False)

    # 每人能自己领几张；NULL = 不限
    #
    # **只管「自领」这一条路**，不约束员工发券：员工定向发是「我知道我在给谁、
    # 给几张」，有审计兜着；这个字段防的是顾客反复点「领取」。
    # 混成一条规则的话，补偿顾客时想多给一张还得先去改模板
    per_member_limit = db.Column(db.Integer, nullable=True)

    status = db.Column(db.String(20), nullable=False, default=STATUS_ACTIVE, index=True)

    # 适用门店：空 = 全公司通用
    stores = db.relationship(
        'Store',
        secondary='coupon_template_store',
        backref=db.backref('coupon_templates', lazy='dynamic'),
        order_by='Store.code',
    )

    issued = db.relationship(
        'UserCoupon', backref='template', lazy='dynamic',
        cascade='all, delete-orphan',
    )

    @property
    def is_expired(self):
        """过期了没——**每次现算**，不依赖库里任何字段

        和 `UserCoupon.is_expired` 同一套判断，这里放在模板上是因为
        「这张券过没过期」本来就是模板（有效期）的属性，券只是继承这个结论。
        """
        valid_to = _as_aware(self.valid_to)
        return valid_to is not None and valid_to < datetime.now(timezone.utc)

    @property
    def not_started(self):
        """还没到生效时间——和过期一样是算出来的"""
        valid_from = _as_aware(self.valid_from)
        return valid_from is not None and valid_from > datetime.now(timezone.utc)

    @property
    def is_all_stores(self):
        return len(self.stores) == 0

    def usable_at(self, store_id):
        """这家店能不能用——空 = 全公司通用"""
        if not self.stores:
            return True
        return any(store.id == store_id for store in self.stores)

    def discount_for(self, amount):
        """这个金额能用它抵多少（不算门槛，门槛由调用方判）"""
        amount = Decimal(amount)
        if self.type == self.TYPE_FULL_CUT:
            # 满减不能减成负数（订单 5 元、券减 20 的话只能减到 0）
            return min(Decimal(self.value), amount)
        # 折扣：减掉的部分 = 原价 × (1 − 折扣率)
        return (amount * (Decimal('1') - Decimal(self.value))).quantize(Decimal('0.01'))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'type_label': self.TYPE_LABELS.get(self.type, self.type),
            'value': float(self.value),
            'min_amount': float(self.min_amount),
            'valid_from': self.valid_from.isoformat() if self.valid_from else None,
            'valid_to': self.valid_to.isoformat() if self.valid_to else None,
            'total_quantity': self.total_quantity,
            'is_claimable': self.is_claimable,
            'per_member_limit': self.per_member_limit,
            'status': self.status,
            'status_label': self.STATUS_LABELS.get(self.status, self.status),
            'store_ids': [store.id for store in self.stores],
            'store_names': [store.name for store in self.stores],
            'is_all_stores': self.is_all_stores,
            'issued_count': self.issued.count(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class UserCoupon(BaseModel):
    """用户持券：某个会员手里的一张券"""
    __tablename__ = 'user_coupon'

    # ---------- 状态 ----------
    # **只有两个值**：过期是算出来的，不写库——理由见模块开头
    STATUS_UNUSED = 'unused'
    STATUS_USED = 'used'

    template_id = db.Column(
        db.Integer, db.ForeignKey('coupon_template.id', ondelete='RESTRICT'),
        nullable=False, index=True,
    )
    member_id = db.Column(
        db.Integer, db.ForeignKey('member.id', ondelete='RESTRICT'),
        nullable=False, index=True,
    )
    member = db.relationship('Member', backref=db.backref('coupons', lazy='dynamic'))

    status = db.Column(db.String(20), nullable=False, default=STATUS_UNUSED, index=True)

    received_at = db.Column(db.DateTime, nullable=False,
                            default=lambda: datetime.now(timezone.utc))
    # 谁发的（NULL = 顾客自己领的）
    issued_by_id = db.Column(
        db.Integer, db.ForeignKey('staff.id', ondelete='SET NULL'), nullable=True,
    )
    issued_by_name = db.Column(db.String(50), nullable=False, default='')

    # ---------- 用掉的时候 ----------
    used_at = db.Column(db.DateTime, nullable=True)
    used_order_id = db.Column(
        db.Integer, db.ForeignKey('order.id', ondelete='RESTRICT'), nullable=True, index=True,
    )
    # 核销门店：券可能全公司通用，但要能查出「在哪家店用的」
    used_store_id = db.Column(
        db.Integer, db.ForeignKey('store.id', ondelete='RESTRICT'), nullable=True,
    )

    order = db.relationship('Order', backref=db.backref('used_coupons', lazy='dynamic'))

    # 过期/未生效直接问模板——有效期本来就是模板的属性，券只是继承这个结论
    @property
    def is_expired(self):
        return self.template.is_expired

    @property
    def not_started(self):
        return self.template.not_started

    @property
    def display_status(self):
        """给人看的状态：未使用 / 已使用 / 已过期 / 未生效

        库里只存「未使用 / 已使用」两种，另外两种是算出来的。
        """
        if self.status == self.STATUS_USED:
            return self.STATUS_USED
        if self.is_expired:
            return 'expired'
        if self.not_started:
            return 'not_started'
        return self.STATUS_UNUSED

    def to_dict(self):
        status = self.display_status
        labels = {'unused': '未使用', 'used': '已使用',
                  'expired': '已过期', 'not_started': '未生效'}
        return {
            'id': self.id,
            'template_id': self.template_id,
            'template_name': self.template.name,
            'template_type': self.template.type,
            'template_type_label': self.template.TYPE_LABELS.get(
                self.template.type, self.template.type),
            'value': float(self.template.value),
            'min_amount': float(self.template.min_amount),
            'member_id': self.member_id,
            'status': status,
            'status_label': labels[status],
            'valid_to': (self.template.valid_to.isoformat()
                         if self.template.valid_to else None),
            'received_at': self.received_at.isoformat() if self.received_at else None,
            'issued_by_name': self.issued_by_name,
            'used_at': self.used_at.isoformat() if self.used_at else None,
            'used_store_id': self.used_store_id,
        }
