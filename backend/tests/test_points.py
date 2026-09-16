"""积分测试：换算、手工调整、消费返、抵扣、流水、权限

和储值（test_balance.py）是一对，但**积分不分本金/赠送**——它全是送的，
没有「顾客真掏的钱」那一部分，所以模型和规则都简单一层。

消费返和抵扣暂时直接调 service：它们要等接进订单流程才有接口。
"""
from decimal import Decimal

import pytest

from backend.app.errors import BusinessError
from backend.app.extensions import db
from backend.app.models import Permission, PointsTxn, Role
from backend.app.services import PointsService


def _member(client, mobile='13800000001'):
    return client.post('/api/members', json={'mobile': mobile}).get_json()['data']


def _adjust(client, member_id, delta, remark='补偿'):
    return client.post(f'/api/members/{member_id}/points/adjust',
                       json={'delta': delta, 'remark': remark})


def _points(client, member_id):
    return client.get(f'/api/members/{member_id}').get_json()['data']['points']


# ---------- 换算 ----------

def test_points_conversion():
    """消费 1 元返 1 分；100 分抵 1 元

    **换算只有这一处**（`points_for_amount` / `amount_for_points`），别处不许自己算——
    比例真要按门店/活动配起来的时候，改动会同时落到「返多少」「抵多少」
    「退款怎么回滚」三处，收在一起才改得动。
    """
    assert PointsService.points_for_amount(Decimal('32.50')) == 32
    assert PointsService.points_for_amount(Decimal('0.90')) == 0    # 不够 1 分
    assert PointsService.amount_for_points(150) == Decimal('1.50')
    assert PointsService.amount_for_points(0) == Decimal('0.00')


# ---------- 手工调整 ----------

def test_adjust_points(client, admin_staff, login):
    """手工补积分：记一条流水，带变动后余额"""
    login('admin', 'Admin123!')
    member = _member(client)

    resp = _adjust(client, member['id'], 100, '顾客投诉补偿')
    assert resp.status_code == 200
    assert resp.get_json()['data']['delta'] == 100
    assert resp.get_json()['data']['after'] == 100

    assert _points(client, member['id'])['balance'] == 100

    txns = client.get(f'/api/members/{member["id"]}/points/txns').get_json()['data']['txns']
    assert len(txns) == 1
    assert txns[0]['type'] == 'adjust'
    assert txns[0]['remark'] == '顾客投诉补偿'


def test_adjust_requires_a_reason(client, admin_staff, login):
    """不写原因不给调——手工加的分，事后没人说得清是谁加的、为什么"""
    login('admin', 'Admin123!')
    member = _member(client)

    resp = client.post(f'/api/members/{member["id"]}/points/adjust',
                       json={'delta': 100})
    assert resp.status_code == 422      # schema 就拦下了


def test_adjust_rejects_zero(points_app_client):
    """调 0 分没有意义，只会往流水里塞一条看不懂的记录"""
    client, member = points_app_client
    resp = _adjust(client, member['id'], 0)
    assert resp.status_code == 400
    assert '不能是 0' in resp.get_json()['message']


def test_cannot_go_negative(client, admin_staff, login):
    """扣不出负数——积分不够就拒绝"""
    login('admin', 'Admin123!')
    member = _member(client)
    _adjust(client, member['id'], 50)

    resp = _adjust(client, member['id'], -80, '扣回')
    assert resp.status_code == 400
    assert '积分不足' in resp.get_json()['message']

    assert _points(client, member['id'])['balance'] == 50


def test_points_adjust_needs_permission(app, client, admin_staff, make_staff, login):
    """能看积分不等于能改积分——改了就是凭空空口给好处"""
    login('admin', 'Admin123!')
    member = _member(client)
    _adjust(client, member['id'], 100)
    client.post('/api/auth/logout')

    with app.app_context():
        role = Role(code='points_reader', name='只能看积分', data_scope='all', description='')
        role.permissions = Permission.query.filter(
            Permission.code.in_(['member:balance:view'])
        ).all()
        db.session.add(role)
        db.session.commit()

    make_staff('kandian', 'points_reader')
    login('kandian', 'Passw0rd!')

    # 看得了
    assert _points(client, member['id'])['balance'] == 100
    # 改不了
    assert _adjust(client, member['id'], 50).status_code == 403


