"""顾客端接口（小程序用）

**没有 @login_required，也没有 @permission_required。**

顾客不是内部员工——设计文档明确说了「顾客不是一个内部角色，它是另一套账号体系，
走微信登录，不进权限码体系」。一期连会员登录都还没有（二期的事），
所以这套接口对任何人开放。

也正因为如此，它面对的调用方是**不受信任的**：能改前端、能重放请求、
能遍历单号。所以这里做了三件内部接口不需要做的事：
1. 只返回营业中门店、只返回本店上架的菜
2. 查订单要「单号 + 随机令牌」，光有单号不行
3. 下单只收菜品和数量，价格一律服务端算

已知缺口（限流、防重复提交）记在 schemas/public_schema.py 末尾。
"""
from flask import jsonify, request
from flask_smorest import Blueprint

from backend.app.errors import BusinessError
from backend.app.schemas.public_schema import (
    PublicOrderCreateSchema,
    PublicPaySchema,
)
from backend.app.services import PublicService
from backend.app.utils.api_response import api_response

bp = Blueprint('public', __name__, url_prefix='/api/public')

# CSRF 保护的是「带着 cookie 的浏览器请求」——攻击者让受害者的浏览器偷偷发请求，
# 靠 cookie 冒充身份。顾客端不用 cookie（小程序发请求时也不带），没有这个风险，
# 所以豁免。**不要**把这个豁免加到任何依赖 session 的蓝图上。
from backend.app.extensions import csrf  # noqa: E402

csrf.exempt(bp)


@bp.get('/stores')
@bp.response(200, description='可点单的门店列表（只含营业中的）')
def stores():
    """顾客选店用的门店列表

    只返回营业中的门店——休息中和已停业的店点了也下不了单，不该出现。
    """
    return jsonify(api_response(
        success=True,
        data={
            'stores': [
                {
                    'id': store.id,
                    'code': store.code,
                    'name': store.name,
                    'address': store.address,
                    'phone': store.phone,
                    'store_type': store.store_type,
                    'store_type_label': store.TYPE_LABELS.get(store.store_type,
                                                             store.store_type),
                    # 顾客端首页那张门店卡片要显示的两项。
                    # **没有用 store.to_dict()**：那份是给员工看的，
                    # 里面有 run_mode（灰度切换）这种顾客不该看到的东西
                    'description': store.description,
                    'business_hours': store.business_hours,
                }
                for store in PublicService.get_open_stores()
            ]
        }
    ))


@bp.get('/stores/<int:store_id>/menu')
@bp.response(200, description='门店菜单（只含在售且本店上架的菜，带规格）')
def menu(store_id):
    """顾客看的菜单

    和内部菜单的区别：过滤掉本店下架的菜（收银台上要显示，因为店长要管理；
    顾客端不该出现）。价格是**本店实际价**，不是菜品基础价。
    """
    return jsonify(api_response(
        success=True,
        data={'dishes': PublicService.get_menu(store_id)}
    ))


@bp.post('/orders')
@bp.response(201, description='下单成功，返回订单和查询令牌')
@bp.arguments(PublicOrderCreateSchema, location='json')
def create_order(data):
    """顾客自助下单

    **只传菜品和数量，不传金额**——价格由服务端按本店实际价 + 规格加价现算。
    顾客端比内部端更该守这条：前端在顾客手里，改起来毫无成本。

    返回里带 `query_token`，顾客端要存下来——查订单详情靠它。

    菜品已停售/本店已下架 → 400；必选规格没选 → 400；门店不存在 → 404。
    """
    order = PublicService.create_order(data['store_id'], data)
    return jsonify(api_response(
        success=True,
        message=f'下单成功，单号 {order.order_no}',
        data=order.to_dict(with_items=True)
    )), 201


@bp.get('/orders/<order_no>')
@bp.response(200, description='订单详情')
def get_order(order_no):
    """凭「单号 + 查询令牌」查订单

    令牌从 query 参数传（`?token=xxx`），不做成请求头是为了小程序端写起来简单。
    代价是 URL 可能进日志——这个令牌只用于查自己的订单，泄露的影响有限；
    但对更敏感的场景（比如支付凭据）不该这么做。
    """
    order = PublicService.find_order(order_no, request.args.get('token', ''))
    return jsonify(api_response(
        success=True,
        data=order.to_dict(with_items=True)
    ))


@bp.post('/orders/<order_no>/pay')
@bp.response(200, description='支付完成')
@bp.arguments(PublicPaySchema, location='json')
def pay(data, order_no):
    """模拟支付

    **没有对接真实的微信支付**，只是把「钱付了」记下来。
    流水号带 MOCK 前缀，一眼能看出不是微信真实的单号。

    订单不存在/令牌不对 → 404；已取消 → 400；已付过 → 400。
    """
    order = PublicService.find_order(order_no, request.args.get('token', ''))
    payment = PublicService.pay(order, data['method'])
    return jsonify(api_response(
        success=True,
        message='支付成功',
        data={'payment': payment.to_dict(), 'order': order.to_dict()}
    ))


@bp.post('/orders/<order_no>/cancel')
@bp.response(200, description='已取消')
def cancel(order_no):
    """顾客自己取消订单

    只有「门店还没接单、也还没付款」时允许——门店已经开始做了，
    就不是顾客说取消就能取消的了。
    """
    order = PublicService.find_order(order_no, request.args.get('token', ''))
    try:
        PublicService.cancel_order(order)
    except BusinessError:
        raise
    return jsonify(api_response(
        success=True,
        message='订单已取消',
        data=order.to_dict()
    ))
