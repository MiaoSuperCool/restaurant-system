"""菜品的请求参数 schema

规格组/选项是嵌套的：整个菜品的规格结构一次性提交，后端按 id 对齐地
原地更新（见 DishService._sync_options），不是全删重建——
订单明细会引用选项 id，重建会让历史订单指到不存在的选项上。
"""
from decimal import Decimal

from marshmallow import Schema, fields, validate

from backend.app.models.dish import Dish
from backend.app.models.dish_option import DishOptionGroup
from backend.app.schemas.query_schema import PageQuerySchema
from backend.app.schemas.validators import one_of


class DishQuerySchema(PageQuerySchema):
    """菜品列表的查询参数：在通用分页/搜索之上多一个分类筛选"""

    category_id = fields.Integer(
        required=False,
        metadata={'description': '只看某个分类下的菜品'},
    )


class DishOptionSchema(Schema):
    id = fields.Integer(
        load_default=None,
        allow_none=True,
        metadata={'description': '已存在的选项才传 id；新选项不传'},
    )
    name = fields.Str(required=True, validate=validate.Length(min=1, max=32))
    extra_price = fields.Decimal(
        load_default=Decimal('0'),
        places=2,
        validate=validate.Range(min=0),
        metadata={'description': '附加价；0 是有意义的取值（微辣和特辣同价）'},
    )
    # 不传时留 None，由 service 按数组中出现的先后顺序补——不能给 0 兜底，
    # 否则每个选项都是 0，排序全平，运营调的顺序存不下来
    sort_order = fields.Integer(load_default=None, allow_none=True)


class DishOptionGroupSchema(Schema):
    id = fields.Integer(load_default=None, allow_none=True)
    name = fields.Str(required=True, validate=validate.Length(min=1, max=32))
    selection_type = fields.Str(
        load_default=DishOptionGroup.TYPE_SINGLE,
        validate=one_of(DishOptionGroup.TYPE_LABELS),
    )
    is_required = fields.Boolean(load_default=True)
    sort_order = fields.Integer(load_default=None, allow_none=True)
    # 一个组至少要有一个选项，否则顾客点单时会卡在一个没得选的必选组上
    options = fields.List(
        fields.Nested(DishOptionSchema),
        load_default=list,
        validate=validate.Length(min=1, error='每个规格组至少要有一个选项'),
    )


class DishCreateSchema(Schema):
    category_id = fields.Integer(required=True)
    name = fields.Str(required=True, validate=validate.Length(min=1, max=64))
    image = fields.Str(load_default='', validate=validate.Length(max=255))
    description = fields.Str(load_default='', validate=validate.Length(max=255))
    base_price = fields.Decimal(
        load_default=Decimal('0'),
        places=2,
        validate=validate.Range(min=0),
        metadata={'description': '基础价；门店可在「门店菜品」里覆盖'},
    )
    status = fields.Str(load_default=Dish.STATUS_ACTIVE, validate=one_of(Dish.STATUS_LABELS))
    sort_order = fields.Integer(load_default=None, allow_none=True)
    option_groups = fields.List(fields.Nested(DishOptionGroupSchema), load_default=list)


class DishUpdateSchema(Schema):
    """只传需要改的字段；option_groups 传了就整体对齐更新，不传表示不动"""

    category_id = fields.Integer()
    name = fields.Str(validate=validate.Length(min=1, max=64))
    image = fields.Str(validate=validate.Length(max=255))
    description = fields.Str(validate=validate.Length(max=255))
    base_price = fields.Decimal(places=2, validate=validate.Range(min=0))
    status = fields.Str(validate=one_of(Dish.STATUS_LABELS))
    sort_order = fields.Integer()
    option_groups = fields.List(fields.Nested(DishOptionGroupSchema))
