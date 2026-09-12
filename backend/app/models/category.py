"""菜品分类

为什么分类要单独建表，而不是在菜品表里放个字符串字段：
**分类本身有属性**——图标、是否显示、适用哪些门店、排序。运营主管日常要
增删分类、调顺序，这些都需要给它开功能。如果分类只是个写死的枚举
（就"主食/饮品/甜点"三个值、没有别的属性），那确实可以直接放字符串，
但餐饮的分类是天天被运营改的东西。
"""
from backend.app.extensions import db
from backend.app.models.base import BaseModel

# 分类的门店适用范围（多对多，纯关联表）。
# 一行都没有 = 全公司通用（默认）；有行 = 只在这些门店的菜单里显示。
# 两边都用 CASCADE：这是「配置」不是「业务数据」，门店或分类没了，配置自然消失。
category_store = db.Table(
    'category_store',
    db.Column('category_id', db.Integer,
              db.ForeignKey('category.id', ondelete='CASCADE'), primary_key=True),
    db.Column('store_id', db.Integer,
              db.ForeignKey('store.id', ondelete='CASCADE'), primary_key=True),
)


class Category(BaseModel):
    __tablename__ = 'category'

    name = db.Column(db.String(32), unique=True, nullable=False)
    # 图标：可以填 emoji（🍜），也可以填图片地址。一期先不做上传，填什么都行
    icon = db.Column(db.String(255), nullable=False, default='')
    is_visible = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0, index=True)

    # 适用门店：空 = 全公司通用
    stores = db.relationship(
        'Store',
        secondary='category_store',
        backref=db.backref('categories', lazy='dynamic'),
        order_by='Store.code',
    )

    @property
    def is_all_stores(self):
        return len(self.stores) == 0

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'icon': self.icon,
            'is_visible': self.is_visible,
            'sort_order': self.sort_order,
            'store_ids': [store.id for store in self.stores],
            'store_names': [store.name for store in self.stores],
            'is_all_stores': self.is_all_stores,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
