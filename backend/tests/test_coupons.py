"""优惠券测试：建模板、发券、券包、能用哪些券、用券

「用券」现在直接调 service——它要接进订单流程才有接口（下一步）。
"""

import pytest

from backend.app.errors import BusinessError
from backend.app.extensions import db
from backend.app.models import Member, UserCoupon
from backend.app.services import CouponService


def _template(client, name='满100减20', **overrides):
    payload = {'name': name, 'type': 'full_cut', 'value': '20.00', 'min_amount': '100.00'}
    payload.update(overrides)
    return client.post('/api/coupons/templates', json=payload)


def _member(client, mobile='13800000001', nickname='测试会员'):
    return client.post('/api/members',
                       json={'mobile': mobile, 'nickname': nickname}).get_json()['data']


def _issue(client, template_id, member_ids, count=1):
    return client.post('/api/coupons/issue', json={
        'template_id': template_id, 'member_ids': member_ids, 'count': count,
    })


def _wallet(client, member_id, status=None):
    params = {'status': status} if status else None
    resp = client.get(f'/api/coupons/members/{member_id}', query_string=params or {})
    return resp.get_json()['data']['coupons']


# ---------- 券模板 ----------

def test_create_template(client, admin_staff, login):
    login('admin', 'Admin123!')
    resp = _template(client)
    assert resp.status_code == 201
    data = resp.get_json()['data']
    assert data['name'] == '满100减20'
    assert data['type_label'] == '满减'
    assert data['min_amount'] == 100.0
    assert data['is_all_stores'] is True       # 没指定门店 = 全公司通用
    assert data['issued_count'] == 0


def test_discount_rate_must_be_between_0_and_1(client, admin_staff, login):
    """折扣率 1 是原价（等于没打折）、0 是白送，都不该允许"""
    login('admin', 'Admin123!')
    for bad in ('1.00', '0'):
        resp = _template(client, name=f'折扣{bad}', type='discount', value=bad)
        assert resp.status_code == 400, f'{bad} 不该被接受'
        assert '折扣率' in resp.get_json()['message']

    assert _template(client, name='八五折', type='discount', value='0.85').status_code == 201


def test_update_checks_type_and_value_together(client, admin_staff, login):
    """单改 value 时类型还是旧的那个——校验必须两个一起看

    折扣券改成 `value=1.5` 该被拦。如果只看「这次传了什么」、不带上旧类型，
    就会放过去，然后在用券的时候算出负数优惠。
    """
    login('admin', 'Admin123!')
    template = _template(client, name='八五折', type='discount',
                         value='0.85').get_json()['data']

    resp = client.put(f'/api/coupons/templates/{template["id"]}', json={'value': '1.50'})
    assert resp.status_code == 400
    assert '折扣率' in resp.get_json()['message']

    # 满减券改成什么数都行（减 0 元是「没优惠」，语义上说得通）
    full_cut = _template(client, name='任意减').get_json()['data']
    assert client.put(f'/api/coupons/templates/{full_cut["id"]}',
                      json={'value': '0'}).status_code == 200


def test_cannot_delete_template_already_issued(client, admin_staff, login):
    """发出去过的模板删不掉——不然顾客手里那张券就成了没头没尾的东西"""
    login('admin', 'Admin123!')
    template = _template(client).get_json()['data']
    member = _member(client)
    _issue(client, template['id'], [member['id']])

    resp = client.delete(f'/api/coupons/templates/{template["id"]}')
    assert resp.status_code == 400
    assert '停用' in resp.get_json()['message']

    # 没发过的就能删
    empty = _template(client, name='没人要的券').get_json()['data']
    assert client.delete(f'/api/coupons/templates/{empty["id"]}').status_code == 200


# ---------- 发券 ----------

def test_issue_coupons(client, admin_staff, login):
    login('admin', 'Admin123!')
    template = _template(client).get_json()['data']
    a, b = _member(client, '13800000001'), _member(client, '13800000002')

    resp = _issue(client, template['id'], [a['id'], b['id']], count=2)
    assert resp.status_code == 200
    assert resp.get_json()['data']['total'] == 4        # 2 人 × 2 张

    assert len(_wallet(client, a['id'])) == 2
    assert len(_wallet(client, b['id'])) == 2


