from marshmallow import Schema, fields, validate


class StoreMenuQuerySchema(Schema):
    """门店菜单的查询参数（这个接口不分页——一家店的菜单要一次看全）"""

    category_id = fields.Integer(required=False, metadata={'description': '只看某个分类'})
    search = fields.String(required=False, metadata={'description': '按菜品名称搜索'})


class StoreDishUpdateSchema(Schema):
    """设置某门店对某道菜的覆盖

    三个字段都可选，只传要改的。语义上这是「upsert」：没有覆盖记录就建一条。

    注意这里**不能**用 load_default=None：那样「没传这个字段」和「传了 null」
    会变成同一个值，而这两件事语义完全不同——
      不传 price  = 别动价格
      传 price:null = 改回用菜品基础价（取消本店覆盖）
    不设 load_default 时，没传的字段根本不出现在 data 里，就能区分了。
    """

    price = fields.Decimal(
        allow_none=True,
        places=2,
        validate=validate.Range(min=0),
        metadata={'description': '本店售价；传 null 表示取消覆盖、改回菜品基础价'},
    )
    is_available = fields.Boolean(
        allow_none=True,
        metadata={'description': '本店是否上架这道菜'},
    )
    daily_limit = fields.Integer(
        allow_none=True,
        validate=validate.Range(min=1, error='每日限量至少是 1；不限量请传 null'),
        metadata={'description': '每日限量；传 null 表示不限量'},
    )
