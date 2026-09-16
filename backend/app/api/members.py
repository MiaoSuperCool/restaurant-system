"""会员 + 储值接口

**会员是全公司通用的**，不按门店分——一个会员在哪家店都能用储值。所以这里
没有 `assert_in_scope`：数据范围管的是「本店的订单/菜单」，会员不属于任何一家店。

权限码分三层，别混：

    member:view              看会员档案（姓名手机号）
    member:balance:view      看储值余额 + 流水    ← 收银员有（不然没法告诉顾客还能抵多少）
    member:balance:recharge  充值                 ← 钱的入口，单独一个码
    member:manage            改会员资料

收银员有 `member:balance:view` 但没有 `member:view`——**看余额的前提是先找到
这个人**，所以查会员的接口两个码任一即可。
"""
from flask import current_app, jsonify
from flask_login import current_user, login_required
from flask_smorest import Blueprint

from backend.app.schemas.member_schema import MemberCreateSchema, RechargeSchema
from backend.app.schemas.query_schema import PageQuerySchema
from backend.app.services import BalanceService, MemberService
from backend.app.utils.api_response import api_response
from backend.app.utils.decorators import permission_required

bp = Blueprint('members', __name__, url_prefix='/api/members')

# 查会员：看档案的、看余额的，任一即可（看余额也得先找到人）
_VIEW = ('member:view', 'member:balance:view')


def _with_balance(member, balances):
    """会员档案 + 储值余额

    `balances` 传 `None` 表示「这个人没有看余额的权限」——余额给 `null`，
    前端据此显示「—」。传空字典则是「能看，只是他还没充过值」。
    **「看不到」和「没钱」是两回事**，别都塞成 0。
    """
    data = member.to_dict()
    if balances is None:
        data['balance'] = None
    else:
        balance = balances.get(member.id)
        data['balance'] = (balance.to_dict() if balance
                           else BalanceService.empty_dict(member.id))
    return data


@bp.get('')
@bp.response(200, description='会员列表（data.members 数组 + data.pagination）')
@login_required
@permission_required(*_VIEW)
@bp.arguments(PageQuerySchema, location='query')
def index(params):
    """会员列表，可按手机号或昵称搜

    收银台那一幕：顾客报手机号 → 搜出人 → 看余额 → 决定能不能抵这单。
    """
    per_page = params.get('per_page') or current_app.config.get('DEFAULT_PAGE_SIZE', 10)
    pagination = MemberService.get_paginated(
        page=params['page'], per_page=per_page, search=params.get('search')
    )

    # 余额一起带上——收银台搜出人来就是要看余额，分两个请求没意义。
    # 但**没有 member:balance:view 的人拿到的余额是 null**（不是 0，
    # 「看不到」和「没钱」是两回事）
    can_see_balance = current_user.has_permission('member:balance:view')
    balances = BalanceService.get_balances(
        [member.id for member in pagination.items]
    ) if can_see_balance else {}

    return jsonify(api_response(
        success=True,
        data={
            'members': [
                _with_balance(member, balances if can_see_balance else None)
                for member in pagination.items
            ],
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages,
            },
        }
    ))


@bp.get('/<int:member_id>')
@bp.response(200, description='会员详情（含储值余额）')
@login_required
@permission_required(*_VIEW)
def detail(member_id):
    """会员详情 + 储值余额

    余额一起返回：收银台查会员就是为了看余额，分两个请求没意义。
    没有 `member:balance:view` 的人也能看档案，但余额会给 null。
    """
    member = MemberService.get_or_404(member_id)
    balances = (BalanceService.get_balances([member_id])
                if current_user.has_permission('member:balance:view') else None)
    return jsonify(api_response(success=True, data=_with_balance(member, balances)))


@bp.get('/<int:member_id>/balance/txns')
@bp.response(200, description='余额流水（倒序）')
@login_required
@permission_required('member:balance:view')
@bp.arguments(PageQuerySchema, location='query')
def txns(params, member_id):
    """余额流水

    **查余额和查流水是一回事**——只给一个数字的余额，收银员没法回答
    「我这钱什么时候充的、怎么少了一半」。
    """
    MemberService.get_or_404(member_id)
    per_page = params.get('per_page') or current_app.config.get('DEFAULT_PAGE_SIZE', 10)
    pagination = BalanceService.get_txns(
        member_id, page=params['page'], per_page=per_page
    )
    return jsonify(api_response(
        success=True,
        data={
            'txns': [txn.to_dict() for txn in pagination.items],
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages,
            },
        }
    ))


@bp.post('')
@bp.response(201, description='建档成功，返回新会员')
@login_required
@permission_required('member:manage')
@bp.arguments(MemberCreateSchema, location='json')
def create(data):
    """员工代客办卡（顾客端自助注册是二期后面的事，走同一套校验）"""
    member = MemberService.create(data)
    return jsonify(api_response(success=True, data=member.to_dict())), 201


@bp.post('/<int:member_id>/balance/recharge')
@bp.response(200, description='充值成功，返回充值后的账户')
@login_required
@permission_required('member:balance:recharge')
@bp.arguments(RechargeSchema, location='json')
def recharge(data, member_id):
    """储值充值（支持充送结合）

    钱的入口，所以权限码是单独一个 `member:balance:recharge`——
    能看余额不等于能凭空给账户加钱。
    """
    balance = BalanceService.recharge(
        member_id,
        principal=data['principal'],
        bonus=data.get('bonus') or 0,
        remark=data.get('remark', ''),
    )
    return jsonify(api_response(success=True, data=balance.to_dict()))
