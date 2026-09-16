"""储值测试：充送拆账、扣款先扣赠送、退款按比例退回、流水锚点、权限

大部分测试走 HTTP 接口。**但扣款和退款退回还没有接口**——它们要等「余额支付」
接进收款流程才有入口。核心逻辑不能等到那时候才测，所以那几个直接调 service
（用 `as_admin` 夹具造出「已登录」的上下文）。
"""
from contextlib import contextmanager
from decimal import Decimal

import pytest
from flask_login import login_user

from backend.app.errors import BusinessError
from backend.app.extensions import db
from backend.app.models import BalanceTxn, Permission, Role, Staff
from backend.app.services import BalanceService


@pytest.fixture
def as_admin(app, admin_staff):
    """在「已登录 admin」的请求上下文里执行一段代码

    用法：`with as_admin(): BalanceService.deduct(...)`

    service 里要用 `current_user`（记审计），所以必须有请求上下文 + 登录态。
    """
    @contextmanager
    def _ctx():
        with app.test_request_context():
            login_user(db.session.get(Staff, admin_staff.id))
            yield
    return _ctx


def _member(client, mobile='13800000001', **extra):
    payload = {'mobile': mobile}
    payload.update(extra)
    return client.post('/api/members', json=payload)


def _recharge(client, member_id, principal, bonus=0):
    return client.post(f'/api/members/{member_id}/balance/recharge',
                       json={'principal': str(principal), 'bonus': str(bonus)})


def _balance(client, member_id):
    return client.get(f'/api/members/{member_id}').get_json()['data']['balance']


# ---------- 建档 ----------

def test_create_member_needs_at_least_one_identity(client, admin_staff, login):
    """手机号和 openid 至少得有一个——两个都空，这张卡谁也认不出来"""
    login('admin', 'Admin123!')
    resp = client.post('/api/members', json={'nickname': '没留联系方式'})
    assert resp.status_code == 400
    assert '至少要填一个' in resp.get_json()['message']


def test_duplicate_mobile_rejected(client, admin_staff, login):
    login('admin', 'Admin123!')
    assert _member(client, '13800000001').status_code == 201
    resp = _member(client, '13800000001', nickname='另一个人')
    assert resp.status_code == 400
    assert '已经被注册' in resp.get_json()['message']


# ---------- 充值 ----------

def test_recharge_splits_principal_and_bonus(client, admin_staff, login):
    """充 100 送 20：本金 100、赠送 20，而且是**两条**流水

    合成一条的话，「这个月充值一共收了多少钱」就得从里面挑出来算——
    本金是收入、赠送是营销成本，报表上是两回事。
    """
    login('admin', 'Admin123!')
    member = _member(client).get_json()['data']

    resp = _recharge(client, member['id'], 100, 20)
    assert resp.status_code == 200
    data = resp.get_json()['data']
    assert data['principal'] == 100.0
    assert data['bonus'] == 20.0
    assert data['total'] == 120.0

    txns = client.get(f'/api/members/{member["id"]}/balance/txns').get_json()['data']['txns']
    assert [t['type'] for t in txns] == ['bonus', 'recharge']    # 倒序，后发生的在前
    assert txns[0]['bonus_delta'] == 20.0
    assert txns[0]['principal_delta'] == 0.0
    assert txns[1]['principal_delta'] == 100.0
    assert txns[1]['bonus_delta'] == 0.0


def test_recharge_records_balance_after(client, admin_staff, login):
    """流水要记「变动后余额」——对账时一眼看出哪一笔不对，不用重算全部"""
    login('admin', 'Admin123!')
    member = _member(client).get_json()['data']
    _recharge(client, member['id'], 100, 0)
    _recharge(client, member['id'], 50, 10)

    txns = client.get(f'/api/members/{member["id"]}/balance/txns').get_json()['data']['txns']
    # 倒序：最后一次赠送 → 最后一次本金 → 第一次本金
    assert [t['type'] for t in txns] == ['bonus', 'recharge', 'recharge']
    # 最后一笔之后的状态
    assert txns[0]['principal_after'] == 150.0
    assert txns[0]['bonus_after'] == 10.0
    # 第一笔之后的状态
    assert txns[2]['principal_after'] == 100.0
    assert txns[2]['bonus_after'] == 0.0


def test_disabled_member_cannot_recharge(app, client, admin_staff, login):
    """停用的会员不能充值——但他还能被查、历史订单还认得他"""
    from backend.app.models import Member

    login('admin', 'Admin123!')
    member = _member(client).get_json()['data']

    with app.app_context():
        m = db.session.get(Member, member['id'])
        m.is_active = False
        db.session.commit()

    resp = _recharge(client, member['id'], 100)
    assert resp.status_code == 400
    assert '停用' in resp.get_json()['message']


# ---------- 扣款（还没有接口，直接调 service） ----------

