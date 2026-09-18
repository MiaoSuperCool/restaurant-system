"""顾客端：个人中心 + 券（都要登录）

**这是「顾客登录之后才能看的那一摊」**：我的账户、我的券包、券中心。

和 `api/public.py`（门店/菜单/下单，不要登录）分开，是因为这两类接口的信任级别不一样：
那边对任何人开放，所以只返回营业中的门店、查订单要令牌；这边每一行数据都是
「本人的」，靠 `@member_required` 从 token 认人，**认出来之后所有查询都带上
`member_id`**——顾客 A 拿不到顾客 B 的任何东西，这一点不靠前端。

顾客不进权限码体系（设计文档第 3 条），所以这里没有 `@permission_required`，
只有「这条数据是不是你的」。
"""
from flask import current_app, g, jsonify
from flask_smorest import Blueprint

from backend.app.extensions import csrf
from backend.app.schemas.coupon_schema import UsableCouponQuerySchema
from backend.app.schemas.public_member_schema import MemberCouponQuerySchema
from backend.app.services import CouponService
from backend.app.services.member_service import MemberService
from backend.app.utils.api_response import api_response
from backend.app.utils.decorators import member_optional, member_required

bp = Blueprint('public_member', __name__, url_prefix='/api/public')

# 顾客端不用 cookie，CSRF 防的那个前提不存在（详见 api/public.py 里的说明）
csrf.exempt(bp)


def _pagination(page_obj):
    return {
        'page': page_obj.page,
        'per_page': page_obj.per_page,
        'total': page_obj.total,
        'pages': page_obj.pages,
    }


# ---------- 个人中心 ----------

@bp.get('/me')
@bp.response(200, description='我的账户：档案 + 储值余额 + 积分')
@member_required
def me():
    """我的

    顾客打开小程序先看的这一屏：还有多少钱、多少分。
    """
    return jsonify(api_response(
        success=True,
        data=MemberService.with_assets(g.member.id),
    ))


# ---------- 券 ----------

@bp.get('/me/coupons')
@bp.response(200, description='我的券包（data.coupons + data.pagination）')
@member_required
@bp.arguments(MemberCouponQuerySchema, location='query')
def my_coupons(params):
    """我的券包

    `status` 传 `unused` / `used` / `expired` / `not_started`——后两个是**算出来的**
    （见 `models/coupon.py` 开头），所以过滤只能在后端做。

    直接复用员工端那个 `CouponService.get_member_coupons`，
    **唯一区别是 member_id 从 token 来、不从 URL 来**——
    URL 里带 id 的话，改一个数字就能看别人的券包。
    """
    per_page = params.get('per_page') or current_app.config.get('DEFAULT_PAGE_SIZE', 10)
    pagination = CouponService.get_member_coupons(
        g.member.id, status=params.get('status'),
        page=params['page'], per_page=per_page,
    )
    return jsonify(api_response(
        success=True,
        data={
            'coupons': [c.to_dict() for c in pagination.items],
            'pagination': _pagination(pagination),
        }
    ))


@bp.get('/me/coupons/usable')
@bp.response(200, description='这一单能用哪些券（按能抵多少倒序）')
@member_required
@bp.arguments(UsableCouponQuerySchema, location='query')
def usable_coupons(params):
    """结算时「这一单能用哪些券」

    和员工端那个 `/api/coupons/members/<id>/usable` 是**同一个 service**，
    区别只有两处：

        member_id   从 token 来，不从 URL 来（URL 里带 id 就能看别人的券）
        返回里带 discount   顾客端要直接显示「能减 5 元」，不该自己再算一遍

    **用不了的券不会出现**——而不是出现了再告诉他不能用。
    """
    coupons = CouponService.get_usable_coupons(
        g.member.id, params['store_id'], params['amount'],
    )
    return jsonify(api_response(
        success=True,
        data={
            'coupons': [
                {**c.to_dict(),
                 'discount': float(c.template.discount_for(params['amount']))}
                for c in coupons
            ],
        }
    ))


@bp.get('/coupons')
@bp.response(200, description='券中心：有哪些券能领，登录了还带「我领了几张」')
@member_optional
def coupon_center():
    """券中心

    **不需要登录**：顾客端首页要把它当「近期活动」展示，一进来就是登录墙
    太难看。不登录时 `claimed_count` 按 0 算、`can_claim` 只看券本身
    （限领几条算不出来）——点「领取」的时候才要求登录。

    **不能领的也返回**（带 `blocked_reason`）：一张券摆在眼前却说不出为什么领不了，
    比它干脆不出现更让人恼火。
    """
    member = g.get('member')
    return jsonify(api_response(
        success=True,
        data={
            'coupons': CouponService.get_claimable_templates(
                member.id if member else None
            ),
            'logged_in': member is not None,
        },
    ))


@bp.post('/coupons/<int:template_id>/claim')
@bp.response(201, description='领到了，返回这张券')
@member_required
def claim_coupon(template_id):
    """领一张券

    约束（每张券能领几张、有没有领完、过没过期）在 service 里，
    这里只管「这个人是谁、要领哪张」。

    领不到时返回的是**具体原因**（「每人限领 2 张」「已经被领完了」），
    不是笼统的「领取失败」。
    """
    coupon = CouponService.claim(template_id, g.member)
    return jsonify(api_response(
        success=True,
        message=f'已领取「{coupon.template.name}」',
        data=coupon.to_dict(),
    )), 201
