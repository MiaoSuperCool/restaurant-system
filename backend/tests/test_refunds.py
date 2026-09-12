"""退款审批流测试

重点验证两件事：
1. **批了 ≠ 钱退了**——申请单是流程，退款流水才是钱
2. 大额退款要更高的权限（设计文档里「值班经理批不了大额」那句）
"""
import itertools
import time

# 每个「收银员」用不同的用户名：同一个测试里可能发起多次申请，
# 撞用户名会违反唯一约束
_cashier_seq = itertools.count(1)


def _setup_paid_order(client, quantity=10):
    """建一单已付款的订单：牛肉面 ¥32 × N，返回 order_id 和金额

    默认 10 份 = ¥320，方便测「超过审批限额 ¥200」的场景。
    """
    suffix = str(time.time_ns())[-6:]
    store = client.post('/api/stores', json={
        'code': f'R{suffix}', 'name': f'退款测试店{suffix}',
    }).get_json()['data']
    category = client.post('/api/categories', json={'name': f'退款测试{suffix}'}).get_json()['data']
    dish = client.post('/api/dishes', json={
        'category_id': category['id'], 'name': f'牛肉面{suffix}', 'base_price': '32.00',
    }).get_json()['data']

    order = client.post('/api/orders', json={
        'store_id': store['id'],
        'items': [{'dish_id': dish['id'], 'quantity': quantity, 'option_ids': []}],
    }).get_json()['data']
    client.post(f'/api/orders/{order["id"]}/payments',
                json={'method': 'wechat', 'amount': str(order['payable_amount'])})
    return order['id'], order['payable_amount'], store['id']


def _apply(client, order_id, amount, reason='顾客投诉', type_='online'):
    return client.post(f'/api/refunds/orders/{order_id}', json={
        'amount': str(amount), 'reason': reason, 'type': type_,
    })


def _apply_as_cashier(client, make_staff, login, store_id, order_id, amount, **kwargs):
    """换收银员身份发起申请，然后换回 admin

    不能自己申请自己批（这是条真规则），所以测试里申请人和审批人得是两个人——
    这也正是真实门店的样子：收银员发起，店长批。
    """
    username = f'shouyin{next(_cashier_seq)}'
    make_staff(username, 'cashier', store_id=store_id)
    login(username, 'Passw0rd!')
    refund_id = _apply(client, order_id, amount, **kwargs).get_json()['data']['id']
    client.post('/api/auth/logout')
    login('admin', 'Admin123!')
    return refund_id


def test_full_refund_flow(client, admin_staff, make_staff, login):
    """申请 → 审批 → 确认退款，钱最后才真的动"""
    login('admin', 'Admin123!')
    order_id, total, store_id = _setup_paid_order(client)
    make_staff('shouyin', 'cashier', store_id=store_id)
    make_staff('zhiban', 'shift_manager', store_id=store_id)
    client.post('/api/auth/logout')

    # --- 收银员发起 ---
    login('shouyin', 'Passw0rd!')
    resp = _apply(client, order_id, 100)
    assert resp.status_code == 201, resp.get_json()
    refund = resp.get_json()['data']
    refund_id = refund['id']
    assert refund['status'] == 'pending'
    assert refund['refund_no'].endswith('-R01')
    assert refund['applicant_name'] == 'shouyin'
    client.post('/api/auth/logout')

    # 申请阶段：钱一分没动
    login('admin', 'Admin123!')
    order = client.get(f'/api/orders/{order_id}').get_json()['data']
    assert order['refunded_amount'] == 0
    assert order['refundable_amount'] == total
    assert len(order['refunds']) == 1
    assert order['refunds'][0]['txns'] == []      # 还没有流水 = 钱没出去
    client.post('/api/auth/logout')

    # --- 值班经理审批 ---
    login('zhiban', 'Passw0rd!')
    resp = client.post(f'/api/refunds/{refund_id}/approve', json={'remark': '情况属实'})
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()['data']['status'] == 'approved'
    client.post('/api/auth/logout')

    # 审批完：钱还是没动
    login('admin', 'Admin123!')
    order = client.get(f'/api/orders/{order_id}').get_json()['data']
    assert order['refunded_amount'] == 0, '批准不等于钱退了'
    assert order['refundable_amount'] == total
    client.post('/api/auth/logout')

    # --- 确认退款（钱真的出去）---
    login('zhiban', 'Passw0rd!')
    resp = client.post(f'/api/refunds/{refund_id}/settle',
                       json={'method': 'original', 'transaction_no': 'WXREFUND001'})
    assert resp.status_code == 200, resp.get_json()
    settled = resp.get_json()['data']
    assert settled['status'] == 'settled'
    assert len(settled['txns']) == 1
    assert settled['txns'][0]['amount'] == 100.0
    assert settled['txns'][0]['transaction_no'] == 'WXREFUND001'
    client.post('/api/auth/logout')

    # 这时候钱才真的动了
    login('admin', 'Admin123!')
    order = client.get(f'/api/orders/{order_id}').get_json()['data']
    assert order['refunded_amount'] == 100.0
    assert order['refundable_amount'] == total - 100


