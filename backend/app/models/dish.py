"""菜品基础（全公司同一套）

**和门店解耦**：这张表里没有「哪家店卖多少钱」——名称、图片、描述、分类
是全公司共用的，各店的价格和上下架在 store_dish（门店菜品）里覆盖。
多店定价就靠那张关联表，别在这里写死价格。
"""
from backend.app.extensions import db
from backend.app.models.base import BaseModel


class Dish(BaseModel):
    __tablename__ = 'dish'

    # 菜品本身的状态（公司级总开关）。
    # 某家店单独下架某个菜，改的是 store_dish.is_available，不是这里。
    STATUS_ACTIVE = 'active'
    STATUS_DISCONTINUED = 'discontinued'
    STATUS_LABELS = {
        STATUS_ACTIVE: '在售',
        STATUS_DISCONTINUED: '已停售',
    }

    # RESTRICT：分类下还有菜品时不许删分类（分类是引用，不是从属）
    category_id = db.Column(
        db.Integer, db.ForeignKey('category.id', ondelete='RESTRICT'),
        nullable=False, index=True,
    )
    category = db.relationship('Category', backref=db.backref('dishes', lazy='dynamic'))

    name = db.Column(db.String(64), nullable=False, index=True)
    image = db.Column(db.String(255), nullable=False, default='')
    description = db.Column(db.String(255), nullable=False, default='')

    # 基础价：门店没在 store_dish 里覆盖价格时用它
    base_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    status = db.Column(db.String(20), nullable=False, default=STATUS_ACTIVE)
    sort_order = db.Column(db.Integer, nullable=False, default=0, index=True)

    # 规格组：从属关系，菜品删了规格跟着走
    option_groups = db.relationship(
        'DishOptionGroup',
        backref='dish',
        order_by='DishOptionGroup.sort_order',
        cascade='all, delete-orphan',
    )

    def to_dict(self, with_options=False):
        data = {
            'id': self.id,
            'category_id': self.category_id,
            'category_name': self.category.name if self.category else None,
            'name': self.name,
            'image': self.image,
            'description': self.description,
            # 转 float 只为展示方便；金额计算一律在后端用 Decimal，不要信任前端的浮点
            'base_price': float(self.base_price) if self.base_price is not None else 0,
            'status': self.status,
            'status_label': self.STATUS_LABELS.get(self.status, self.status),
            'sort_order': self.sort_order,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        if with_options:
            data['option_groups'] = [group.to_dict() for group in self.option_groups]
        return data
