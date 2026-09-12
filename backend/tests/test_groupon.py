"""团购券核销测试

重点：同一张券码不能核销两次。这是单开一张表的主要理由——
靠代码「先查再插」在并发下挡不住，得让数据库的唯一约束来。
"""
import time


def _setup_order(client, quantity=2):
    """建一单未付款的订单：牛肉面 ¥32 × N"""
    suffix = str(time.time_ns())[-6:]
    store = client.post('/api/stores', json={
        'code': f'G{suffix}', 'name': f'团购测试店{suffix}',
    }).get_json()['data']
    category = client.post('/api/categories', json={'name': f'团购测试{suffix}'}).get_json()['data']
    dish = client.post('/api/dishes', json={
        'category_id': category['id'], 'name': f'团购面{suffix}', 'base_price': '32.00',
    }).get_json()['data']
    order = client.post('/api/orders', json={
        'store_id': store['id'],
        'items': [{'dish_id': dish['id'], 'quantity': quantity, 'option_ids': []}],
    }).get_json()['data']
    return order['id'], order['payable_amount'], store['id']


def _verify(client, order_id, code, amount, platform='meituan'):
    return client.post(f'/api/orders/{order_id}/vouchers', json={
        'code': code, 'amount': str(amount), 'platform': platform,
    })


def test_verify_creates_record_and_payment(client, admin_staff, login):
    """核销同时产生两样东西：核销记录（对账用）+ 收款记录（记账用）"""
    login('admin', 'Admin123!')
    order_id, total, _store = _setup_order(client)   # ¥64

    resp = _verify(client, order_id, 'MT20260912001', 64)
    assert resp.status_code == 201, resp.get_json()
    data = resp.get_json()['data']

    assert data['voucher']['code'] == 'MT20260912001'
    assert data['voucher']['platform_label'] == '美团'
    assert data['voucher']['amount'] == 64.0
    # 引用夹具本身而不是硬编码名字——改夹具时不会连带挂掉
    assert data['voucher']['verified_by_name'] == admin_staff.real_name

    order = data['order']
    assert order['paid_amount'] == 64.0
    assert order['is_paid'] is True

    detail = client.get(f'/api/orders/{order_id}').get_json()['data']
    groupon_payments = [p for p in detail['payments'] if p['method'] == 'groupon']
    assert len(groupon_payments) == 1
    # 收款流水号里存的是券码——对账时一眼能对上
    assert groupon_payments[0]['transaction_no'] == 'MT20260912001'
    assert groupon_payments[0]['method_label'] == '团购券'


def test_same_code_cannot_be_verified_twice(client, admin_staff, login):
    """同一张券不能核销两次——顾客拿着同一张券跑两家店是真实会发生的事"""
    login('admin', 'Admin123!')
    first_order, _total, _store = _setup_order(client, quantity=2)
    second_order, _t2, _s2 = _setup_order(client, quantity=2)

    assert _verify(client, first_order, 'MT-DUP-001', 32).status_code == 201

    resp = _verify(client, second_order, 'MT-DUP-001', 32)
    assert resp.status_code == 400
    message = resp.get_json()['message']
    assert '已经核销过' in message
    # 提示里要能看出是谁、什么时候、在哪单核销的——只报「重复」帮不了收银员
    assert admin_staff.real_name in message
    first_order_no = client.get(f'/api/orders/{first_order}').get_json()['data']['order_no']
    assert first_order_no in message

    # 第二单没被影响
    detail = client.get(f'/api/orders/{second_order}').get_json()['data']
    assert detail['paid_amount'] == 0


def test_amount_cannot_exceed_unpaid(client, admin_staff, login):
    """团购券只能抵扣，不找零"""
    login('admin', 'Admin123!')
    order_id, total, _store = _setup_order(client, quantity=1)   # ¥32

    resp = _verify(client, order_id, 'MT-BIG-001', total + 10)
    assert resp.status_code == 400
    assert '超过未付部分' in resp.get_json()['message']
    assert '不找零' in resp.get_json()['message']


