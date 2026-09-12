"""门店菜品：多店定价就靠这张表

**菜品基础（dish）和门店（store）是解耦的**：名称、图片、描述、分类属于
全公司；「这家店卖不卖这道菜、卖多少钱、一天限几份」全在这张关联表里覆盖。

设计文档「必须守住的第 5 条」说的就是这个——别在菜品上写死价格。

--------------------------------------------------------------------------
一条重要约定：**没有行 = 用默认值**

不是每家店每道菜都有一行，而是「这家店对这道菜做了特殊设置」才有一行。
没有行的时候按默认理解：用菜品的基础价、可以卖、不限量。

为什么这么设计：6 家店 × 50 道菜 = 300 行，如果要求每家店每道菜都得有行
才能卖，等于运营每加一道菜要手动上架 6 次。默认可用的话，新菜自动出现在
所有门店，哪家店不想卖再去单独下架。

代价是「查某道菜在某店的价格」要合并两层——所以有了 effective_price 这个
property，调用方别自己去判断 price 是不是 None。
"""
from backend.app.extensions import db
from backend.app.models.base import BaseModel


class StoreDish(BaseModel):
    __tablename__ = 'store_dish'

    # 两边都 RESTRICT：门店还有菜单配置、或菜品还在某店菜单里，都不许直接删
    store_id = db.Column(
        db.Integer, db.ForeignKey('store.id', ondelete='RESTRICT'),
        nullable=False, index=True,
    )
    dish_id = db.Column(
        db.Integer, db.ForeignKey('dish.id', ondelete='RESTRICT'),
        nullable=False, index=True,
    )

    store = db.relationship('Store', backref=db.backref('store_dishes', lazy='dynamic'))
    dish = db.relationship('Dish', backref=db.backref('store_dishes', lazy='dynamic'))

    # 本店覆盖价；NULL = 用菜品基础价
    price = db.Column(db.Numeric(10, 2), nullable=True)
    # 本店是否上架这道菜
    is_available = db.Column(db.Boolean, nullable=False, default=True)
    # 每日限量；NULL = 不限量。
    # 注意：这里只是「配置的上限」，当天已卖多少要靠订单统计，
    # 真正的限购校验等订单域建好之后接上。
    daily_limit = db.Column(db.Integer, nullable=True)

    # 一家店对一道菜只有一条覆盖记录
    __table_args__ = (
        db.UniqueConstraint('store_id', 'dish_id', name='uq_store_dish'),
    )

    @property
    def has_price_override(self):
        return self.price is not None

    @property
    def effective_price(self):
        """本店实际售价：覆盖价优先，没覆盖就用菜品基础价"""
        return self.price if self.price is not None else self.dish.base_price

    def to_dict(self):
        return {
            'id': self.id,
            'store_id': self.store_id,
            'dish_id': self.dish_id,
            'price': float(self.price) if self.price is not None else None,
            'is_available': self.is_available,
            'daily_limit': self.daily_limit,
            'has_price_override': self.has_price_override,
        }
