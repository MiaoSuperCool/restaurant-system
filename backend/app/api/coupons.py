"""优惠券接口：模板管理 + 发券 + 券包 + 这单能用哪些券

权限码分三档（`rbac.py` 里早就预留了）：

    coupon:manage   建/改/删券模板、看发券记录
    coupon:issue    发券给会员
    coupon:verify   核销——那是用券的入口

**发券和管模板分开**：能设计券的人不一定该能随便发（发出去就是成本）。
"""
from flask import current_app, jsonify
from flask_login import login_required
from flask_smorest import Blueprint

from backend.app.schemas.coupon_schema import (
    CouponIssueSchema,
    CouponQuerySchema,
    CouponTemplateCreateSchema,
    CouponTemplateQuerySchema,
    CouponTemplateUpdateSchema,
    UsableCouponQuerySchema,
)
from backend.app.services import CouponService, MemberService
from backend.app.utils.api_response import api_response
from backend.app.utils.decorators import permission_required

bp = Blueprint('coupons', __name__, url_prefix='/api/coupons')

# 看券不需要单独的码：它和「看储值余额」是一类事——收银台得知道顾客有什么能用
_VIEW_MEMBER_COUPONS = ('member:balance:view', 'coupon:verify')


def _pagination(page_obj):
    return {
        'page': page_obj.page,
        'per_page': page_obj.per_page,
        'total': page_obj.total,
        'pages': page_obj.pages,
    }


def _per_page(params):
    return params.get('per_page') or current_app.config.get('DEFAULT_PAGE_SIZE', 10)


# ---------- 券模板 ----------

@bp.get('/templates')
@bp.response(200, description='券模板列表（data.templates + data.pagination）')
@login_required
@permission_required('coupon:manage')
@bp.arguments(CouponTemplateQuerySchema, location='query')
def list_templates(params):
    pagination = CouponService.get_templates(
        page=params['page'], per_page=_per_page(params),
        search=params.get('search'), status=params.get('status'),
    )
    return jsonify(api_response(
        success=True,
        data={
            'templates': [t.to_dict() for t in pagination.items],
            'pagination': _pagination(pagination),
        }
    ))


@bp.post('/templates')
@bp.response(201, description='建好了，返回新模板')
@login_required
@permission_required('coupon:manage')
@bp.arguments(CouponTemplateCreateSchema, location='json')
def create_template(data):
    template = CouponService.create_template(data)
    return jsonify(api_response(success=True, data=template.to_dict())), 201


@bp.put('/templates/<int:template_id>')
@bp.response(200, description='改好了，返回模板')
@login_required
@permission_required('coupon:manage')
@bp.arguments(CouponTemplateUpdateSchema, location='json')
def edit_template(data, template_id):
    template = CouponService.update_template(template_id, data)
    return jsonify(api_response(success=True, data=template.to_dict()))


@bp.delete('/templates/<int:template_id>')
@bp.response(200, description='已删除')
@login_required
@permission_required('coupon:manage')
def delete_template(template_id):
    """删模板——**发出去过的就删不掉了**，不想再发请改成「停用」"""
    CouponService.delete_template(template_id)
    return jsonify(api_response(success=True, message='已删除'))


# ---------- 发券 ----------

@bp.post('/issue')
@bp.response(200, description='发券成功，返回发出去多少张')
@login_required
@permission_required('coupon:issue')
@bp.arguments(CouponIssueSchema, location='json')
def issue(data):
    """给一批会员发券

    三道检查（模板启用、会员能用、总量够）都在 service 里。
    """
    total = CouponService.issue(
        data['template_id'], data['member_ids'],
        count=data['count'], remark=data.get('remark', ''),
    )
    return jsonify(api_response(success=True, message=f'发出 {total} 张',
                                data={'total': total}))


# ---------- 会员的券 ----------

@bp.get('/members/<int:member_id>')
@bp.response(200, description='某会员的券包（data.coupons + data.pagination）')
@login_required
@permission_required(*_VIEW_MEMBER_COUPONS)
@bp.arguments(CouponQuerySchema, location='query')
def member_coupons(params, member_id):
    """会员的券包

    `status` 传 `expired` 时是**算出来的**——库里只存未用/已用。
    """
    MemberService.get_or_404(member_id)
    pagination = CouponService.get_member_coupons(
        member_id, status=params.get('status'),
        page=params['page'], per_page=_per_page(params),
    )
    return jsonify(api_response(
        success=True,
        data={
            'coupons': [c.to_dict() for c in pagination.items],
            'pagination': _pagination(pagination),
        }
    ))


@bp.get('/members/<int:member_id>/usable')
@bp.response(200, description='这单能用的券（按能抵多少倒序）')
@login_required
@permission_required(*_VIEW_MEMBER_COUPONS)
@bp.arguments(UsableCouponQuerySchema, location='query')
def usable_coupons(params, member_id):
    """这一单能用哪些券

    要传门店和金额——「适用门店」和「满多少」这两个条件得靠它们判。
    **用不了的不会出现在结果里**（而不是出现了再说不能用），
    收银员看到的每一张都是真能用的。
    """
    MemberService.get_or_404(member_id)
    coupons = CouponService.get_usable_coupons(
        member_id, params['store_id'], params['amount'],
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
