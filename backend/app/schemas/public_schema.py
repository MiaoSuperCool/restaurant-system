"""顾客端接口的参数 schema

顾客不是内部员工，**不进权限码体系**——设计文档明确说了「顾客不是一个内部角色，
它是另一套账号体系」。所以这套接口不挂 @permission_required，
一期也还没有会员登录（那是二期）。

代价是这些接口对任何人开放。已知道的缺口写在文件末尾。
"""
from marshmallow import Schema, fields, validate

from backend.app.models.order import Order
from backend.app.models.payment import Payment
from backend.app.schemas.validators import one_of


class PublicOrderItemSchema(Schema):
    """顾客点的一行

    和内部一样**只收菜品和数量，不收价格**。顾客端更该如此——
    这是唯一能防止「前端改价」的地方。
    """

    dish_id = fields.Integer(required=True)
    quantity = fields.Integer(
        required=True,
        validate=validate.Range(min=1, max=99, error='数量必须在 1~99 之间'),
    )
    option_ids = fields.List(fields.Integer(), load_default=list)


class PublicOrderCreateSchema(Schema):
    store_id = fields.Integer(required=True)
    source = fields.Str(
        load_default=Order.SOURCE_DINE_IN,
        validate=one_of(Order.SOURCE_LABELS),
    )
    remark = fields.Str(load_default='', validate=validate.Length(max=255))
    items = fields.List(
        fields.Nested(PublicOrderItemSchema),
        required=True,
        validate=validate.Length(min=1, error='订单至少要有一道菜'),
    )
    # 要用哪张券。**不传就是不用券**——顾客端不登录也能下单，
    # 没登录的人手里本来就没有券（券挂在会员头上）。
    #
    # 名字带 `user_` 是为了和「券模板」区分开：模板是"满 30 减 5"那条规则，
    # 这里是这个人手里那张具体的券（`UserCoupon` 的 id）
    user_coupon_id = fields.Integer(
        required=False,
        metadata={'description': '用哪张券（我的券包里的 id）；不传 = 不用券'},
    )


class PublicPaySchema(Schema):
    """模拟支付

    真实对接微信支付时，这里应该什么都不收——金额由服务端根据订单算，
    客户端只负责调起收银台。现在收 method 只是因为要记「用什么方式付的」。
    """

    method = fields.Str(
        load_default=Payment.METHOD_WECHAT,
        validate=one_of(Payment.METHOD_LABELS),
    )


# ---------------------------------------------------------------------------
# 已知缺口（一期有意留下，记在这里免得忘）
#
# 1. **没有限流**：任何人都能不停调下单接口造垃圾订单。真实环境要按 IP /
#    设备指纹限流，或者至少要有个图形验证码。
# 2. **没有防重复提交**：顾客手抖连点两下会下两单。真实环境该用幂等键
#    （客户端生成一个 request_id，服务端认这个 id）。
# 3. **没有会员关联**：订单的 member_id 永远是空的，二期做完会员登录才填。
# ---------------------------------------------------------------------------