def test_shift_manager_can_adjust_points(client, admin_staff, make_staff, login):
    """值班经理能补积分（店长是整个列表的超集，自动也有）

    补积分是门店现场的事——顾客投诉了当场补一点。它不涉及钱（积分全是送的），
    所以不用像退款那样卡限额，值班经理顶班时就该能处理。

    **收银员没有这个码**：多一层「谁能给好处」的区分。
    """
    login('admin', 'Admin123!')
    member = _member(client)
    client.post('/api/auth/logout')

    make_staff('zhiban', 'shift_manager')
    login('zhiban', 'Passw0rd!')

    assert _adjust(client, member['id'], 30, '上错菜了').status_code == 200


# ---------- 消费返 / 抵扣（还没有接口，直接调 service） ----------

def test_earn_points_on_consumption(as_admin, client, admin_staff, login):
    """消费 32.5 元返 32 分——向下取整，不出现"差 0.5 分"这种说不清的东西"""
    login('admin', 'Admin123!')
    member = _member(client)

    with as_admin():
        txn = PointsService.earn(member['id'], Decimal('32.50'))
        db.session.commit()
        # 出了 with 就没有 app 上下文了，ORM 对象读不动——值在这儿取出来
        earned = txn.delta

    assert earned == 32
    assert _points(client, member['id'])['balance'] == 32


def test_tiny_amount_earns_nothing(as_admin, client, admin_staff, login):
    """不到 1 元的消费返不出整数分——**不记这条流水**，别塞一堆 +0 进去"""
    login('admin', 'Admin123!')
    member = _member(client)

    with as_admin():
        txn = PointsService.earn(member['id'], Decimal('0.90'))
        db.session.commit()
        txn_count = PointsTxn.query.count()

    assert txn is None
    assert txn_count == 0
    assert _points(client, member['id'])['balance'] == 0


def test_redeem_returns_the_money(as_admin, client, admin_staff, login):
    """抵扣：扣积分，**返回抵了多少钱**——调用方拿它去减应付"""
    login('admin', 'Admin123!')
    member = _member(client)
    _adjust(client, member['id'], 500)

    with as_admin():
        discount = PointsService.redeem(member['id'], 200)
        db.session.commit()

    assert discount == Decimal('2.00')
    assert _points(client, member['id'])['balance'] == 300


def test_redeem_rejects_when_short(as_admin, client, admin_staff, login):
    """积分不够就拒绝，而且**一分不动**"""
    login('admin', 'Admin123!')
    member = _member(client)
    _adjust(client, member['id'], 50)

    with as_admin():
        with pytest.raises(BusinessError, match='积分不够'):
            PointsService.redeem(member['id'], 200)
        db.session.rollback()

    assert _points(client, member['id'])['balance'] == 50


@pytest.fixture
def points_app_client(client, admin_staff, login):
    """建好会员 + 登录，给「只用 HTTP 接口」的那几条测试用"""
    login('admin', 'Admin123!')
    return client, _member(client)


# ---------- 接进订单：收款返、退款扣回 ----------

def _store(client, code='S001', name='解放路店'):
    return client.post('/api/stores', json={'code': code, 'name': name}).get_json()['data']


def _dish(client, name='牛肉面', base_price='15.00'):
    import time
    category = client.post('/api/categories',
                           json={'name': f'面食{time.time_ns()}'}).get_json()['data']
    return client.post('/api/dishes', json={
        'category_id': category['id'], 'name': name, 'base_price': base_price,
    }).get_json()['data']


def _order(client, store_id, dish_id, member_id=None, quantity=1):
    payload = {
        'store_id': store_id,
        'items': [{'dish_id': dish_id, 'quantity': quantity, 'option_ids': []}],
    }
    if member_id:
        payload['member_id'] = member_id
    return client.post('/api/orders', json=payload).get_json()['data']


def _collect(client, order_id, method, amount):
    return client.post(f'/api/orders/{order_id}/payments',
                       json={'method': method, 'amount': str(amount)})


def test_collecting_earns_points(client, admin_staff, login):
    """**收款时**返积分，不是下单时——钱到手才算

    按这次收款的金额算（组合支付时每笔各返各的）。
    """
    login('admin', 'Admin123!')
    store, dish = _store(client), _dish(client)          # 牛肉面 ¥15
    member = _member(client)

    order = _order(client, store['id'], dish['id'], member['id'])
    # 下单时还没返——订单建了不算数
    assert _points(client, member['id'])['balance'] == 0

    assert _collect(client, order['id'], 'cash', 15).status_code == 201
    assert _points(client, member['id'])['balance'] == 15


