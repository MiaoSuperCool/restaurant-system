"""订单接口测试：算价、规格校验、状态流转、收款、数据范围、快照"""
import time


def _store(client, code='S001', name='解放路店'):
    return client.post('/api/stores', json={'code': code, 'name': name}).get_json()['data']


def _dish_with_options(client, name='牛肉面', base_price='15.00'):
    """建一道和设计文档里一样的牛肉面：份量（必选单选）+ 加料（可多选）"""
    category = client.post('/api/categories', json={'name': f'面食{time.time_ns()}'}).get_json()['data']
    dish = client.post('/api/dishes', json={
        'category_id': category['id'], 'name': name, 'base_price': base_price,
        'option_groups': [
            {'name': '份量', 'selection_type': 'single', 'is_required': True, 'options': [
                {'name': '中份', 'extra_price': '0'},
                {'name': '大份', 'extra_price': '3'},
            ]},
            {'name': '加料', 'selection_type': 'multiple', 'is_required': False, 'options': [
                {'name': '加蛋', 'extra_price': '2'},
            ]},
        ],
    }).get_json()['data']
    groups = {g['name']: g for g in dish['option_groups']}
    return dish, {
        'medium': groups['份量']['options'][0]['id'],
        'large': groups['份量']['options'][1]['id'],
        'egg': groups['加料']['options'][0]['id'],
    }


def _order(client, store_id, items, **extra):
    payload = {'store_id': store_id, 'items': items}
    payload.update(extra)
    return client.post('/api/orders', json=payload)


def test_price_is_computed_server_side(client, admin_staff, login):
    """设计文档的例子：牛肉面 ¥15，大份 +3、加蛋 +2

    本店把价格覆盖成 18 → 单价 = 18 + 3 + 2 = 23，两份 46。
    """
    login('admin', 'Admin123!')
    store = _store(client)
    dish, opt = _dish_with_options(client)
    client.put(f'/api/stores/{store["id"]}/dishes/{dish["id"]}', json={'price': '18.00'})

    resp = _order(client, store['id'], [
        {'dish_id': dish['id'], 'quantity': 2, 'option_ids': [opt['large'], opt['egg']]},
    ])
    assert resp.status_code == 201, resp.get_json()
    order = resp.get_json()['data']

    item = order['items'][0]
    assert item['dish_name'] == '牛肉面'
    assert item['unit_price'] == 23.0        # 18 + 3 + 2
    assert item['quantity'] == 2
    assert item['subtotal'] == 46.0
    assert item['options_text'] == '大份,加蛋'
    assert order['total_amount'] == 46.0
    assert order['payable_amount'] == 46.0
    assert order['paid_amount'] == 0.0
    assert order['is_paid'] is False
    assert order['status'] == 'pending'


def test_client_cannot_inject_price(client, admin_staff, login):
    """前端传价格会被拒——价格一律后端算，这是收银系统最基本的安全要求"""
    login('admin', 'Admin123!')
    store = _store(client)
    dish, opt = _dish_with_options(client)

    resp = _order(client, store['id'], [
        {'dish_id': dish['id'], 'quantity': 1, 'option_ids': [opt['medium']],
         'unit_price': '0.01', 'subtotal': '0.01'},
    ])
    # 未声明的字段被 schema 拒掉（marshmallow 默认 unknown=RAISE）
    assert resp.status_code == 422

    # 就算换个方式夹带，也不影响算出来的钱
    resp = _order(client, store['id'], [
        {'dish_id': dish['id'], 'quantity': 1, 'option_ids': [opt['medium']]},
    ])
    assert resp.get_json()['data']['total_amount'] == 15.0


def test_option_validation(client, admin_staff, login):
    login('admin', 'Admin123!')
    store = _store(client)
    dish, opt = _dish_with_options(client)

    # 必选组没选
    resp = _order(client, store['id'], [{'dish_id': dish['id'], 'quantity': 1, 'option_ids': []}])
    assert resp.status_code == 400
    assert '必选' in resp.get_json()['message']

    # 单选组选了两个
    resp = _order(client, store['id'], [
        {'dish_id': dish['id'], 'quantity': 1,
         'option_ids': [opt['medium'], opt['large']]},
    ])
    assert resp.status_code == 400
    assert '只能选一个' in resp.get_json()['message']

    # 选了不属于这道菜的选项
    resp = _order(client, store['id'], [
        {'dish_id': dish['id'], 'quantity': 1, 'option_ids': [99999]},
    ])
    assert resp.status_code == 400
    assert '规格选项' in resp.get_json()['message']


