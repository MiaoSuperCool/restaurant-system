"""老系统共存：ID 映射、同步记录、对账

对账那部分是**先造出错账，再看它抓不抓得住**——对账功能最怕的不是算错，
是「什么都对得上」这种假太平：真有问题它一声不吭，那这个功能还不如不做。
"""

import pytest

from backend.app.errors import BusinessError, NotFoundError
from backend.app.extensions import db
from backend.app.models import Balance, LegacyMap, Member, Reconciliation, SyncRecord
from backend.app.services import LegacyService, ReconciliationService


def _member(app, mobile='13800000001', nickname='测试会员'):
    with app.app_context():
        member = Member(mobile=mobile, nickname=nickname)
        db.session.add(member)
        db.session.commit()
        return member.id


def _balance(app, member_id, principal='100.00', bonus='0'):
    from decimal import Decimal
    with app.app_context():
        db.session.add(Balance(member_id=member_id, principal=Decimal(principal),
                               bonus=Decimal(bonus)))
        db.session.commit()


# ---------- ID 映射 ----------

def test_bind_and_resolve(as_admin, app, admin_staff, login):
    """记一条映射，再按老号查回来——客服那个动作"""
    member_id = _member(app)

    with as_admin():
        mapping = LegacyService.bind(LegacyMap.TARGET_MEMBER, member_id, 'M0010086')
        assert mapping.legacy_id == 'M0010086'

        assert LegacyService.resolve_member('M0010086').id == member_id
        # 没迁过的老号返回 None——**「查不到」是个正常答案，不该是 404**
        assert LegacyService.resolve_member('M0099999') is None


def test_bind_checks_target_exists(as_admin, app, admin_staff, login):
    """多态引用数据库拦不住，只能应用层拦——所以这条一定要有测试"""
    with as_admin():
        with pytest.raises(NotFoundError, match='不存在'):
            LegacyService.bind(LegacyMap.TARGET_MEMBER, 999999, 'M001')

        with pytest.raises(BusinessError, match='不认识的对象类型'):
            LegacyService.bind('order', 1, 'M001')


def test_bind_is_unique_both_ways(as_admin, app, admin_staff, login):
    """两个方向都得唯一，不然一个老号能对上新系统的两个人"""
    a, b = _member(app, '13800000001'), _member(app, '13800000002')

    with as_admin():
        LegacyService.bind(LegacyMap.TARGET_MEMBER, a, 'M001')

        with pytest.raises(BusinessError, match='已经映射过了'):
            LegacyService.bind(LegacyMap.TARGET_MEMBER, b, 'M001')

        with pytest.raises(BusinessError, match='已经有一个老系统的号'):
            LegacyService.bind(LegacyMap.TARGET_MEMBER, a, 'M002')


def test_unbind_leaves_a_trace(as_admin, app, admin_staff, login):
    """删映射要留痕——它是「这条老数据迁到哪去了」的唯一线索"""
    from backend.app.models import AuditLog

    member_id = _member(app)
    with as_admin():
        mapping = LegacyService.bind(LegacyMap.TARGET_MEMBER, member_id, 'M001')
        LegacyService.unbind(mapping.id)

        assert LegacyService.resolve_member('M001') is None
        assert AuditLog.query.filter_by(action='UNBIND_LEGACY_ID').count() == 1


# ---------- 同步记录 ----------

def test_sync_summary_counts_by_status(as_admin, app, admin_staff, login):
    with as_admin():
        LegacyService.record_sync('pull', 'member', 'M001')
        LegacyService.record_sync('pull', 'member', 'M002')
        LegacyService.record_sync('pull', 'member', 'M003',
                                  status=SyncRecord.STATUS_FAILED, message='超时')
        db.session.commit()

        summary = LegacyService.sync_summary()
        assert summary == {'success': 2, 'failed': 1, 'pending': 0, 'total': 3}


def test_sync_records_filter(as_admin, app, admin_staff, login):
    with as_admin():
        LegacyService.record_sync('pull', 'member', 'M001')
        LegacyService.record_sync('push', 'order', 'S001-1',
                                  status=SyncRecord.STATUS_FAILED, message='ERP 超时')
        db.session.commit()

        failed = LegacyService.get_sync_records(status='failed').items
        assert [r.ref for r in failed] == ['S001-1']
        assert failed[0].message == 'ERP 超时'   # 失败原因原样留着，不翻译


# ---------- 对账：储值 ----------

