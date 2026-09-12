from marshmallow import Schema, fields, validate


class CategoryCreateSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=32))
    icon = fields.Str(
        load_default='',
        validate=validate.Length(max=255),
        metadata={'description': '图标：emoji 或图片地址都行'},
    )
    is_visible = fields.Boolean(
        load_default=True,
        metadata={'description': '关掉之后该分类不出现在菜单里'},
    )
    sort_order = fields.Integer(
        load_default=None,
        allow_none=True,
        metadata={'description': '排序；不传则自动排在最后'},
    )
    store_ids = fields.List(
        fields.Integer(),
        load_default=list,
        metadata={'description': '适用门店 id；空数组 = 全公司通用'},
    )


class CategoryUpdateSchema(Schema):
    """只传需要改的字段"""

    name = fields.Str(validate=validate.Length(min=1, max=32))
    icon = fields.Str(validate=validate.Length(max=255))
    is_visible = fields.Boolean()
    sort_order = fields.Integer()
    store_ids = fields.List(fields.Integer())
