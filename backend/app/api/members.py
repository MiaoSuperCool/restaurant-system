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

from backend.app.schemas.member_schema import (
    MemberCreateSchema,
    PointsAdjustSchema,
    RechargeSchema,
)
from backend.app.schemas.query_schema import PageQuerySchema
from backend.app.services import BalanceService, MemberService, PointsService
from backend.app.utils.api_response import api_response
from backend.app.utils.decorators import permission_required

bp = Blueprint('members', __name__, url_prefix='/api/members')

# 查会员：看档案的、看余额的，任一即可（看余额也得先找到人）
_VIEW = ('member:view', 'member:balance:view')


def _asset(rows, member_id, empty_dict):
    """组装「储值余额 / 积分」这类字段

    `rows` 传 `None` 表示**当前这个人没有看的权限**——给 `null`，前端显示「—」。
    传空字典则是「能看，只是他还没建过账户」。**「看不到」和「没有」是两回事**，
    别都塞成 0。
    """
    if rows is None:
        return None
    row = rows.get(member_id)
    return row.to_dict() if row else empty_dict(member_id)


def _with_assets(member, balances, points_map):
    """会员档案 + 储值余额 + 积分

    两种资产一起给：收银台查会员就是为了看「他账上有多少钱、多少分」，
    分三个请求没意义。
    """
    data = member.to_dict()
    data['balance'] = _asset(balances, member.id, BalanceService.empty_dict)

    points = _asset(points_map, member.id, PointsService.empty_dict)
    if points is not None:
        # 顺手把「这些分能抵多少钱」算出来——**用 service 的换算，不在这儿另写一套**。
        # 前端拿它直接显示，收银员不用心算「320 分是几块钱」
        points['amount'] = float(PointsService.amount_for_points(points['balance']))
    data['points'] = points
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

    # 余额和积分一起带上——收银台搜出人来就是要看这两个数，分请求没意义。
    # 但**没有 member:balance:view 的人拿到的是 null**（不是 0，
    # 「看不到」和「没钱」是两回事）
    member_ids = [member.id for member in pagination.items]
    if current_user.has_permission('member:balance:view'):
        balances = BalanceService.get_balances(member_ids)
        points_map = PointsService.get_balances(member_ids)
    else:
        balances = points_map = None

    return jsonify(api_response(
        success=True,
        data={
            'members': [
                _with_assets(member, balances, points_map)
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
    if current_user.has_permission('member:balance:view'):
        balances = BalanceService.get_balances([member_id])
        points_map = PointsService.get_balances([member_id])
    else:
        balances = points_map = None
    return jsonify(api_response(
        success=True, data=_with_assets(member, balances, points_map)
    ))


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


@bp.get('/<int:member_id>/points/txns')
@bp.response(200, description='积分流水（倒序）')
@login_required
@permission_required('member:balance:view')
@bp.arguments(PageQuerySchema, location='query')
def points_txns(params, member_id):
    """积分流水

    和余额流水一样：只给一个分数，收银员没法回答「我这分怎么少了」。
    """
    MemberService.get_or_404(member_id)
    per_page = params.get('per_page') or current_app.config.get('DEFAULT_PAGE_SIZE', 10)
    pagination = PointsService.get_txns(
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


@bp.post('/<int:member_id>/points/adjust')
@bp.response(200, description='调整成功，返回那条流水')
@login_required
@permission_required('points:adjust')
@bp.arguments(PointsAdjustSchema, location='json')
def adjust_points(data, member_id):
    """手工调整积分（补偿、纠错）

    **必须写原因**——手工加的分不写清楚为什么，事后没人说得清是谁加的、为什么。
    这条规则在 schema 和 service 里各拦一道。
    """
    txn = PointsService.adjust_with_audit(
        member_id, delta=data['delta'], remark=data['remark'],
    )
    return jsonify(api_response(success=True, data=txn.to_dict()))


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