def _run(app, category, store_id=None, biz_date=None):
    import datetime
    with app.app_context():
        return ReconciliationService.run(
            biz_date or datetime.date.today(), category, store_id=store_id,
        ).to_dict()


def test_balance_matches_when_ledger_is_clean(as_admin, app, admin_staff, login):
    """账和流水一致时，差异必须是 0

    账上 100 = 充值 60 + 赠送 40
    """
    from decimal import Decimal

    from backend.app.models import BalanceTxn

    member_id = _member(app)
    _balance(app, member_id, '100.00')
    with app.app_context():
        db.session.add(BalanceTxn(
            member_id=member_id, type=BalanceTxn.TYPE_RECHARGE,
            principal_delta=Decimal('100.00'), bonus_delta=Decimal('0'),
            principal_after=Decimal('100.00'), bonus_after=Decimal('0'),
        ))
        db.session.commit()

    with as_admin():
        record = _run(app, 'balance')
    assert record['status'] == 'matched'
    assert record['diff_amount'] == 0
    assert record['detail'] == []


def test_balance_catches_a_missing_transaction(as_admin, app, admin_staff, login):
    """**账上少了钱要抓得住**——这正是「那 80 万一分不差」要防的事"""
    from decimal import Decimal

    from backend.app.models import BalanceTxn

    member_id = _member(app)
    _balance(app, member_id, '78.00')          # 账上只剩 78
    with app.app_context():
        db.session.add(BalanceTxn(             # 流水说进过 100
            member_id=member_id, type=BalanceTxn.TYPE_RECHARGE,
            principal_delta=Decimal('100.00'), bonus_delta=Decimal('0'),
            principal_after=Decimal('100.00'), bonus_after=Decimal('0'),
        ))
        db.session.commit()

    with as_admin():
        record = _run(app, 'balance')
    assert record['status'] == 'mismatched'
    assert record['diff_amount'] == -22.0       # 实际 − 期望，负数 = 账上少了
    assert record['detail'][0]['member_name'] == '测试会员'
    assert record['detail'][0]['diff'] == -22.0


def test_balance_compares_member_by_member_not_the_total(as_admin, app, admin_staff, login):
    """**汇总对得上不代表没问题**：一个人多 100、一个人少 100，总数是平的

    这条测试盯的就是「别图省事直接 SUM 两边相减」。
    """
    from decimal import Decimal

    from backend.app.models import BalanceTxn

    over, under = _member(app, '13800000001', '多出来的'), _member(app, '13800000002', '少掉的')
    _balance(app, over, '200.00')
    _balance(app, under, '0')

    with app.app_context():
        for member_id, delta in ((over, '100.00'), (under, '100.00')):
            db.session.add(BalanceTxn(
                member_id=member_id, type=BalanceTxn.TYPE_RECHARGE,
                principal_delta=Decimal(delta), bonus_delta=Decimal('0'),
                principal_after=Decimal(delta), bonus_after=Decimal('0'),
            ))
        db.session.commit()

    with as_admin():
        record = _run(app, 'balance')

    assert record['expected_amount'] == record['actual_amount'] == 200.0
    assert record['diff_amount'] == 0           # **总额正好抵消**
    assert record['status'] == 'mismatched'     # 但仍然是错的——不能只看总额
    assert record['mismatch_count'] == 2
    assert len(record['detail']) == 2


# ---------- 对账：订单 ----------

def _paid_order(app, store_id, amount='50.00', biz_date=None, with_payment=True):
    """造一笔「已收款」的订单；with_payment=False 就是只写了订单没写支付流水"""
    import datetime
    from decimal import Decimal

    from backend.app.models import Order, Payment

    with app.app_context():
        order = Order(
            store_id=store_id, order_no=f'T-{datetime.datetime.now().timestamp()}',
            query_token='x', total_amount=Decimal(amount),
            payable_amount=Decimal(amount), paid_amount=Decimal(amount),
        )
        if biz_date is not None:
            # 按本地自然日造下单时间：取当天中午，离两边的边界都远
            local_noon = datetime.datetime.combine(
                biz_date, datetime.time(12, 0),
            ).astimezone()
            order.created_at = local_noon.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        db.session.add(order)
        db.session.flush()
        if with_payment:
            payment = Payment(method='cash', amount=Decimal(amount),
                              payment_no=f'{order.order_no}-P01')
            payment.mark_success()
            order.payments.append(payment)
        db.session.commit()
        return order.id


def _store(client, code='S001', name='解放路店'):
    return client.post('/api/stores', json={'code': code, 'name': name}).get_json()['data']


