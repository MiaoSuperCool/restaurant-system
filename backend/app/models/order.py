"""订单 / 订单明细 / 明细里选的规格

三张表的关系：

    Order 订单
      └── OrderItem 明细（一份牛肉面 ×2）
            └── OrderItemOption 这份明细选了哪些规格（大份 / 加蛋）

--------------------------------------------------------------------------
两个容易做错的地方，这里都按设计文档处理了：

**1. 明细要存快照，但也要保留引用**

菜名、单价在下单那一刻就固定下来（快照字段），因为运营明天可能把「牛肉面」
改名成「红烧牛肉面」、或者涨价，历史订单必须还原当时的样子。
但 dish_id 和 option 的引用也要留着——不然「加蛋卖了多少份」这类统计就
做不了（这正是规格组要建两层表的原因）。

快照负责「当时是什么样」，引用负责「统计和分析」。两个都要。

**2. 金额一律后端算，永远不信前端传来的价格**

下单接口只收 dish_id / quantity / option_ids，价格由后端查门店菜品表
现算。前端传什么价格都不看——这是收银系统最基本的安全要求。
"""
from backend.app.extensions import db
from backend.app.models.base import BaseModel


class Order(BaseModel):
    __tablename__ = 'order'

    # ---------- 来源 ----------
    SOURCE_DINE_IN = 'dine_in'      # 堂食
    SOURCE_TAKEAWAY = 'takeaway'    # 自取
    SOURCE_DELIVERY = 'delivery'    # 外卖
    SOURCE_LABELS = {
        SOURCE_DINE_IN: '堂食',
        SOURCE_TAKEAWAY: '自取',
        SOURCE_DELIVERY: '外卖',
    }

    # ---------- 状态 ----------
    # 流转：pending → accepted → completed
    #        pending/accepted → cancelled
    STATUS_PENDING = 'pending'        # 待接单
    STATUS_ACCEPTED = 'accepted'      # 已接单（在做）
    STATUS_COMPLETED = 'completed'    # 已完成
    STATUS_CANCELLED = 'cancelled'    # 已取消
    STATUS_LABELS = {
        STATUS_PENDING: '待接单',
        STATUS_ACCEPTED: '已接单',
        STATUS_COMPLETED: '已完成',
        STATUS_CANCELLED: '已取消',
    }
    # 允许的状态流转，别处判断时统一查这张表，不要各写各的 if
    STATUS_FLOW = {
        STATUS_PENDING: (STATUS_ACCEPTED, STATUS_CANCELLED),
        STATUS_ACCEPTED: (STATUS_COMPLETED, STATUS_CANCELLED),
        STATUS_COMPLETED: (),
        STATUS_CANCELLED: (),
    }

    # 单号：门店码-日期-当日序号，如 S001-20260912-0001。
    # 做成可读的而不是 UUID——顾客电话里报单号、店员在屏幕上一眼找单子都要用
    order_no = db.Column(db.String(32), unique=True, nullable=False, index=True)

    # 顾客端查订单的凭据。
    # 单号是可读的、**也是可以猜的**（S001-20260912-0001、0002、0003……），
    # 如果只凭单号就能查详情，遍历一遍就看到了别人点了什么、花了多少。
    # 所以下单时另发一个随机串，查详情要同时带上单号和它。
    query_token = db.Column(db.String(32), nullable=False, default='', index=True)

    store_id = db.Column(
        db.Integer, db.ForeignKey('store.id', ondelete='RESTRICT'),
        nullable=False, index=True,
    )
    store = db.relationship('Store', backref=db.backref('orders', lazy='dynamic'))

    # 会员 id：一期还没有会员表（二期做），顾客下单时先留空。
    # 这里不加外键，等二期建表时再补迁移
    member_id = db.Column(db.Integer, nullable=True, index=True)

    source = db.Column(db.String(20), nullable=False, default=SOURCE_DINE_IN)
    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING, index=True)

    # ---------- 金额（一律 Decimal，不用浮点）----------
    total_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)      # 原价合计
    discount_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)   # 优惠合计
    payable_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)    # 应付 = 原价 - 优惠
    paid_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)       # 已收（可能分多笔）
    # 已退。有了它才答得出「这单还能退多少」——退款要校验的可退金额
    # = paid_amount − refunded_amount，两个数都得留着
    refunded_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    # ---------- 操作人 ----------
    # 语义是「实际操作人」而不是「登录账号」：
    # 服务员用公用账号登录时，下单要先选「我是谁」，记的是那个人——
    # 否则出了事追责无门。登录账号本身在审计日志里能查到。
    # 顾客自己下单时为空。
    operator_id = db.Column(
        db.Integer, db.ForeignKey('staff.id', ondelete='SET NULL'), nullable=True,
    )
    operator_name = db.Column(db.String(50), nullable=False, default='')

    remark = db.Column(db.String(255), nullable=False, default='')

    items = db.relationship(
        'OrderItem', backref='order',
        order_by='OrderItem.id',
        cascade='all, delete-orphan',
    )
    payments = db.relationship(
        'Payment', backref='order',
        order_by='Payment.id',
        cascade='all, delete-orphan',
    )

    @property
    def is_paid(self):
        """钱收够了没有——不是「有没有支付记录」（可能只付了一部分）"""
        return self.paid_amount >= self.payable_amount

    @property
    def refundable_amount(self):
        """还能退多少：收到的钱减去已经退掉的"""
        return self.paid_amount - self.refunded_amount

    @property
    def net_amount(self):
        """这单实际留下多少钱。营业收入统计算的是这个，不是 paid_amount"""
        return self.paid_amount - self.refunded_amount

    def can_transition_to(self, status):
        return status in self.STATUS_FLOW.get(self.status, ())

    def to_dict(self, with_items=False):
        data = {
            'id': self.id,
            'order_no': self.order_no,
            'query_token': self.query_token,
            'store_id': self.store_id,
            'store_name': self.store.name if self.store else None,
            'member_id': self.member_id,
            'source': self.source,
            'source_label': self.SOURCE_LABELS.get(self.source, self.source),
            'status': self.status,
            'status_label': self.STATUS_LABELS.get(self.status, self.status),
            'total_amount': float(self.total_amount),
            'discount_amount': float(self.discount_amount),
            'payable_amount': float(self.payable_amount),
            'paid_amount': float(self.paid_amount),
            'refunded_amount': float(self.refunded_amount),
            'refundable_amount': float(self.refundable_amount),
            'is_paid': self.is_paid,
            'operator_id': self.operator_id,
            'operator_name': self.operator_name,
            'remark': self.remark,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if with_items:
            data['items'] = [item.to_dict() for item in self.items]
            data['payments'] = [payment.to_dict() for payment in self.payments]
            # 退款单也带上：订单详情是「这单发生过什么」的唯一入口，
            # 收款和退款分开看会很别扭
            data['refunds'] = [refund.to_dict(with_txns=True) for refund in self.refunds]
        return data


class OrderItem(BaseModel):
    """订单明细的一行：一道菜 + 数量 + 当时的价格"""

    __tablename__ = 'order_item'

    # CASCADE：明细从属于订单，订单没了明细也没有独立意义
    order_id = db.Column(
        db.Integer, db.ForeignKey('order.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    # RESTRICT：菜品被订单引用过就不许删（历史订单得认得它）
    dish_id = db.Column(
        db.Integer, db.ForeignKey('dish.id', ondelete='RESTRICT'),
        nullable=False, index=True,
    )

    # ---------- 下单那一刻的快照 ----------
    # 菜名和单价都可能被改，历史订单要还原当时的样子
    dish_name = db.Column(db.String(64), nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)   # 单价（已含规格加价）
    quantity = db.Column(db.Integer, nullable=False, default=1)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)     # 小计 = 单价 × 数量

    # 规格的文本快照，给人看的：「大份,特辣,加蛋」
    options_text = db.Column(db.String(255), nullable=False, default='')

    options = db.relationship(
        'OrderItemOption', backref='item',
        order_by='OrderItemOption.id',
        cascade='all, delete-orphan',
    )

    def to_dict(self):
        return {
            'id': self.id,
            'dish_id': self.dish_id,
            'dish_name': self.dish_name,
            'unit_price': float(self.unit_price),
            'quantity': self.quantity,
            'subtotal': float(self.subtotal),
            'options_text': self.options_text,
            'options': [option.to_dict() for option in self.options],
        }


class OrderItemOption(BaseModel):
    """这份明细选了哪个规格选项

    为什么不留一行文本就完事：设计文档要求「统计加蛋卖了多少份」「控加牛肉的
    库存」，纯文本做不到。所以既存快照名（给人看），也留 option 引用（给统计）。

    dish_option 用 RESTRICT：已经被订单点过的选项不能删——删了这条统计就断链。
    停用某个加料应该用别的方式（下架/改名保留），不能直接删。
    """

    __tablename__ = 'order_item_option'

    order_item_id = db.Column(
        db.Integer, db.ForeignKey('order_item.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    # 保留引用供统计：加蛋到底卖了多少份
    dish_option_id = db.Column(
        db.Integer, db.ForeignKey('dish_option.id', ondelete='RESTRICT'),
        nullable=False, index=True,
    )

    # 快照
    dish_option_group_name = db.Column(db.String(32), nullable=False, default='')
    dish_option_name = db.Column(db.String(32), nullable=False, default='')
    extra_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'dish_option_id': self.dish_option_id,
            'group_name': self.dish_option_group_name,
            'name': self.dish_option_name,
            'extra_price': float(self.extra_price),
        }
