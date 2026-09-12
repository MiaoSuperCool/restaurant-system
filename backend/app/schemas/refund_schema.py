from marshmallow import Schema, fields, validate

from backend.app.models.refund import Refund, RefundTxn
from backend.app.schemas.query_schema import PageQuerySchema
from backend.app.schemas.validators import one_of


class RefundQuerySchema(PageQuerySchema):
    """退款列表的查询参数"""

    store_id = fields.Integer(required=False, metadata={'description': '按门店筛选'})
    status = fields.Str(required=False, validate=one_of(Refund.STATUS_LABELS))


class RefundCreateSchema(Schema):
    """发起退款申请

    金额上限由 service 层校验（不能超过订单的可退金额）——schema 不知道订单，
    所以这里只能做基础校验。
    """

    amount = fields.Decimal(
        required=True,
        places=2,
        validate=validate.Range(min=0.01, error='退款金额必须大于 0'),
    )
    reason = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=255, error='退款必须写原因——留痕的用途就在这里'),
    )
    type = fields.Str(
        load_default=Refund.TYPE_ONLINE,
        validate=one_of(Refund.TYPE_LABELS),
        metadata={'description': '线上退款 / 线下补录（钱已经用现金退了，事后补录）'},
    )


class RefundApproveSchema(Schema):
    """审批意见（批准和驳回都走这个，批准时可为空、驳回时必填由 service 校验）"""

    remark = fields.Str(
        load_default='',
        validate=validate.Length(max=255),
        metadata={'description': '审批意见；驳回时必填'},
    )


class RefundSettleSchema(Schema):
    """确认退款完成：钱真的出去了，记一条退款流水"""

    method = fields.Str(
        load_default=RefundTxn.METHOD_ORIGINAL,
        validate=one_of(RefundTxn.METHOD_LABELS),
    )
    transaction_no = fields.Str(
        load_default='',
        validate=validate.Length(max=64),
        metadata={'description': '第三方退款单号（微信退款单号）；现金留空'},
    )