def test_order_reconciliation_matches(as_admin, app, client, admin_staff, login):
    """订单和支付流水一致时差异为 0"""
    import datetime

    login('admin', 'Admin123!')
    store = _store(client)
    today = datetime.date.today()
    _paid_order(app, store['id'], '50.00')
    _paid_order(app, store['id'], '30.00')

    with as_admin():
        record = _run(app, 'order', store_id=store['id'], biz_date=today)
    assert record['status'] == 'matched'
    assert record['actual_amount'] == 80.0


def test_order_reconciliation_catches_a_payment_that_never_landed(as_admin, app, client,
                                                                  admin_staff, login):
    """订单说收钱了、支付流水里没有——**这种账最吓人**，得抓得住"""
    import datetime

    login('admin', 'Admin123!')
    store = _store(client)
    today = datetime.date.today()
    _paid_order(app, store['id'], '50.00')
    _paid_order(app, store['id'], '30.00', with_payment=False)   # 只写了订单

    with as_admin():
        record = _run(app, 'order', store_id=store['id'], biz_date=today)
    assert record['status'] == 'mismatched'
    assert record['diff_amount'] == 30.0        # 账上多出来的这 30
    assert record['expected_amount'] == 50.0
    assert len(record['detail']) == 1


def test_order_reconciliation_only_counts_that_day(as_admin, app, client, admin_staff, login):
    """按天对账——别的日子的单子不能被算进来"""
    import datetime

    login('admin', 'Admin123!')
    store = _store(client)
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    _paid_order(app, store['id'], '50.00', biz_date=yesterday)
    _paid_order(app, store['id'], '30.00', biz_date=today)

    with as_admin():
        record = _run(app, 'order', store_id=store['id'], biz_date=today)
    assert record['actual_amount'] == 30.0


def test_order_reconciliation_needs_a_store(as_admin, app, admin_staff, login):
    import datetime
    with as_admin():
        with pytest.raises(BusinessError, match='指定门店'):
            ReconciliationService.run(datetime.date.today(), 'order')


def test_unknown_category_is_rejected(as_admin, app, admin_staff, login):
    import datetime
    with as_admin():
        with pytest.raises(BusinessError, match='不认识的对账类别'):
            ReconciliationService.run(datetime.date.today(), 'stock')


# ---------- 对账：重跑 ----------

def test_rerun_replaces_the_same_day_record(as_admin, app, admin_staff, login):
    """同一天同一个类别只留一条——对账是「重新下一遍结论」，不是攒历史"""

    from decimal import Decimal

    from backend.app.models import BalanceTxn

    member_id = _member(app)
    _balance(app, member_id, '50.00')
    with app.app_context():
        db.session.add(BalanceTxn(
            member_id=member_id, type=BalanceTxn.TYPE_RECHARGE,
            principal_delta=Decimal('50.00'), bonus_delta=Decimal('0'),
            principal_after=Decimal('50.00'), bonus_after=Decimal('0'),
        ))
        db.session.commit()

    with as_admin():
        _run(app, 'balance')
        _run(app, 'balance')
        assert Reconciliation.query.filter_by(category='balance').count() == 1


# ---------- 接口 ----------

def test_maps_api(as_admin, app, client, admin_staff, login):
    """建映射 → 列表 → 按老号查 → 删掉，整条走一遍"""
    member_id = _member(app)
    login('admin', 'Admin123!')

    resp = client.post('/api/legacy/maps', json={
        'target_type': 'member', 'target_id': member_id,
        'legacy_id': 'M0001001', 'remark': '手工补录',
    })
    assert resp.status_code == 201
    map_id = resp.get_json()['data']['id']

    listed = client.get('/api/legacy/maps', query_string={'search': 'M0001'})
    assert [m['legacy_id'] for m in listed.get_json()['data']['maps']] == ['M0001001']

    resolved = client.get('/api/legacy/maps/resolve',
                          query_string={'legacy_id': 'M0001001'}).get_json()['data']
    assert resolved['found'] is True
    assert resolved['target']['id'] == member_id

    # 没迁过的号：found=False，而不是 404
    missing = client.get('/api/legacy/maps/resolve',
                         query_string={'legacy_id': 'M9999'}).get_json()['data']
    assert missing['found'] is False
    assert missing['target'] is None

    assert client.delete(f'/api/legacy/maps/{map_id}').status_code == 200
    assert client.get('/api/legacy/maps').get_json()['data']['maps'] == []


