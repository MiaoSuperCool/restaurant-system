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


def test_seed_demo_schedules_two_weeks(app):
    """班次和排班：每家店一套班次，真人各排两周

    排两周是**有意的**——「排班」页面要能翻页，只排本周的话点「下一周」
    是一片空白，看不出这是个能用的功能。
    """
    from datetime import date, timedelta

    from backend.app.models import ShiftAssignment, ShiftTemplate, Staff

    with app.app_context():
        stats = seed_demo()

        assert stats['shifts'] == len(STORES) * 3          # 每家店三个班次
        # **公用账号不排班**：那台设备背后不是一个具体的人
        shared_ids = {s.id for s in Staff.query.filter(Staff.is_shared.is_(True)).all()}
        assert not (ShiftAssignment.query
                    .filter(ShiftAssignment.staff_id.in_(shared_ids)).count())

        week_start = date.today() - timedelta(days=date.today().weekday())
        dates = {a.work_date for a in ShiftAssignment.query.all()}
        assert min(dates) == week_start
        assert max(dates) == week_start + timedelta(days=13)

        # 两头班真的排出来了（一天两个班），不然那个格子演示不了
        counts = {}
        for item in ShiftAssignment.query.all():
            counts[(item.staff_id, item.work_date)] = counts.get((item.staff_id, item.work_date), 0) + 1
        assert max(counts.values()) == 2

        # 班次时间没被写成空——排班表上显示的是「09:30-14:00」
        morning = ShiftTemplate.query.filter_by(name='早班').first()
        assert morning.start_time.strftime('%H:%M') == '09:30'


def test_seed_demo_is_idempotent(app):
    """基础数据反复灌不会重复建（订单按设计每次新增）"""
    from backend.app.models import Dish, ShiftAssignment, ShiftTemplate, Staff, Store

    with app.app_context():
        first = seed_demo()
        second = seed_demo()

        assert second['stores'] == 0
        assert second['categories'] == 0
        assert second['dishes'] == 0
        assert second['staff'] == 0
        # 班次和排班也是幂等的——不然反复跑会把同一周排上几十遍
        assert second['shifts'] == 0
        assert second['assignments'] == 0
        assert ShiftAssignment.query.count() == first['assignments']
        assert ShiftTemplate.query.count() == first['shifts']
        assert Store.query.count() == len(STORES)
        assert Dish.query.count() == len(DISHES)
        assert Staff.query.filter(Staff.username != 'admin').count() == len(STAFF)


def test_seed_demo_reset_clears_schedule_but_keeps_shifts(app):
    """--reset 清排班、**不清班次**——班次是配置（和菜单、券模板一类）"""
    from backend.app.models import ShiftAssignment, ShiftTemplate

    with app.app_context():
        first = seed_demo()
        seed_demo(reset=True)

        assert ShiftAssignment.query.count() == first['assignments']
        assert ShiftTemplate.query.count() == first['shifts']   # 没被删掉


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