def test_same_option_twice_means_two_portions(client, admin_staff, login):
    """同一个加料传两次 = 加两份

    `option_ids` 本来就是数组，重复出现就是份数——请求结构不用再加一层嵌套，
    购物车的选中列表也天然支持。

    落库是**一条**记录带 `quantity=2`，不是两条重复的行：两条行的话，
    「这份面加了什么」和「加蛋卖了多少份」都得让调用方自己去合并。
    """
    login('admin', 'Admin123!')
    store = _store(client)
    dish, opt = _dish_with_options(client)

    resp = _order(client, store['id'], [
        {'dish_id': dish['id'], 'quantity': 1,
         'option_ids': [opt['medium'], opt['egg'], opt['egg']]},
    ])
    assert resp.status_code == 201
    item = resp.get_json()['data']['items'][0]

    # 15（基础价）+ 0（中份）+ 2×2（两份加蛋）= 19
    assert item['unit_price'] == 19.0
    assert item['options_text'] == '中份,加蛋×2'

    eggs = [o for o in item['options'] if o['dish_option_id'] == opt['egg']]
    assert len(eggs) == 1, '加蛋只该落一条记录'
    assert eggs[0]['quantity'] == 2
    assert eggs[0]['extra_price'] == 2.0, 'extra_price 是单价，不是小计'


def test_single_group_rejects_two_portions(client, admin_staff, login):
    """单选组里同一个选项传两次也算「选了多个」

    「中份 ×2」到底是什么意思？要两碗面应该改菜的数量，不是改份量的份数。
    """
    login('admin', 'Admin123!')
    store = _store(client)
    dish, opt = _dish_with_options(client)

    resp = _order(client, store['id'], [
        {'dish_id': dish['id'], 'quantity': 1,
         'option_ids': [opt['medium'], opt['medium']]},
    ])
    assert resp.status_code == 400
    assert '只能选一个' in resp.get_json()['message']


def test_unavailable_dish_cannot_be_ordered(client, admin_staff, login):
    """本店下架 / 全公司停售的菜都点不了"""
    login('admin', 'Admin123!')
    store = _store(client)
    dish, opt = _dish_with_options(client)
    item = {'dish_id': dish['id'], 'quantity': 1, 'option_ids': [opt['medium']]}

    # 本店下架
    client.put(f'/api/stores/{store["id"]}/dishes/{dish["id"]}', json={'is_available': False})
    resp = _order(client, store['id'], [item])
    assert resp.status_code == 400
    assert '已下架' in resp.get_json()['message']

    # 恢复上架后全公司停售
    client.delete(f'/api/stores/{store["id"]}/dishes/{dish["id"]}')
    client.put(f'/api/dishes/{dish["id"]}', json={'status': 'discontinued'})
    resp = _order(client, store['id'], [item])
    assert resp.status_code == 400
    assert '已停售' in resp.get_json()['message']


def test_order_no_is_readable(client, admin_staff, login):
    """单号做成「门店码-日期-当日序号」，顾客报单号、店员找单都要用"""
    login('admin', 'Admin123!')
    store = _store(client)
    dish, opt = _dish_with_options(client)
    item = {'dish_id': dish['id'], 'quantity': 1, 'option_ids': [opt['medium']]}

    first = _order(client, store['id'], [item]).get_json()['data']['order_no']
    second = _order(client, store['id'], [item]).get_json()['data']['order_no']

    assert first.startswith('S001-')
    assert first.endswith('-0001')
    assert second.endswith('-0002')

    # 另一家店从 0001 重新开始，各店不互相占号
    other = _store(client, code='S002', name='文化路店')
    third = _order(client, other['id'], [item]).get_json()['data']['order_no']
    assert third.startswith('S002-') and third.endswith('-0001')


def test_status_flow(client, admin_staff, login):
    """pending → accepted → completed；跳步和回退都要被拒"""
    login('admin', 'Admin123!')
    store = _store(client)
    dish, opt = _dish_with_options(client)
    order_id = _order(client, store['id'], [
        {'dish_id': dish['id'], 'quantity': 1, 'option_ids': [opt['medium']]},
    ]).get_json()['data']['id']

    # 待接单状态不能直接完成
    resp = client.post(f'/api/orders/{order_id}/complete')
    assert resp.status_code == 400
    assert '待接单' in resp.get_json()['message']

    assert client.post(f'/api/orders/{order_id}/accept').status_code == 200
    assert client.post(f'/api/orders/{order_id}/accept').status_code == 400   # 不能重复接单
    assert client.post(f'/api/orders/{order_id}/complete').status_code == 200

    # 完成之后是终态
    resp = client.post(f'/api/orders/{order_id}/cancel')
    assert resp.status_code == 400