def test_amount_cannot_exceed_refundable(client, admin_staff, login):
    login('admin', 'Admin123!')
    order_id, total, _store = _setup_paid_order(client, quantity=1)   # ¥32

    resp = _apply(client, order_id, 50)
    assert resp.status_code == 400
    assert '可退金额只剩 ¥32.00' in resp.get_json()['message']

    assert _apply(client, order_id, 32).status_code == 201


def test_pending_refunds_count_against_available(client, admin_staff, login):
    """两笔待审批的申请加起来不能超过实收——否则批完就该倒贴了"""
    login('admin', 'Admin123!')
    order_id, total, _store = _setup_paid_order(client, quantity=1)   # ¥32

    assert _apply(client, order_id, 20).status_code == 201
    # 第二笔只能退剩下的 12
    resp = _apply(client, order_id, 20)
    assert resp.status_code == 400
    assert '¥12.00' in resp.get_json()['message']
    assert _apply(client, order_id, 12).status_code == 201


def test_large_refund_needs_higher_permission(client, admin_staff, make_staff, login):
    """值班经理能批限额内（¥200），批不了大额——这是设计文档要求的角色区分"""
    login('admin', 'Admin123!')
    order_id, total, store_id = _setup_paid_order(client)   # ¥320
    make_staff('shouyin', 'cashier', store_id=store_id)
    make_staff('zhiban', 'shift_manager', store_id=store_id)
    make_staff('dianzhang', 'store_manager', store_id=store_id)

    # 小额：收银员发起，值班经理能批
    small_id = _apply(client, order_id, 100).get_json()['data']['id']
    # 大额：另一笔，超过 ¥200
    big_id = _apply(client, order_id, 220).get_json()['data']['id']
    client.post('/api/auth/logout')

    login('zhiban', 'Passw0rd!')
    assert client.post(f'/api/refunds/{small_id}/approve',
                       json={'remark': ''}).status_code == 200
    resp = client.post(f'/api/refunds/{big_id}/approve', json={'remark': ''})
    assert resp.status_code == 403
    assert '超过审批限额' in resp.get_json()['message']
    assert '审批大额退款' in resp.get_json()['message']
    client.post('/api/auth/logout')

    # 店长有 refund:approve:large，能批
    login('dianzhang', 'Passw0rd!')
    assert client.post(f'/api/refunds/{big_id}/approve',
                       json={'remark': '已核实'}).status_code == 200


def test_cannot_approve_own_refund(client, admin_staff, make_staff, login):
    """自己申请自己批，等于没有审批"""
    login('admin', 'Admin123!')
    order_id, _total, store_id = _setup_paid_order(client)
    make_staff('zhiban', 'shift_manager', store_id=store_id)
    client.post('/api/auth/logout')

    login('zhiban', 'Passw0rd!')
    refund_id = _apply(client, order_id, 50).get_json()['data']['id']
    resp = client.post(f'/api/refunds/{refund_id}/approve', json={'remark': ''})
    assert resp.status_code == 400
    assert '不能审批自己发起的' in resp.get_json()['message']


def test_reject_requires_reason(client, admin_staff, make_staff, login):
    login('admin', 'Admin123!')
    order_id, _total, store_id = _setup_paid_order(client)
    make_staff('shouyin', 'cashier', store_id=store_id)
    make_staff('zhiban', 'shift_manager', store_id=store_id)
    refund_id = _apply(client, order_id, 50).get_json()['data']['id']
    client.post('/api/auth/logout')

    login('zhiban', 'Passw0rd!')
    resp = client.post(f'/api/refunds/{refund_id}/reject', json={'remark': '  '})
    assert resp.status_code == 400
    assert '必须写原因' in resp.get_json()['message']

    assert client.post(f'/api/refunds/{refund_id}/reject',
                       json={'remark': '金额对不上'}).status_code == 200

    # 驳回之后是终态，不能再批准
    assert client.post(f'/api/refunds/{refund_id}/approve',
                       json={'remark': ''}).status_code == 400


def test_cannot_settle_without_approval(client, admin_staff, login):
    """不能跳过审批直接打款"""
    login('admin', 'Admin123!')
    order_id, _total, _store = _setup_paid_order(client)
    refund_id = _apply(client, order_id, 50).get_json()['data']['id']

    resp = client.post(f'/api/refunds/{refund_id}/settle', json={'method': 'cash'})
    assert resp.status_code == 400
    assert '要先审批通过' in resp.get_json()['message']