def test_sync_records_api(as_admin, app, client, admin_staff, login):
    login('admin', 'Admin123!')
    with as_admin():
        LegacyService.record_sync('pull', 'member', 'M001')
        LegacyService.record_sync('pull', 'member', 'M002',
                                  status=SyncRecord.STATUS_FAILED, message='连接超时')
        db.session.commit()

    data = client.get('/api/legacy/sync-records').get_json()['data']
    assert data['summary'] == {'success': 1, 'failed': 1, 'pending': 0, 'total': 2}
    assert len(data['records']) == 2

    only_failed = client.get('/api/legacy/sync-records',
                             query_string={'status': 'failed'}).get_json()['data']
    assert [r['ref'] for r in only_failed['records']] == ['M002']
    assert only_failed['records'][0]['message'] == '连接超时'


def test_reconcile_api_returns_the_diff_detail(as_admin, app, client, admin_staff, login):
    """跑对账要**把差异明细一起返回**——只说「有差异」，财务还得自己去翻"""
    from decimal import Decimal

    from backend.app.models import BalanceTxn

    login('admin', 'Admin123!')
    member_id = _member(app)
    _balance(app, member_id, '78.00')
    with app.app_context():
        db.session.add(BalanceTxn(
            member_id=member_id, type=BalanceTxn.TYPE_RECHARGE,
            principal_delta=Decimal('100.00'), bonus_delta=Decimal('0'),
            principal_after=Decimal('100.00'), bonus_after=Decimal('0'),
        ))
        db.session.commit()

    record = client.post('/api/legacy/reconciliations/run',
                         json={'category': 'balance'}).get_json()['data']
    assert record['status'] == 'mismatched'
    assert record['mismatch_count'] == 1
    assert record['detail'][0]['member_name'] == '测试会员'
    assert record['detail'][0]['diff'] == -22.0

    # 再查一次列表，结论是留档的
    listed = client.get('/api/legacy/reconciliations').get_json()['data']['records']
    assert len(listed) == 1
    assert listed[0]['diff_amount'] == -22.0


def test_reconcile_api_rejects_a_bad_store(as_admin, app, client, admin_staff, login):
    """门店 id 写错要报错，不能算出个「0 对 0、对得上」"""
    login('admin', 'Admin123!')
    resp = client.post('/api/legacy/reconciliations/run',
                       json={'category': 'order', 'store_id': 999999})
    assert resp.status_code == 404

    # 订单对账不传门店也不行
    assert client.post('/api/legacy/reconciliations/run',
                       json={'category': 'order'}).status_code == 400


def test_legacy_needs_sync_view(app, client, make_staff, login):
    """没有 sync:view 的人进不来——收银员不干对账和对接的活"""
    make_staff('shouyin9', 'cashier')
    login('shouyin9', 'Passw0rd!')

    assert client.get('/api/legacy/maps').status_code == 403
    assert client.get('/api/legacy/sync-records').status_code == 403
    assert client.get('/api/legacy/reconciliations').status_code == 403
    assert client.post('/api/legacy/reconciliations/run',
                       json={'category': 'balance'}).status_code == 403


# ---------- seed-demo --reset 的清理顺序 ----------

def test_reset_clears_legacy_tables_before_members(app, as_admin):
    """`--reset` 要把老系统那三张表**一起**清掉，而且得在会员之前

    不清的话：会员被删了，`LegacyMap` 成了指向空气的孤儿记录；
    再跑迁移时老号被当成「迁过了」跳过——**储值那笔钱就凭空消失了**。
    """
    from decimal import Decimal

    from backend.app.demo import _clear_business_data
    from backend.app.models import BalanceTxn

    member_id = _member(app)
    _balance(app, member_id, '100.00')
    with app.app_context():
        db.session.add(BalanceTxn(
            member_id=member_id, type=BalanceTxn.TYPE_MIGRATE,
            principal_delta=Decimal('100.00'), bonus_delta=Decimal('0'),
            principal_after=Decimal('100.00'), bonus_after=Decimal('0'),
        ))
        db.session.commit()

    with as_admin():
        LegacyService.bind(LegacyMap.TARGET_MEMBER, member_id, 'M001')
        LegacyService.record_sync('pull', 'member', 'M001')
        db.session.commit()
        _run(app, 'balance')

    with app.app_context():
        assert Reconciliation.query.count() == 1

    with app.app_context():
        _clear_business_data()

        assert Member.query.count() == 0
        assert LegacyMap.query.count() == 0
        assert SyncRecord.query.count() == 0
        assert Reconciliation.query.count() == 0
