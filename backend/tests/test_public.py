"""顾客端公开接口测试

这套接口对任何人开放（顾客不进权限码体系），所以规则要测严：
能不能匿名访问、看得到什么、能不能遍历别人的订单。
"""
import time


def _setup(client):
    """建一家营业中的门店 + 一道带必选规格的菜

    返回 (store, dish, options)，options 是 {选项名: id}——
    这道菜的「份量」组是必选的，下单时不能不传。

    **调用前要先 login('admin', ...)**，而且**不会登出**——后面的测试
    往往还要继续用管理员身份操作。需要匿名身份的用例自己调 logout。
    """
    suffix = str(time.time_ns())[-6:]
    store = client.post('/api/stores', json={
        'code': f'P{suffix}', 'name': f'顾客测试店{suffix}',
        'address': '杭州市某某路 1 号', 'phone': '0571-88880000',
    }).get_json()['data']
    category = client.post('/api/categories', json={'name': f'顾客测试{suffix}'}).get_json()['data']
    dish = client.post('/api/dishes', json={
        'category_id': category['id'], 'name': f'测试面{suffix}', 'base_price': '20.00',
        'option_groups': [
            {'name': '份量', 'selection_type': 'single', 'is_required': True,
             'options': [{'name': '标准', 'extra_price': '0'},
                         {'name': '大份', 'extra_price': '5'}]},
        ],
    }).get_json()['data']
    options = {o['name']: o['id'] for g in dish['option_groups'] for o in g['options']}
    return store, dish, options


def _order(client, store_id, dish_id, option_ids, quantity=1, **extra):
    payload = {
        'store_id': store_id,
        'items': [{'dish_id': dish_id, 'quantity': quantity, 'option_ids': option_ids}],
    }
    payload.update(extra)
    return client.post('/api/public/orders', json=payload)


def test_public_endpoints_need_no_login(client, admin_staff, login):
    """顾客端所有接口都不需要登录——这是它和内部接口最大的区别"""
    login('admin', 'Admin123!')
    store, dish, opts = _setup(client)
    # 完全登出，模拟一个没有任何凭据的顾客
    client.post('/api/auth/logout')

    for resp in (
        client.get('/api/public/stores'),
        client.get(f'/api/public/stores/{store["id"]}/menu'),
    ):
        assert resp.status_code == 200, resp.get_json()


def test_csrf_exempt(client, admin_staff, login):
    """顾客端不校验 CSRF：小程序发请求不带 cookie，没有 CSRF 风险

    （测试环境下 CSRF 本来就是关的，这条主要靠代码里的 csrf.exempt 保证；
    这里退而求其次，验证「不带 X-CSRFToken 头也能下单」。）
    """
    login('admin', 'Admin123!')
    store, dish, opts = _setup(client)
    resp = _order(client, store['id'], dish['id'], [opts['标准']])
    assert resp.status_code == 201, resp.get_json()


def test_only_open_stores(client, admin_staff, login):
    """只返回营业中的门店：休息中的店点了也下不了单，不该出现在选店列表里"""
    login('admin', 'Admin123!')
    store, _dish, _c = _setup(client)
    store2 = client.post('/api/stores', json={
        'code': store['code'] + 'X', 'name': store['name'] + '二店',
    }).get_json()['data']
    client.put(f'/api/stores/{store2["id"]}', json={'business_status': 'resting'})

    codes = [s['code'] for s in client.get('/api/public/stores').get_json()['data']['stores']]
    assert store['code'] in codes
    assert store2['code'] not in codes

    # 休息中的店连菜单都不给
    resp = client.get(f'/api/public/stores/{store2["id"]}/menu')
    assert resp.status_code == 400
    assert '不接单' in resp.get_json()['message']


def test_menu_hides_delisted_dishes(client, admin_staff, login):
    """本店下架的菜不出现在顾客菜单里（内部菜单要显示，因为店长要管理）"""
    login('admin', 'Admin123!')
    store, dish, opts = _setup(client)

    names = [d['name'] for d in
             client.get(f'/api/public/stores/{store["id"]}/menu').get_json()['data']['dishes']]
    assert dish['name'] in names

    client.put(f'/api/stores/{store["id"]}/dishes/{dish["id"]}', json={'is_available': False})
    names = [d['name'] for d in
             client.get(f'/api/public/stores/{store["id"]}/menu').get_json()['data']['dishes']]
    assert dish['name'] not in names


def test_order_price_computed_server_side(client, admin_staff, login):
    """顾客端比内部端更该守「价格服务端算」——前端在顾客手里，改起来毫无成本"""
    login('admin', 'Admin123!')
    store, dish, opts = _setup(client)
    client.put(f'/api/stores/{store["id"]}/dishes/{dish["id"]}', json={'price': '25.00'})

    menu = client.get(f'/api/public/stores/{store["id"]}/menu').get_json()['data']['dishes']
    row = next(d for d in menu if d['dish_id'] == dish['id'])
    large = next(o['id'] for g in row['option_groups'] for o in g['options']
                 if o['name'] == '大份')

    # 夹带价格 → 未知字段，直接拒
    resp = client.post('/api/public/orders', json={
        'store_id': store['id'],
        'items': [{'dish_id': dish['id'], 'quantity': 2,
                   'option_ids': [large], 'unit_price': '0.01'}],
    })
    assert resp.status_code == 422

    resp = _order(client, store['id'], dish['id'], [large], quantity=2)
    order = resp.get_json()['data']
    # 本店价 25 + 大份 5 = 30，两份 60
    assert order['items'][0]['unit_price'] == 30.0
    assert order['payable_amount'] == 60.0
    assert order['operator_name'] == ''      # 顾客自助，没有操作人
    assert order['member_id'] is None        # 会员是二期的事