def test_paid_order_cannot_be_cancelled(client, admin_staff, login):
    """已经收过钱的单子不能直接取消——钱得先退回去"""
    login('admin', 'Admin123!')
    store = _store(client)
    dish, opt = _dish_with_options(client)
    order_id = _order(client, store['id'], [
        {'dish_id': dish['id'], 'quantity': 1, 'option_ids': [opt['medium']]},
    ]).get_json()['data']['id']

    client.post(f'/api/orders/{order_id}/payments',
                json={'method': 'cash', 'amount': '15.00'})

    resp = client.post(f'/api/orders/{order_id}/cancel')
    assert resp.status_code == 400
    assert '退款' in resp.get_json()['message']


def test_multiple_payments(client, admin_staff, login):
    """组合支付：一个订单可以收多笔，金额累加；超额被拒"""
    login('admin', 'Admin123!')
    store = _store(client)
    dish, opt = _dish_with_options(client)
    order_id = _order(client, store['id'], [
        {'dish_id': dish['id'], 'quantity': 2, 'option_ids': [opt['large']]},
    ]).get_json()['data']['id']   # 单价 18（15+3），两份 36

    # 这条测的是「多笔累加」，和支付方式无关。一期这里随手写的是 balance，
    # 那会儿储值还没实现；现在储值真的能扣了，用它就得先挂会员——
    # 换成微信，别把两件事搅在一起
    r1 = client.post(f'/api/orders/{order_id}/payments',
                     json={'method': 'wechat', 'amount': '20.00'})
    assert r1.status_code == 201
    assert r1.get_json()['data']['order']['paid_amount'] == 20.0
    assert r1.get_json()['data']['order']['is_paid'] is False

    # 超收被拒
    resp = client.post(f'/api/orders/{order_id}/payments',
                       json={'method': 'cash', 'amount': '20.00'})
    assert resp.status_code == 400
    assert '还剩 ¥16.00' in resp.get_json()['message']

    r2 = client.post(f'/api/orders/{order_id}/payments',
                     json={'method': 'cash', 'amount': '16.00'})
    assert r2.get_json()['data']['order']['is_paid'] is True

    detail = client.get(f'/api/orders/{order_id}').get_json()['data']
    assert len(detail['payments']) == 2
    # 支付流水号挂在订单号后面，一眼看出是第几笔
    assert detail['payments'][0]['payment_no'].endswith('-P01')
    assert detail['payments'][1]['payment_no'].endswith('-P02')
    assert detail['payments'][0]['method_label'] == '微信支付'


def test_order_items_are_snapshots(client, admin_staff, login):
    """历史订单要还原当时的菜名和价格——运营改菜名涨价不该影响已下的单"""
    login('admin', 'Admin123!')
    store = _store(client)
    dish, opt = _dish_with_options(client)
    order_id = _order(client, store['id'], [
        {'dish_id': dish['id'], 'quantity': 1, 'option_ids': [opt['large']]},
    ]).get_json()['data']['id']

    # 之后改名 + 涨价
    client.put(f'/api/dishes/{dish["id"]}', json={'name': '红烧牛肉面', 'base_price': '20.00'})

    detail = client.get(f'/api/orders/{order_id}').get_json()['data']
    assert detail['items'][0]['dish_name'] == '牛肉面'   # 快照，不是新名字
    assert detail['items'][0]['unit_price'] == 18.0      # 15 + 3，不是涨价后的 23


def test_order_list_scope_and_filter(client, admin_staff, make_staff, login):
    """数据范围（店长只看本店）+ 状态筛选"""
    login('admin', 'Admin123!')
    s1 = _store(client, code='S001', name='解放路店')
    s2 = _store(client, code='S002', name='文化路店')
    dish, opt = _dish_with_options(client)
    item = {'dish_id': dish['id'], 'quantity': 1, 'option_ids': [opt['medium']]}

    first = _order(client, s1['id'], [item]).get_json()['data']
    _order(client, s2['id'], [item])
    client.post(f'/api/orders/{first["id"]}/accept')
    client.post('/api/auth/logout')

    make_staff('dianzhang', 'store_manager', store_id=s1['id'])
    login('dianzhang', 'Passw0rd!')

    body = client.get('/api/orders').get_json()['data']
    assert body['pagination']['total'] == 1     # 只看得到本店那一单
    assert body['orders'][0]['store_id'] == s1['id']

    # 状态筛选
    assert client.get('/api/orders?status=accepted').get_json()['data']['pagination']['total'] == 1
    assert client.get('/api/orders?status=pending').get_json()['data']['pagination']['total'] == 0

    # 别家店的订单详情看不了
    other_order = client.get('/api/orders?store_id=' + str(s2['id'])).get_json()['data']
    assert other_order['pagination']['total'] == 0