def test_partial_groupon_plus_cash(client, admin_staff, login):
    """团购券抵扣一部分、剩下的现金付——组合支付里也要能用"""
    login('admin', 'Admin123!')
    order_id, total, _store = _setup_order(client)   # ¥64

    assert _verify(client, order_id, 'MT-PART-001', 40).status_code == 201
    order = client.get(f'/api/orders/{order_id}').get_json()['data']
    assert order['paid_amount'] == 40.0
    assert order['is_paid'] is False

    client.post(f'/api/orders/{order_id}/payments',
                json={'method': 'cash', 'amount': str(total - 40)})
    order = client.get(f'/api/orders/{order_id}').get_json()['data']
    assert order['is_paid'] is True
    assert len(order['payments']) == 2


def test_cancelled_order_cannot_verify(client, admin_staff, login):
    login('admin', 'Admin123!')
    order_id, _total, _store = _setup_order(client, quantity=1)
    client.post(f'/api/orders/{order_id}/cancel')

    resp = _verify(client, order_id, 'MT-CANCEL-001', 10)
    assert resp.status_code == 400
    assert '已取消' in resp.get_json()['message']


def test_scope_and_permission(client, admin_staff, make_staff, login):
    """数据范围：店长只能核销本店订单的券"""
    login('admin', 'Admin123!')
    order_id, total, mine = _setup_order(client)
    _other_order, _t, other = _setup_order(client)

    make_staff('shouyin', 'cashier', store_id=mine)
    make_staff('other_shouyin', 'cashier', store_id=other)
    client.post('/api/auth/logout')

    # 本店收银员能核销（coupon:verify 在收银员权限里）
    login('shouyin', 'Passw0rd!')
    assert _verify(client, order_id, 'MT-SCOPE-001', 10).status_code == 201
    client.post('/api/auth/logout')

    # 别店收银员核销本店订单 → 403
    login('other_shouyin', 'Passw0rd!')
    resp = _verify(client, order_id, 'MT-SCOPE-002', 10)
    assert resp.status_code == 403
    assert '其他门店' in resp.get_json()['message']


def test_voucher_list_and_scope(client, admin_staff, make_staff, login):
    """核销记录列表——月底拿去和平台对账用"""
    login('admin', 'Admin123!')
    order_id, _total, mine = _setup_order(client)
    _other, _t, other = _setup_order(client)
    _verify(client, order_id, 'MT-LIST-001', 10)
    _verify(client, _other, 'MT-LIST-002', 10)

    body = client.get('/api/groupon-vouchers').get_json()['data']
    assert body['pagination']['total'] == 2
    assert {v['code'] for v in body['vouchers']} == {'MT-LIST-001', 'MT-LIST-002'}

    make_staff('dianzhang', 'store_manager', store_id=mine)
    client.post('/api/auth/logout')

    login('dianzhang', 'Passw0rd!')
    body = client.get('/api/groupon-vouchers').get_json()['data']
    assert body['pagination']['total'] == 1
    assert body['vouchers'][0]['code'] == 'MT-LIST-001'


def test_verify_is_audited(client, admin_staff, login):
    """核销是设计文档点名的关键动作"""
    login('admin', 'Admin123!')
    order_id, _total, _store = _setup_order(client, quantity=1)
    _verify(client, order_id, 'MT-AUDIT-001', 10)

    logs = client.get('/api/audit?search=GROUPON').get_json()['data']['logs']
    assert any(log['action'] == 'VERIFY_GROUPON' for log in logs)
    assert all(log['resource'] == 'groupon_voucher' for log in logs)


def test_refund_after_groupon(client, admin_staff, make_staff, login):
    """团购券核销进来的钱也能退——退款不关心钱是怎么进来的"""
    login('admin', 'Admin123!')
    order_id, total, store_id = _setup_order(client)   # ¥64
    _verify(client, order_id, 'MT-REFUND-001', total)

    make_staff('shouyin', 'cashier', store_id=store_id)
    client.post('/api/auth/logout')
    login('shouyin', 'Passw0rd!')
    refund_id = client.post(f'/api/refunds/orders/{order_id}', json={
        'amount': str(total), 'reason': '团购券顾客要求退回', 'type': 'online',
    }).get_json()['data']['id']
    client.post('/api/auth/logout')

    login('admin', 'Admin123!')
    client.post(f'/api/refunds/{refund_id}/approve', json={'remark': 'ok'})
    client.post(f'/api/refunds/{refund_id}/settle', json={'method': 'original'})

    order = client.get(f'/api/orders/{order_id}').get_json()['data']
    assert order['refunded_amount'] == 64.0
    assert order['refundable_amount'] == 0.0