def test_deduct_spends_bonus_first(as_admin, client, admin_staff, login):
    """扣款先扣赠送：本金留着随时能退

    充 100 送 20，消费 30 → 赠送清空、本金扣 10，剩 90 **全是能退的本金**。
    反过来先扣本金的话，会留下「本金花完、赠送还剩一堆」的尴尬状态，
    那时候退款规则就说不清了。
    """
    login('admin', 'Admin123!')
    member = _member(client).get_json()['data']
    _recharge(client, member['id'], 100, 20)

    with as_admin():
        BalanceService.deduct(member['id'], Decimal('30'))
        db.session.commit()

    balance = _balance(client, member['id'])
    assert balance['bonus'] == 0.0
    assert balance['principal'] == 90.0


def test_deduct_rejects_when_short_and_leaves_balance_alone(as_admin, client, admin_staff, login):
    """余额不够就拒绝，而且**余额一分不动**"""
    login('admin', 'Admin123!')
    member = _member(client).get_json()['data']
    _recharge(client, member['id'], 100, 20)

    with as_admin():
        with pytest.raises(BusinessError, match='余额不足'):
            BalanceService.deduct(member['id'], Decimal('200'))
        db.session.rollback()

    balance = _balance(client, member['id'])
    assert balance['total'] == 120.0


# ---------- 退款退回（还没有接口，直接调 service） ----------

def _spend(client, as_admin, member_id, amount):
    """消费一笔，返回那条流水的 id（退款要挂在它上面）"""
    with as_admin():
        txn = BalanceService.deduct(member_id, Decimal(amount))
        db.session.commit()
        return txn.id


def test_refund_returns_by_original_ratio(as_admin, client, admin_staff, login):
    """退款按原消费的比例拆：扣的时候扣了多少本金，退的时候就退多少

    充 100 送 20，消费 100 → 扣掉赠送 20 + 本金 80。
    退一半（50）→ 按 80:20 拆 → 退回本金 40 + 赠送 10。
    """
    login('admin', 'Admin123!')
    member = _member(client).get_json()['data']
    _recharge(client, member['id'], 100, 20)
    txn_id = _spend(client, as_admin, member['id'], 100)

    with as_admin():
        txn = db.session.get(BalanceTxn, txn_id)
        BalanceService.refund_to_balance(txn, Decimal('50'))
        db.session.commit()

    balance = _balance(client, member['id'])
    # 消费后：本金 20、赠送 0；退回后：本金 60、赠送 10
    assert balance['principal'] == 60.0
    assert balance['bonus'] == 10.0


def test_full_refund_restores_exactly(as_admin, client, admin_staff, login):
    """全额退款要把本金和赠送**原样还原**——这是「按比例拆」的最佳检验"""
    login('admin', 'Admin123!')
    member = _member(client).get_json()['data']
    _recharge(client, member['id'], 100, 20)
    txn_id = _spend(client, as_admin, member['id'], 100)

    with as_admin():
        txn = db.session.get(BalanceTxn, txn_id)
        BalanceService.refund_to_balance(txn, Decimal('100'))
        db.session.commit()

    balance = _balance(client, member['id'])
    assert balance['principal'] == 100.0
    assert balance['bonus'] == 20.0


def test_refund_cannot_exceed_the_original(as_admin, client, admin_staff, login):
    login('admin', 'Admin123!')
    member = _member(client).get_json()['data']
    _recharge(client, member['id'], 100, 0)
    txn_id = _spend(client, as_admin, member['id'], 60)

    with as_admin():
        txn = db.session.get(BalanceTxn, txn_id)
        with pytest.raises(BusinessError, match='退不回这么多'):
            BalanceService.refund_to_balance(txn, Decimal('80'))
        db.session.rollback()


# ---------- 权限 ----------

def test_balance_view_does_not_imply_recharge(app, client, admin_staff, make_staff, login):
    """能看余额不等于能充值——充值是钱的入口，单独一个权限码

    收银员两个都有（要告诉顾客还能抵多少，也要能给他充卡）；但一个只有
    「查看」的角色绝不该能凭空给账户加钱。
    """
    login('admin', 'Admin123!')
    member = _member(client).get_json()['data']
    client.post('/api/auth/logout')

    with app.app_context():
        role = Role(code='balance_reader', name='只能看余额', data_scope='all', description='')
        role.permissions = Permission.query.filter(
            Permission.code.in_(['member:balance:view'])
        ).all()
        db.session.add(role)
        db.session.commit()

    make_staff('kanyue', 'balance_reader')
    login('kanyue', 'Passw0rd!')

    # 看得了
    assert client.get(f'/api/members/{member["id"]}').get_json()['data']['balance'] is not None
    # 充不了
    resp = _recharge(client, member['id'], 100)
    assert resp.status_code == 403


def test_member_detail_hides_balance_without_permission(app, client, admin_staff,
                                                        make_staff, login):
    """没有「查看储值余额」权限的人，看得到档案、看不到钱"""
    login('admin', 'Admin123!')
    member = _member(client).get_json()['data']
    client.post('/api/auth/logout')

    with app.app_context():
        role = Role(code='member_only', name='只能看档案', data_scope='all', description='')
        role.permissions = Permission.query.filter(
            Permission.code.in_(['member:view'])
        ).all()
        db.session.add(role)
        db.session.commit()

    make_staff('dangan', 'member_only')
    login('dangan', 'Passw0rd!')

    data = client.get(f'/api/members/{member["id"]}').get_json()['data']
    assert data['mobile'] == '13800000001'
    assert data['balance'] is None
