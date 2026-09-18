"""经营报表

两张报表最容易出错的地方，这里各盯一条：

1. **口径**——营业额是不是「已收 − 已退」、取消的单算不算、没有单的日子有没有补零
2. **数据范围**——店长改个 URL 里的 store_id 能不能看到别家的数
"""
from datetime import date, datetime, timezone
from decimal import Decimal

from backend.app.extensions import db
from backend.app.models import Order, OrderItem, Payment


def _store(client, code='S001', name='解放路店'):
    return client.post('/api/stores', json={'code': code, 'name': name}).get_json()['data']


def _dish(client, name='牛肉面', price='15.00'):
    import time
    category = client.post('/api/categories',
                           json={'name': f'面食{time.time_ns()}'}).get_json()['data']
    return client.post('/api/dishes', json={
        'category_id': category['id'], 'name': name, 'base_price': price,
    }).get_json()['data']


def _order(app, store_id, dish_id, *, dish_name='牛肉面', quantity=1,
           unit_price='15.00', paid='15.00', refunded='0',
           status=Order.STATUS_COMPLETED, biz_date=None, hour=12):
    """造一单。

    `biz_date` / `hour` 都是**本地时间**——报表按本地日/本地小时分组，
    造数据时也得按本地时间来造，不然测的是时区换算而不是报表本身。
    """
    with app.app_context():
        local = datetime.combine(
            biz_date or date.today(), datetime.min.time().replace(hour=hour),
        ).astimezone()
        order = Order(
            store_id=store_id, order_no=f'T{datetime.now().timestamp()}',
            query_token='x',
            total_amount=Decimal(quantity) * Decimal(unit_price),
            payable_amount=Decimal(quantity) * Decimal(unit_price),
            paid_amount=Decimal(paid), refunded_amount=Decimal(refunded),
            status=status,
            created_at=local.astimezone(timezone.utc).replace(tzinfo=None),
        )
        # dish_name 是快照——报表按它分组，所以造数据时得和菜一致
        order.items.append(OrderItem(
            dish_id=dish_id, dish_name=dish_name, unit_price=Decimal(unit_price),
            quantity=quantity, subtotal=Decimal(quantity) * Decimal(unit_price),
        ))
        db.session.add(order)
        db.session.commit()
        return order.id


def _pay(app, order_id, method='wechat', amount='15.00'):
    with app.app_context():
        payment = Payment(method=method, amount=Decimal(amount),
                          payment_no=f'P{order_id}', order_id=order_id)
        payment.mark_success()
        db.session.add(payment)
        db.session.commit()


def _overview(client, **params):
    return client.get('/api/reports/overview',
                      query_string=params).get_json()['data']


# ---------- 口径 ----------

def test_revenue_is_paid_minus_refunded(app, client, admin_staff, login):
    """营业额 = 已收 − 已退

    只算 paid_amount 的话，退过款的单会把营业额撑高——那个数没法拿去交差。
    """
    login('admin', 'Admin123!')
    store, dish = _store(client), _dish(client)

    _order(app, store['id'], dish['id'], paid='100.00', refunded='0')
    _order(app, store['id'], dish['id'], paid='100.00', refunded='30.00')

    summary = _overview(client, days=1)['summary']
    assert summary['revenue'] == 170.0
    assert summary['refund_amount'] == 30.0
    assert summary['order_count'] == 2


def test_cancelled_orders_are_excluded_but_counted(app, client, admin_staff, login):
    """取消的单不算营业额，但**要能看出取消了几单**

    钱根本没进来过，算进营业额就是虚的；但店长想知道这个数。
    """
    login('admin', 'Admin123!')
    store, dish = _store(client), _dish(client)

    _order(app, store['id'], dish['id'], paid='50.00')
    _order(app, store['id'], dish['id'], paid='0', status=Order.STATUS_CANCELLED)

    summary = _overview(client, days=1)['summary']
    assert summary['revenue'] == 50.0
    assert summary['order_count'] == 1
    assert summary['cancelled_count'] == 1


def test_avg_order_is_zero_when_no_orders(client, admin_staff, login):
    """一单都没有时客单价给 0，不是 NaN——前端显示「NaN 元」很难看"""
    login('admin', 'Admin123!')
    summary = _overview(client, days=1)['summary']
    assert summary['order_count'] == 0
    assert summary['avg_order_amount'] == 0


def test_trend_has_a_row_for_every_day(app, client, admin_staff, login):
    """**没有单的日子也要有一行**——不然柱子会跳着排

    只在有单的日子返回的话，前端画出来的「7 天趋势」其实只有 3 根柱子，
    而且看不出哪天是空的（空和「没有这一天」看着一样）。
    """
    login('admin', 'Admin123!')
    store, dish = _store(client), _dish(client)
    _order(app, store['id'], dish['id'], paid='88.00')

    trend = _overview(client, days=7)['trend']
    assert len(trend) == 7
    assert trend[-1]['revenue'] == 88.0          # 今天在最后
    assert trend[0]['revenue'] == 0              # 六天前没单