def test_order_returns_query_token(client, admin_staff, login):
    """下单返回查询令牌——光有单号是查不到订单的"""
    login('admin', 'Admin123!')
    store, dish, opts = _setup(client)
    order = _order(client, store['id'], dish['id'], [opts['标准']]).get_json()['data']

    assert order['query_token']
    assert len(order['query_token']) >= 16

    # 带令牌能查到
    resp = client.get(f'/api/public/orders/{order["order_no"]}',
                      query_string={'token': order['query_token']})
    assert resp.status_code == 200
    assert resp.get_json()['data']['order_no'] == order['order_no']


def test_order_lookup_requires_token(client, admin_staff, login):
    """单号可读也可猜，光凭单号不能查——否则遍历一遍就看到别人的订单了"""
    login('admin', 'Admin123!')
    store, dish, opts = _setup(client)
    order = _order(client, store['id'], dish['id'], [opts['标准']]).get_json()['data']

    # 不带令牌
    resp = client.get(f'/api/public/orders/{order["order_no"]}')
    assert resp.status_code == 404

    # 令牌不对
    resp = client.get(f'/api/public/orders/{order["order_no"]}',
                      query_string={'token': '0' * 24})
    assert resp.status_code == 404

    # 「单号不存在」和「令牌不对」返回同样的错误，不给探测者额外信息
    resp2 = client.get('/api/public/orders/NOT-EXIST-0001',
                       query_string={'token': '0' * 24})
    assert resp2.status_code == 404
    assert resp.get_json()['message'] == resp2.get_json()['message']


def test_mock_payment(client, admin_staff, login):
    """模拟支付：流水号带 MOCK 前缀，一眼看出不是微信真实的单号"""
    login('admin', 'Admin123!')
    store, dish, opts = _setup(client)
    order = _order(client, store['id'], dish['id'], [opts['标准']]).get_json()['data']
    url = f'/api/public/orders/{order["order_no"]}'
    token = {'token': order['query_token']}

    resp = client.post(f'{url}/pay', json={}, query_string=token)
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()['data']
    assert data['order']['is_paid'] is True
    assert data['payment']['transaction_no'].startswith('MOCK')

    # 再付一次会被拒
    resp = client.post(f'{url}/pay', json={}, query_string=token)
    assert resp.status_code == 400
    assert '已经付过' in resp.get_json()['message']


def test_customer_can_cancel_only_before_accept(client, admin_staff, login):
    """顾客只有「门店还没接单、也还没付款」时能自己取消"""
    login('admin', 'Admin123!')
    store, dish, opts = _setup(client)

    # 未接单未付款 → 能取消
    order1 = _order(client, store['id'], dish['id'], [opts['标准']]).get_json()['data']
    resp = client.post(f'/api/public/orders/{order1["order_no"]}/cancel',
                       query_string={'token': order1['query_token']})
    assert resp.status_code == 200
    assert resp.get_json()['data']['status'] == 'cancelled'

    # 门店已接单 → 不能自己取消
    order2 = _order(client, store['id'], dish['id'], [opts['标准']]).get_json()['data']
    client.post(f'/api/orders/{order2["id"]}/accept')
    resp = client.post(f'/api/public/orders/{order2["order_no"]}/cancel',
                       query_string={'token': order2['query_token']})
    assert resp.status_code == 400
    assert '请联系门店' in resp.get_json()['message']

    # 已付款 → 不能自己取消（要走退款，那条路有员工审批）
    order3 = _order(client, store['id'], dish['id'], [opts['标准']]).get_json()['data']
    client.post(f'/api/public/orders/{order3["order_no"]}/pay', json={},
                query_string={'token': order3['query_token']})
    resp = client.post(f'/api/public/orders/{order3["order_no"]}/cancel',
                       query_string={'token': order3['query_token']})
    assert resp.status_code == 400
    assert '退款' in resp.get_json()['message']


def test_option_validation_same_as_internal(client, admin_staff, login):
    """规格校验走同一套代码——必选组没选、单选组选了多个都要拒"""
    login('admin', 'Admin123!')
    store, dish, opts = _setup(client)

    # 必选组没选
    resp = _order(client, store['id'], dish['id'], [])
    assert resp.status_code == 400
    assert '必选' in resp.get_json()['message']

    # 选了不属于这道菜的选项
    resp = _order(client, store['id'], dish['id'], [99999])
    assert resp.status_code == 400
    assert '规格选项' in resp.get_json()['message']


def test_customer_order_shows_up_in_staff_list(client, admin_staff, login):
    """顾客下的单要能被门店看到——否则这条链路就是断的"""
    login('admin', 'Admin123!')
    store, dish, opts = _setup(client)
    order = _order(client, store['id'], dish['id'], [opts['标准']]).get_json()['data']

    body = client.get('/api/orders').get_json()['data']
    assert any(o['order_no'] == order['order_no'] for o in body['orders'])
