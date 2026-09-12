from marshmallow import Schema, fields, validate

from backend.app.models.groupon_voucher import GrouponVoucher
from backend.app.schemas.validators import one_of


class GrouponVerifySchema(Schema):
    """核销团购券

    目前券码是收银员手工输入的，平台也是手选的——**没有真的对接美团/抖音**。
    真对接时这里会多一步「调平台接口验证券码有效性」，金额也不该由人工填。
    """

    code = fields.Str(
        required=True,
        validate=validate.Length(min=4, max=64),
        metadata={'description': '券码；全局唯一，同一张券不能核销两次'},
    )
    platform = fields.Str(
        load_default=GrouponVoucher.PLATFORM_MEITUAN,
        validate=one_of(GrouponVoucher.PLATFORM_LABELS),
    )
    amount = fields.Decimal(
        required=True,
        places=2,
        validate=validate.Range(min=0.01, error='券面额必须大于 0'),
    )
