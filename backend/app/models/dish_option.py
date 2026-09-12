"""规格组 / 规格选项（两层结构）

以牛肉面（¥15）为例：

    规格组「份量」(单选，必选)  → 中份 +0 / 大份 +3
    规格组「辣度」(单选，必选)  → 微辣 +0 / 中辣 +0 / 特辣 +0
    规格组「加料」(多选，非必选) → 加蛋 +2 / 加牛肉 +6

    顾客选：大份 + 特辣 + 加蛋  →  15 + 3 + 2 = ¥20
    订单明细记下：牛肉面(大份,特辣,加蛋) ¥20

**为什么不直接在菜品描述里写一行字？** 因为要统计「加蛋卖了多少份」、
要控「加牛肉」的库存、要统一给某个加料改价——写死成文字，这些全做不了。
选项带自己的 id，订单明细才能指回来说清楚它到底是哪个。
"""
from backend.app.extensions import db
from backend.app.models.base import BaseModel


class DishOptionGroup(BaseModel):
    __tablename__ = 'dish_option_group'

    TYPE_SINGLE = 'single'
    TYPE_MULTIPLE = 'multiple'
    TYPE_LABELS = {
        TYPE_SINGLE: '单选',
        TYPE_MULTIPLE: '多选',
    }

    dish_id = db.Column(
        db.Integer, db.ForeignKey('dish.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )

    name = db.Column(db.String(32), nullable=False)   # 份量 / 辣度 / 加料
    selection_type = db.Column(db.String(16), nullable=False, default=TYPE_SINGLE)
    # 必选：单选组必选 = 必须选一个；多选组必选 = 至少要选一个
    is_required = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    options = db.relationship(
        'DishOption',
        backref='group',
        order_by='DishOption.sort_order',
        cascade='all, delete-orphan',
    )

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'selection_type': self.selection_type,
            'selection_type_label': self.TYPE_LABELS.get(
                self.selection_type, self.selection_type
            ),
            'is_required': self.is_required,
            'sort_order': self.sort_order,
            'options': [option.to_dict() for option in self.options],
        }


class DishOption(BaseModel):
    __tablename__ = 'dish_option'

    group_id = db.Column(
        db.Integer, db.ForeignKey('dish_option_group.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )

    name = db.Column(db.String(32), nullable=False)   # 大份 / 微辣 / 加蛋
    # 附加价：可以是 0（微辣和特辣一样价），所以 0 是有意义的取值，不是「没填」
    extra_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'extra_price': float(self.extra_price) if self.extra_price is not None else 0,
            'sort_order': self.sort_order,
        }