def test_issue_respects_total_quantity(client, admin_staff, login):
    """总量不够就拒绝——而且要说清楚「一共多少、已发多少、这次要发多少」"""
    login('admin', 'Admin123!')
    template = _template(client, name='限量 3 张',
                         total_quantity=3).get_json()['data']
    a, b = _member(client, '13800000001'), _member(client, '13800000002')

    assert _issue(client, template['id'], [a['id']], count=2).status_code == 200

    resp = _issue(client, template['id'], [b['id']], count=2)     # 已发 2 + 要发 2 > 3
    assert resp.status_code == 400
    assert '一共 3 张' in resp.get_json()['message']

    # 刚好填满是可以的
    assert _issue(client, template['id'], [b['id']], count=1).status_code == 200


def test_disabled_template_cannot_be_issued(client, admin_staff, login):
    """停用的模板不能再发——但已经发出去的不受影响（见下一条）"""
    login('admin', 'Admin123!')
    template = _template(client, name='停用的券').get_json()['data']
    member = _member(client)

    client.put(f'/api/coupons/templates/{template["id"]}', json={'status': 'disabled'})
    resp = _issue(client, template['id'], [member['id']])
    assert resp.status_code == 400
    assert '已停用' in resp.get_json()['message']


def test_disabled_member_cannot_receive(app, client, admin_staff, login):
    login('admin', 'Admin123!')
    template = _template(client).get_json()['data']
    member = _member(client)

    with app.app_context():
        db.session.get(Member, member['id']).is_active = False
        db.session.commit()

    resp = _issue(client, template['id'], [member['id']])
    assert resp.status_code == 400
    assert '已停用' in resp.get_json()['message']


# ---------- 券包 ----------

def test_wallet_filters_by_status(client, admin_staff, login):
    login('admin', 'Admin123!')
    template = _template(client).get_json()['data']
    member = _member(client)
    _issue(client, template['id'], [member['id']], count=3)

    assert len(_wallet(client, member['id'])) == 3
    assert len(_wallet(client, member['id'], 'unused')) == 3
    assert len(_wallet(client, member['id'], 'used')) == 0


def test_expired_is_computed_not_stored(app, client, admin_staff, login):
    """过期是**算出来的**——库里的 status 还是 unused

    查「已过期」能查到、查「未使用」查不到，但数据库里的那一行从没被改过。
    这就是「不写库」的意思：不存在「该过期了但状态还是未用」的脏数据。
    """
    login('admin', 'Admin123!')
    template = _template(client, name='去年就过期了',
                         valid_to='2020-01-01T00:00:00').get_json()['data']
    member = _member(client)
    _issue(client, template['id'], [member['id']])

    assert len(_wallet(client, member['id'], 'expired')) == 1
    assert len(_wallet(client, member['id'], 'unused')) == 0

    with app.app_context():
        coupon = UserCoupon.query.first()
        assert coupon.status == UserCoupon.STATUS_UNUSED   # 库里没动过
        assert coupon.display_status == 'expired'          # 但算出来是过期


# ---------- 这单能用哪些券 ----------

def _usable(client, member_id, store_id, amount):
    resp = client.get(f'/api/coupons/members/{member_id}/usable',
                      query_string={'store_id': store_id, 'amount': str(amount)})
    return resp.get_json()['data']['coupons']


def _store(client, code='S001', name='解放路店'):
    return client.post('/api/stores', json={'code': code, 'name': name}).get_json()['data']


