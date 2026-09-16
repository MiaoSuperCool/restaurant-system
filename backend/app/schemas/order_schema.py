from marshmallow import Schema, fields, validate

from backend.app.models.order import Order
from backend.app.models.payment import Payment
from backend.app.schemas.query_schema import PageQuerySchema
from backend.app.schemas.validators import one_of


class OrderQuerySchema(PageQuerySchema):
    """订单列表的查询参数"""

    store_id = fields.Integer(required=False, metadata={'description': '按门店筛选'})
    status = fields.Str(required=False, validate=one_of(Order.STATUS_LABELS))


class OrderItemCreateSchema(Schema):
    """下单时的一行明细

    注意这里**只收菜品和数量，不收价格**——价格一律后端查库现算。
    前端传什么金额都不看，这是收银系统最基本的安全要求。
    """

    dish_id = fields.Integer(required=True)
    quantity = fields.Integer(
        required=True,
        validate=validate.Range(min=1, max=99, error='数量必须在 1~99 之间'),
    )
    option_ids = fields.List(
        fields.Integer(),
        load_default=list,
        metadata={'description': '选中的规格选项 id；必选组不选会被拒'},
    )


class OrderCreateSchema(Schema):
    store_id = fields.Integer(required=True)
    source = fields.Str(
        load_default=Order.SOURCE_DINE_IN,
        validate=one_of(Order.SOURCE_LABELS),
    )
    remark = fields.Str(load_default='', validate=validate.Length(max=255))
    operator_id = fields.Integer(
        allow_none=True,
        metadata={'description': '实际操作人；服务员用公用账号下单时必须传'},
    )
    member_id = fields.Integer(
        allow_none=True,
        metadata={'description': '会员 id；**储值支付要靠它**。不传就是散客单'},
    )
    items = fields.List(
        fields.Nested(OrderItemCreateSchema),
        required=True,
        validate=validate.Length(min=1, error='订单至少要有一道菜'),
    )


class PaymentCreateSchema(Schema):
    """收银端收款：一次记一笔

    一个订单可以多次调用（组合支付、先定金后尾款），金额累加到 paid_amount。
    """

    method = fields.Str(required=True, validate=one_of(Payment.METHOD_LABELS))
    amount = fields.Decimal(
        required=True,
        places=2,
        validate=validate.Range(min=0.01, error='收款金额必须大于 0'),
    )
    transaction_no = fields.Str(
        load_default='',
        validate=validate.Length(max=64),
        metadata={'description': '第三方流水号（微信支付单号等）；现金留空。对账靠它'},
    )