def test_partial_refunds_accumulate(client, admin_staff, make_staff, login):
    """一个订单可以退多次，每次记一笔流水"""
    login('admin', 'Admin123!')
    order_id, total, store_id = _setup_paid_order(client)   # ¥320

    for amount, method in ((32, 'original'), (64, 'cash')):
        refund_id = _apply_as_cashier(client, make_staff, login, store_id, order_id, amount)
        client.post(f'/api/refunds/{refund_id}/approve', json={'remark': 'ok'})
        client.post(f'/api/refunds/{refund_id}/settle', json={'method': method})

    order = client.get(f'/api/orders/{order_id}').get_json()['data']
    assert order['refunded_amount'] == 96.0
    assert order['refundable_amount'] == total - 96.0
    assert len(order['refunds']) == 2
    assert [t['method_label'] for r in order['refunds'] for t in r['txns']] == \
        ['原路退回', '现金']


def test_offline_backfill(client, admin_staff, make_staff, login):
    """线下退款：钱已经用现金退给顾客了，事后补录留痕"""
    login('admin', 'Admin123!')
    order_id, _total, store_id = _setup_paid_order(client, quantity=1)

    refund_id = _apply_as_cashier(client, make_staff, login, store_id, order_id, 32,
                                 reason='顾客当场退货，已现金退还', type_='offline')

    client.post(f'/api/refunds/{refund_id}/approve', json={'remark': '已知悉'})
    resp = client.post(f'/api/refunds/{refund_id}/settle', json={'method': 'cash'})
    assert resp.status_code == 200
    data = resp.get_json()['data']
    assert data['type_label'] == '线下补录'
    assert data['txns'][0]['method_label'] == '现金'
    # 现金退款没有第三方流水号，留空是正常的
    assert data['txns'][0]['transaction_no'] == ''


def test_fully_refunded_order_can_be_cancelled(client, admin_staff, make_staff, login):
    """全退完之后订单就能取消了——判断用的是净收款而不是实收"""
    login('admin', 'Admin123!')
    order_id, total, store_id = _setup_paid_order(client, quantity=1)

    resp = client.post(f'/api/orders/{order_id}/cancel')
    assert resp.status_code == 400
    assert '未退的收款' in resp.get_json()['message']

    refund_id = _apply_as_cashier(client, make_staff, login, store_id, order_id, total)
    client.post(f'/api/refunds/{refund_id}/approve', json={'remark': ''})
    client.post(f'/api/refunds/{refund_id}/settle', json={'method': 'original'})

    assert client.post(f'/api/orders/{order_id}/cancel').status_code == 200


def test_refund_scope(client, admin_staff, make_staff, login):
    """数据范围：店长只能看和操作本店订单的退款"""
    login('admin', 'Admin123!')
    order_id, _total, mine = _setup_paid_order(client, quantity=1)
    _other_order, _t, other = _setup_paid_order(client, quantity=1)
    refund_id = _apply(client, order_id, 10).get_json()['data']['id']

    make_staff('dianzhang', 'store_manager', store_id=other)
    client.post('/api/auth/logout')

    login('dianzhang', 'Passw0rd!')
    # 列表里看不到别店的退款单
    assert client.get('/api/refunds').get_json()['data']['pagination']['total'] == 0
    # 也批不了
    resp = client.post(f'/api/refunds/{refund_id}/approve', json={'remark': ''})
    assert resp.status_code == 403
    assert '其他门店' in resp.get_json()['message']


def test_revenue_subtracts_refunds(client, admin_staff, make_staff, login):
    """营业收入要减掉退款——只算实收的话退过款的单子会把营业额撑高"""
    login('admin', 'Admin123!')
    order_id, total, store_id = _setup_paid_order(client, quantity=1)   # ¥32

    before = client.get('/index').get_json()['data']['today']['revenue']
    assert before == 32.0

    refund_id = _apply_as_cashier(client, make_staff, login, store_id, order_id, 12)
    client.post(f'/api/refunds/{refund_id}/approve', json={'remark': ''})
    client.post(f'/api/refunds/{refund_id}/settle', json={'method': 'cash'})

    after = client.get('/index').get_json()['data']['today']['revenue']
    assert after == 20.0


def test_refund_is_audited(client, admin_staff, login):
    """退款的每一步都要留痕——设计文档点名要求"""
    login('admin', 'Admin123!')
    order_id, _total, _store = _setup_paid_order(client, quantity=1)
    refund_id = _apply(client, order_id, 10).get_json()['data']['id']
    client.post(f'/api/refunds/{refund_id}/approve', json={'remark': 'ok'})
    client.post(f'/api/refunds/{refund_id}/settle', json={'method': 'cash'})

    logs = client.get('/api/audit?search=REFUND').get_json()['data']['logs']
    actions = {log['action'] for log in logs}
    assert {'CREATE_REFUND', 'APPROVE_REFUND', 'SETTLE_REFUND'} <= actions
    assert all(log['resource'] == 'refund' for log in logs)