def test_partial_payment_earns_proportionally(client, admin_staff, login):
    """组合支付：每笔各返各的（收 10 返 10、再收 5 返 5）"""
    login('admin', 'Admin123!')
    store, dish = _store(client), _dish(client)
    member = _member(client)
    order = _order(client, store['id'], dish['id'], member['id'])

    _collect(client, order['id'], 'cash', 10)
    assert _points(client, member['id'])['balance'] == 10

    _collect(client, order['id'], 'wechat', 5)
    assert _points(client, member['id'])['balance'] == 15


def test_scattered_order_earns_nothing(client, admin_staff, login):
    """散客单不返——返给谁？"""
    login('admin', 'Admin123!')
    store, dish = _store(client), _dish(client)
    order = _order(client, store['id'], dish['id'])      # 没挂会员

    assert _collect(client, order['id'], 'cash', 15).status_code == 201


def test_disabled_member_earns_nothing(app, client, admin_staff, login):
    """停用的会员不返——他不该再攒新的好处"""
    from backend.app.models import Member

    login('admin', 'Admin123!')
    store, dish = _store(client), _dish(client)
    member = _member(client)
    order = _order(client, store['id'], dish['id'], member['id'])

    with app.app_context():
        db.session.get(Member, member['id']).is_active = False
        db.session.commit()

    assert _collect(client, order['id'], 'cash', 15).status_code == 201
    assert _points(client, member['id'])['balance'] == 0


def test_refund_takes_points_back(client, admin_staff, make_staff, login):
    """退款要把当初返的扣回来——按退款金额算，和返的时候同一个换算"""
    login('admin', 'Admin123!')
    store, dish = _store(client), _dish(client)
    member = _member(client)
    order = _order(client, store['id'], dish['id'], member['id'])

    _collect(client, order['id'], 'cash', 15)
    assert _points(client, member['id'])['balance'] == 15
    client.post('/api/auth/logout')

    # 申请和审批得两个人
    make_staff('shouyin', 'cashier', store_id=store['id'])
    login('shouyin', 'Passw0rd!')
    refund = client.post(f'/api/refunds/orders/{order["id"]}',
                         json={'amount': '15.00', 'reason': '点错了'}).get_json()['data']
    client.post('/api/auth/logout')

    login('admin', 'Admin123!')
    client.post(f'/api/refunds/{refund["id"]}/approve', json={'remark': '同意'})
    # 审批通过还不扣——钱没出去呢
    assert _points(client, member['id'])['balance'] == 15

    assert client.post(f'/api/refunds/{refund["id"]}/settle',
                       json={'method': 'cash'}).status_code == 200
    # 打款了才扣
    assert _points(client, member['id'])['balance'] == 0


def test_revoke_stops_at_zero(as_admin, client, admin_staff, login):
    """积分已经被花掉时，扣到 0 为止——**不让积分变负**

    花 1000 分抵 10 元、再把那 10 元退掉的话，只会扣回 10 分——那 1000 分已经
    花出去了。金额很小，而且退款要走审批流，先接受这个口子。
    """
    login('admin', 'Admin123!')
    member = _member(client)
    _adjust(client, member['id'], 5)         # 账上只有 5 分

    with as_admin():
        txn = PointsService.revoke(member['id'], Decimal('32.00'))   # 本该扣 32 分
        db.session.commit()
        actual = txn.delta
        note = txn.remark

    assert actual == -5                       # 只扣掉账上有的
    assert _points(client, member['id'])['balance'] == 0
    # 流水里写清楚了，免得看的人以为程序算错了
    assert '扣到 0 为止' in note


def test_revoke_on_empty_account_writes_nothing(as_admin, client, admin_staff, login):
    """一分都没有就**不记流水**——别塞一条 0 变动的记录进去"""
    login('admin', 'Admin123!')
    member = _member(client)

    with as_admin():
        txn = PointsService.revoke(member['id'], Decimal('32.00'))
        db.session.commit()
        count = PointsTxn.query.count()

    assert txn is None
    assert count == 0