def test_usable_requires_all_four_conditions(client, admin_staff, login):
    """四个条件各拦一类券：用过 / 过期 / 不适用这家店 / 不够门槛"""
    login('admin', 'Admin123!')
    store = _store(client)
    other = _store(client, code='S002', name='文化路店')
    member = _member(client)

    ok = _template(client, name='能用的券').get_json()['data']
    expired = _template(client, name='过期的券',
                        valid_to='2020-01-01T00:00:00').get_json()['data']
    elsewhere = _template(client, name='只在那家店能用',
                          store_ids=[other['id']]).get_json()['data']
    too_high = _template(client, name='满 500 才能用',
                         min_amount='500.00').get_json()['data']

    ids = [t['id'] for t in (ok, expired, elsewhere, too_high)]
    _issue(client, ids[0], [member['id']])
    _issue(client, ids[1], [member['id']])
    _issue(client, ids[2], [member['id']])
    _issue(client, ids[3], [member['id']])
    assert len(_wallet(client, member['id'])) == 4

    usable = _usable(client, member['id'], store['id'], '150.00')
    assert [c['template_name'] for c in usable] == ['能用的券']
    assert usable[0]['discount'] == 20.0        # 满 100 减 20


def test_usable_sorts_by_discount(client, admin_staff, login):
    """按能抵多少倒序——收银员多半想先看最划算的那张"""
    login('admin', 'Admin123!')
    store = _store(client)
    member = _member(client)

    small = _template(client, name='减 5 块', value='5.00',
                      min_amount='0').get_json()['data']
    big = _template(client, name='减 30 块', value='30.00',
                    min_amount='0').get_json()['data']
    _issue(client, small['id'], [member['id']])
    _issue(client, big['id'], [member['id']])

    usable = _usable(client, member['id'], store['id'], '100.00')
    assert [c['template_name'] for c in usable] == ['减 30 块', '减 5 块']


def test_full_cut_never_goes_negative(client, admin_staff, login):
    """满减不能减成负数——订单 5 元、券减 20 只能减到 0

    （门槛设成 0 才凑得出这个场景；有门槛的话根本轮不到它）
    """
    login('admin', 'Admin123!')
    store = _store(client)
    member = _member(client)
    template = _template(client, name='减 20', value='20.00',
                         min_amount='0').get_json()['data']
    _issue(client, template['id'], [member['id']])

    usable = _usable(client, member['id'], store['id'], '5.00')
    assert usable[0]['discount'] == 5.0         # 不是 -15


# ---------- 用券（还没有接口，直接调 service） ----------

def test_use_coupon(as_admin, client, admin_staff, login):
    """用券：状态变成已用，记下时间和在哪家店用的"""
    from decimal import Decimal as D

    from backend.app.models import Order

    login('admin', 'Admin123!')
    store = _store(client)
    member = _member(client)
    template = _template(client, min_amount='0').get_json()['data']
    _issue(client, template['id'], [member['id']])

    with as_admin():
        coupon = UserCoupon.query.first()
        order = Order(store_id=store['id'], payable_amount=D('150.00'),
                      order_no='T-1', query_token='x')
        db.session.add(order)
        db.session.flush()

        discount = CouponService.use(coupon, order)
        db.session.commit()

        assert discount == D('20.00')
        assert coupon.status == UserCoupon.STATUS_USED
        assert coupon.used_store_id == store['id']
        assert coupon.used_order_id == order.id

    # 用过的券不能再出现在「能用的」里面
    assert _usable(client, member['id'], store['id'], '150.00') == []


def test_check_returns_reason_as_text(as_admin, client, admin_staff, login):
    """`check()` 返回原因字符串、不抛异常——「查能用的券」只是查，不该炸"""
    from decimal import Decimal as D

    login('admin', 'Admin123!')
    store = _store(client)
    member = _member(client)
    template = _template(client, valid_to='2020-01-01T00:00:00').get_json()['data']
    _issue(client, template['id'], [member['id']])

    with as_admin():
        coupon = UserCoupon.query.first()
        reason = CouponService.check(coupon, store['id'], D('150.00'))
        assert reason == '这张券已经过期了'
        # 用的时候就把它抛出来
        with pytest.raises(BusinessError, match='已经过期'):
            CouponService.use(coupon, type('O', (), {'store_id': store['id'],
                                                     'payable_amount': D('150.00'),
                                                     'id': 1})())
