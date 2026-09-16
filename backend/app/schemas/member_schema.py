"""会员 + 储值的请求 schema"""
from decimal import Decimal

from marshmallow import Schema, fields, validate


class MemberCreateSchema(Schema):
    """员工代客办卡（将来顾客端微信登录也会走同一套校验）

    「手机号和 openid 至少得有一个」这个约束在 `MemberService._assert_identity`
    里判，不在这儿——schema 只管格式，不管业务规则。
    """

    mobile = fields.Str(
        allow_none=True,
        load_default=None,
        validate=validate.Length(min=6, max=20),
        metadata={'description': '手机号；和微信 openid 至少填一个'},
    )
    openid = fields.Str(
        allow_none=True,
        load_default=None,
        validate=validate.Length(max=64),
        metadata={'description': '微信 openid；一般由顾客端登录带出来，手工办卡不用填'},
    )
    nickname = fields.Str(load_default='', validate=validate.Length(max=32))
    avatar = fields.Str(load_default='', validate=validate.Length(max=255))


class RechargeSchema(Schema):
    """充值：`principal` 是顾客真掏的钱，`bonus` 是送的

    「充 100 送 20」= `principal=100, bonus=20`。两者进不同的科目——
    本金是收入、赠送是营销成本，报表上要分得开。
    """

    principal = fields.Decimal(
        required=True,
        places=2,
        validate=validate.Range(min=0),
        metadata={'description': '本金：顾客真掏的钱，能退'},
    )
    bonus = fields.Decimal(
        load_default=Decimal('0'),
        places=2,
        validate=validate.Range(min=0),
        metadata={'description': '赠送：充值送的，不退，扣款时先花掉'},
    )
    remark = fields.Str(load_default='', validate=validate.Length(max=255))
