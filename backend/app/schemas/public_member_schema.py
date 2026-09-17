"""顾客端（登录 + 个人中心 + 券）的请求 schema"""
from marshmallow import Schema, fields, validate

from backend.app.schemas.query_schema import PageQuerySchema


class MemberCodeSchema(Schema):
    """要验证码"""

    mobile = fields.Str(
        required=True,
        validate=validate.Length(min=11, max=11, error='手机号是 11 位'),
        metadata={'description': '手机号；同一个号 60 秒内只能要一次'},
    )


class MemberLoginSchema(Schema):
    """验证码换 token"""

    mobile = fields.Str(required=True, validate=validate.Length(min=11, max=11))
    code = fields.Str(
        required=True,
        validate=validate.Length(min=4, max=8),
        metadata={'description': '验证码；5 分钟内有效、只能用一次、错 5 次作废'},
    )


class MemberCouponQuerySchema(PageQuerySchema):
    """我的券包"""

    status = fields.Str(
        required=False,
        validate=validate.OneOf(['unused', 'used', 'expired', 'not_started']),
        metadata={'description': '用法和员工端那个券包接口一致；不传 = 全部'},
    )