def test_cashier_can_collect_but_not_cancel(client, admin_staff, make_staff, login):
    """收银员能下单、接单、收款，但取消订单要 order:cancel（值班经理/店长才有）"""
    login('admin', 'Admin123!')
    store = _store(client)
    dish, opt = _dish_with_options(client)
    client.post('/api/auth/logout')

    make_staff('shouyin', 'cashier', store_id=store['id'])
    login('shouyin', 'Passw0rd!')

    item = {'dish_id': dish['id'], 'quantity': 1, 'option_ids': [opt['medium']]}
    resp = _order(client, store['id'], [item])
    assert resp.status_code == 201
    order_id = resp.get_json()['data']['id']

    assert client.post(f'/api/orders/{order_id}/accept').status_code == 200
    assert client.post(f'/api/orders/{order_id}/payments',
                       json={'method': 'cash', 'amount': '15.00'}).status_code == 201

    resp = client.post(f'/api/orders/{order_id}/cancel')
    assert resp.status_code == 403
    assert '取消订单' in resp.get_json()['message']


def test_operator_is_recorded(client, admin_staff, make_staff, login):
    """服务员用公用账号代点单时，记的是实际操作人而不是公用账号"""
    login('admin', 'Admin123!')
    store = _store(client)
    dish, opt = _dish_with_options(client)
    # 真正干活的服务员
    waitress = client.post('/api/staff', json={
        'username': 'xiaoli', 'real_name': '小李',
        'email': 'xiaoli@example.com', 'mobile': '13500001111',
        'password': 'Passw0rd!', 'store_id': store['id'],
    }).get_json()['data']
    client.post('/api/auth/logout')

    # 公用账号登录（它自己也是一条员工记录）
    make_staff('gongyong', 'waiter', store_id=store['id'], is_shared=True)
    login('gongyong', 'Passw0rd!')

    order = _order(client, store['id'], [
        {'dish_id': dish['id'], 'quantity': 1, 'option_ids': [opt['medium']]},
    ], operator_id=waitress['id']).get_json()['data']

    assert order['operator_id'] == waitress['id']
    assert order['operator_name'] == '小李'

    # 不传 operator_id 就记登录账号本身
    order2 = _order(client, store['id'], [
        {'dish_id': dish['id'], 'quantity': 1, 'option_ids': [opt['medium']]},
    ]).get_json()['data']
    assert order2['operator_name'] == 'gongyong'


def test_needs_order_permission(client, normal_staff, make_staff, login):
    """没有 order:view 的角色看不了订单列表"""
    login('staff', 'Staff123!')
    assert client.get('/api/orders').status_code == 403
    client.post('/api/auth/logout')

    # 后厨有 order:view（出单要看订单）但没有 order:create
    make_staff('chushi', 'kitchen')
    login('chushi', 'Passw0rd!')
    assert client.get('/api/orders').status_code == 200
    assert _order(client, 1, []).status_code == 403


def test_list_can_include_items(client, admin_staff, login):
    """订单列表默认不带明细，加 with_items 才带

    **出单页要**：后厨得知道做什么菜，只有单号和金额的单子没法做。
    网页端的列表不要——多查一遍明细是白花钱。
    """
    login('admin', 'Admin123!')
    store = _store(client)
    dish, opt = _dish_with_options(client)
    # 份量是必选组，不选会被拒——这里选「中份」（不加价）
    _order(client, store['id'], [
        {'dish_id': dish['id'], 'quantity': 2, 'option_ids': [opt['medium']]},
    ])

    plain = client.get('/api/orders').get_json()['data']['orders'][0]
    assert 'items' not in plain

    detailed = client.get('/api/orders', query_string={'with_items': 1}).get_json()['data']['orders'][0]
    assert [item['dish_name'] for item in detailed['items']] == ['牛肉面']
    assert detailed['items'][0]['quantity'] == 2
