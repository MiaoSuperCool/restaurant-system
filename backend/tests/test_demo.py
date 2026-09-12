"""演示数据测试

这是别人 clone 下来跑的第一条命令，跑不通就全完了——所以值得有个测试守住。
"""
from backend.app.demo import (
    CATEGORIES,
    DEMO_PASSWORD,
    DISHES,
    ORDERS,
    STAFF,
    STORES,
    seed_demo,
)


def test_seed_demo_runs_end_to_end(app):
    """一次灌完，各类数据都建出来了"""
    from backend.app.models import (
        Category,
        Dish,
        Order,
        Payment,
        Staff,
        Store,
        StoreDish,
    )

    with app.app_context():
        stats = seed_demo()

        assert stats['stores'] == len(STORES)
        assert stats['dishes'] == len(DISHES)
        assert stats['orders'] == len(ORDERS)
        assert Store.query.count() == len(STORES)
        assert Category.query.count() == len(CATEGORIES)
        assert Dish.query.count() == len(DISHES)
        # 9 个演示账号（不含 admin，那个不是演示数据建的）
        assert Staff.query.filter(Staff.username != 'admin').count() == len(STAFF)
        assert StoreDish.query.count() == 6
        assert Order.query.count() == len(ORDERS)
        assert Payment.query.count() == 7

        # 订单状态铺开了，打开页面才能看到「有要处理的单子」
        statuses = {order.status for order in Order.query.all()}
        assert statuses == {'pending', 'accepted', 'completed', 'cancelled'}
        # 有未收款的单子，也有收清的
        assert Order.query.filter(Order.paid_amount == 0).count() > 0
        assert Order.query.filter(Order.paid_amount > 0).count() > 0


def test_seed_demo_is_idempotent(app):
    """基础数据反复灌不会重复建（订单按设计每次新增）"""
    from backend.app.models import Dish, Staff, Store

    with app.app_context():
        seed_demo()
        second = seed_demo()

        assert second['stores'] == 0
        assert second['categories'] == 0
        assert second['dishes'] == 0
        assert second['staff'] == 0
        assert Store.query.count() == len(STORES)
        assert Dish.query.count() == len(DISHES)
        assert Staff.query.filter(Staff.username != 'admin').count() == len(STAFF)


def test_seed_demo_reset_clears_orders(app):
    """--reset 清掉订单重建，基础数据不动"""
    from backend.app.models import Order, Store

    with app.app_context():
        seed_demo()
        seed_demo(reset=True)

        assert Order.query.count() == len(ORDERS)          # 不是 24
        assert Store.query.count() == len(STORES)


def test_demo_accounts_can_login(client, app):
    """演示账号真的能登录——README 里会写「用 shouyin 登录试试」"""
    from backend.app.models import Staff

    with app.app_context():
        seed_demo()

    resp = client.post('/api/auth', json={'username': 'shouyin', 'password': DEMO_PASSWORD})
    assert resp.status_code == 200
    data = resp.get_json()['data']

    assert data['staff']['username'] == 'shouyin'
    assert data['data_scope'] == 'store'
    # 收银员：能接单收款，不能管菜单也不能看审计
    assert 'order:receive' in data['permissions']
    assert 'pay:collect' in data['permissions']
    assert 'menu:update' not in data['permissions']
    assert 'audit:view' not in data['permissions']

    with app.app_context():
        assert Staff.query.filter_by(username='shouyin').first() is not None
