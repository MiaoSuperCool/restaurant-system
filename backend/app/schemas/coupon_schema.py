"""优惠券的请求 schema"""
from decimal import Decimal

from marshmallow import Schema, fields, validate

from backend.app.models.coupon import CouponTemplate
from backend.app.schemas.query_schema import PageQuerySchema
from backend.app.schemas.validators import one_of


class CouponTemplateQuerySchema(PageQuerySchema):
    """券模板列表的查询参数"""
    status = fields.Str(required=False, validate=one_of(CouponTemplate.STATUS_LABELS))


class CouponTemplateCreateSchema(Schema):
    """建券模板

    「折扣率必须在 (0,1) 之间」这条在 service 里判——它要看 `type` 和 `value`
    两个字段，而且**改的时候也得判**（单改 value 时类型还是旧的那个），
    放 schema 里只能覆盖「新建」这一种情况。
    """

    name = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=64),
        metadata={'description': '券名，顾客在小程序里看到的就是它'},
    )
    type = fields.Str(
        load_default=CouponTemplate.TYPE_FULL_CUT,
        validate=one_of(CouponTemplate.TYPE_LABELS),
        metadata={'description': 'full_cut 满减 / discount 折扣'},
    )
    value = fields.Decimal(
        required=True,
        places=2,
        validate=validate.Range(min=0),
        metadata={'description': '满减填「减多少钱」；折扣填折扣率（0.85 = 八五折）'},
    )
    min_amount = fields.Decimal(
        load_default=Decimal('0'),
        places=2,
        validate=validate.Range(min=0),
        metadata={'description': '门槛：满多少才能用；0 = 无门槛'},
    )
    valid_from = fields.DateTime(
        allow_none=True, load_default=None,
        metadata={'description': '生效时间；不传 = 立即生效'},
    )
    valid_to = fields.DateTime(
        allow_none=True, load_default=None,
        metadata={'description': '失效时间；不传 = 长期有效'},
    )
    total_quantity = fields.Integer(
        allow_none=True, load_default=None,
        validate=validate.Range(min=1),
        metadata={'description': '发放总量；不传 = 不限量。只约束「发」，不约束「用」'},
    )
    is_claimable = fields.Boolean(
        load_default=False,
        metadata={'description': '挂到券中心让顾客自己领。默认不挂——'
                                 '券默认是「运营圈了人才发」的东西'},
    )
    per_member_limit = fields.Integer(
        allow_none=True, load_default=None,
        validate=validate.Range(min=1, error='每人限领至少 1 张'),
        metadata={'description': '每人能自己领几张；不传 = 不限。'
                                 '**只管顾客自领**，不约束员工发券'},
    )
    status = fields.Str(
        load_default=CouponTemplate.STATUS_ACTIVE,
        validate=one_of(CouponTemplate.STATUS_LABELS),
    )
    store_ids = fields.List(
        fields.Integer(),
        load_default=list,
        metadata={'description': '适用门店 id；空数组 = 全公司通用'},
    )


class CouponTemplateUpdateSchema(Schema):
    """改券模板：只传要改的字段

    **`value` 允许传 null 吗？不允许。** 面额是券的立身之本，改成空没有意义。
    """

    name = fields.Str(validate=validate.Length(min=1, max=64))
    type = fields.Str(validate=one_of(CouponTemplate.TYPE_LABELS))
    value = fields.Decimal(places=2, validate=validate.Range(min=0))
    min_amount = fields.Decimal(places=2, validate=validate.Range(min=0))
    valid_from = fields.DateTime(allow_none=True)
    valid_to = fields.DateTime(allow_none=True)
    total_quantity = fields.Integer(allow_none=True, validate=validate.Range(min=1))
    is_claimable = fields.Boolean()
    per_member_limit = fields.Integer(allow_none=True, validate=validate.Range(min=1))
    status = fields.Str(validate=one_of(CouponTemplate.STATUS_LABELS))
    store_ids = fields.List(fields.Integer())


class CouponIssueSchema(Schema):
    """发券给一批会员"""

    template_id = fields.Integer(required=True)
    member_ids = fields.List(
        fields.Integer(),
        required=True,
        validate=validate.Length(min=1, error='至少要选一个会员'),
    )
    count = fields.Integer(
        load_default=1,
        validate=validate.Range(min=1, max=99),
        metadata={'description': '每个会员发几张'},
    )
    remark = fields.Str(load_default='', validate=validate.Length(max=255))


class CouponQuerySchema(PageQuerySchema):
    """会员券包的查询参数"""

    status = fields.Str(
        required=False,
        validate=one_of({'unused': '未使用', 'used': '已使用',
                         'expired': '已过期', 'not_started': '未生效'}),
        metadata={'description': '不传 = 全部。**expired / not_started 都是算出来的**，'
                                 '不是库里的状态；unused 不含这两种'},
    )


class UsableCouponQuerySchema(Schema):
    """「这单能用哪些券」的查询参数

    要门店和金额——四个条件里有两个（适用门店、满多少）得靠它们判。
    """

    store_id = fields.Integer(required=True)
    amount = fields.Decimal(
        required=True,
        places=2,
        validate=validate.Range(min=0),
        metadata={'description': '订单金额（算门槛用）'},
    )