def test_hour_buckets_use_local_time(app, client, admin_staff, login):
    """时段按**本地时间**分组

    库里存的是 UTC，直接按 UTC 的小时分组的话，「中午 12 点那波单」
    会被算成早上 4 点——排班的人看着一张全是凌晨的图，只会觉得系统坏了。
    """
    login('admin', 'Admin123!')
    store, dish = _store(client), _dish(client)
    _order(app, store['id'], dish['id'], paid='10.00', hour=12)
    _order(app, store['id'], dish['id'], paid='20.00', hour=18)

    by_hour = _overview(client, days=1)['by_hour']
    hours = {row['hour']: row for row in by_hour}
    assert 12 in hours and 18 in hours
    assert hours[12]['order_count'] == 1
    assert hours[18]['revenue'] == 20.0


def test_by_method_only_counts_successful_payments(app, client, admin_staff, login):
    """支付构成只看成功的流水——失败的和还没付的不算钱"""
    login('admin', 'Admin123!')
    store, dish = _store(client), _dish(client)
    order_id = _order(app, store['id'], dish['id'], paid='15.00')

    _pay(app, order_id, 'wechat', '15.00')
    with app.app_context():
        failed = Payment(method='cash', amount=Decimal('99.00'),
                         payment_no=f'F{order_id}', order_id=order_id,
                         status=Payment.STATUS_FAILED)
        db.session.add(failed)
        db.session.commit()

    methods = {row['method']: row for row in _overview(client, days=1)['by_method']}
    assert methods['wechat']['amount'] == 15.0
    assert 'cash' not in methods


def test_top_dishes_ranked_by_quantity(app, client, admin_staff, login):
    """菜品排行按**份数**排，不是按销售额"""
    login('admin', 'Admin123!')
    store = _store(client)
    cheap = _dish(client, '凉拌黄瓜', '12.00')
    pricey = _dish(client, '金牌猪软骨面', '38.00')

    _order(app, store['id'], cheap['id'], dish_name='凉拌黄瓜',
           quantity=10, unit_price='12.00', paid='120.00')
    _order(app, store['id'], pricey['id'], dish_name='金牌猪软骨面',
           quantity=2, unit_price='38.00', paid='76.00')

    rows = _overview(client, days=1)['top_dishes']
    assert [r['dish_name'] for r in rows] == ['凉拌黄瓜', '金牌猪软骨面']
    assert rows[0]['quantity'] == 10


def test_range_is_capped(app, client, admin_staff, login):
    """最多往回看 90 天——传个 3650 会把「拉回来在 Python 里切」变成拉十万行"""
    login('admin', 'Admin123!')
    data = _overview(client, start='2000-01-01', end='2026-12-31')
    assert data['range']['days'] == 90


# ---------- 数据范围 ----------

def test_store_manager_only_sees_own_store(app, client, admin_staff, make_staff, login):
    """**店长只看到自己那家**——by_store 里只有一行，没有门店对比"""
    login('admin', 'Admin123!')
    a, b = _store(client, 'S001', '解放路店'), _store(client, 'S002', '文三路店')
    dish = _dish(client)
    _order(app, a['id'], dish['id'], paid='100.00')
    _order(app, b['id'], dish['id'], paid='200.00')

    make_staff('dianzhang1', 'store_manager', store_id=a['id'])
    login('dianzhang1', 'Passw0rd!')

    data = _overview(client, days=1)
    assert data['summary']['revenue'] == 100.0        # 只算自己那家
    assert len(data['by_store']) == 1
    assert data['by_store'][0]['store_id'] == a['id']


def test_boss_sees_all_stores(app, client, admin_staff, login):
    """老板看到 6 家对比（这里是 2 家），按营业额倒序——「哪家做得好」是这张表要答的"""
    login('admin', 'Admin123!')
    a, b = _store(client, 'S001', '解放路店'), _store(client, 'S002', '文三路店')
    dish = _dish(client)
    _order(app, a['id'], dish['id'], paid='100.00')
    _order(app, b['id'], dish['id'], paid='200.00')

    rows = _overview(client, days=1)['by_store']
    assert [r['store_name'] for r in rows] == ['文三路店', '解放路店']


def test_manager_cannot_peek_at_other_store(app, client, admin_staff, make_staff, login):
    """**店长改 URL 里的 store_id 也看不到别家的数**

    这条要是漏了，整个报表模块就白做了——范围是唯一挡住他的东西。
    """
    login('admin', 'Admin123!')
    a, b = _store(client, 'S001', '解放路店'), _store(client, 'S002', '文三路店')

    make_staff('dianzhang2', 'store_manager', store_id=a['id'])
    login('dianzhang2', 'Passw0rd!')

    assert client.get('/api/reports/overview',
                      query_string={'store_id': a['id']}).status_code == 200
    resp = client.get('/api/reports/overview',
                      query_string={'store_id': b['id']})
    assert resp.status_code == 403
    assert '无权查看其他门店' in resp.get_json()['message']


def test_report_needs_a_permission_code(app, client, admin_staff, make_staff, login):
    """**权限码和范围是两件事**

    收银员能看订单（`order:view`），但没有 `report:store`——经营数据
    （哪道菜卖了多少、一天做多少生意）不该给他。店长有 `report:store`，
    再加上范围收窄，才是「本店报表」。
    """
    login('admin', 'Admin123!')
    store = _store(client)

    make_staff('shouyin1', 'cashier', store_id=store['id'])
    login('shouyin1', 'Passw0rd!')
    assert client.get('/api/reports/overview').status_code == 403

    make_staff('dianzhang3', 'store_manager', store_id=store['id'])
    login('dianzhang3', 'Passw0rd!')
    assert client.get('/api/reports/overview',
                      query_string={'days': 1}).status_code == 200
