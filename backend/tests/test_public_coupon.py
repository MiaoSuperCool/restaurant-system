"""顾客端下单用券

把「券中心领的券」和「点单结算」接起来的那一段。盯四件事：

1. 用券之后**金额真的变了**（应付少了、券变成已用）
2. **别人的券不能用**，而且失败时**订单不会留下**（整单回滚）
3. 没登录的人手里没有券，传了 id 要报错——**不能静默忽略**，
   不然顾客以为抵扣了、其实按原价付了
4. 加券**没有把「不登录也能下单」这条堵上**（那是顾客端一期的前提）

这一整套的前提都在 service 里（归属校验、门槛、适用门店），
这里从接口打进去，验的是「接线接对了没有」。
"""
from backend.app.extensions import db
from backend.app.models import Order, UserCoupon


def _ctx(client):
    return client.application.app_context()


def _store(client, code='S001', name='解放路店'):
    return client.post('/api/stores', json={'code': code, 'name': name}).get_json()['data']


def _dish(client, name='红烧牛肉面', price='120.00'):
    import time
    category = client.post('/api/categories',
                           json={'name': f'面食{time.time_ns()}'}).get_json()['data']
    return client.post('/api/dishes', json={
        'category_id': category['id'], 'name': name, 'base_price': price,
    }).get_json()['data']


def _member(client, mobile='13800000001'):
    return client.post('/api/members',
                       json={'mobile': mobile, 'nickname': '测试会员'}).get_json()['data']


def _issue(client, template_id, member_ids):
    return client.post('/api/coupons/issue', json={
        'template_id': template_id, 'member_ids': member_ids, 'count': 1,
    }).get_json()['data']


def _template(client, **overrides):
    payload = {'name': '满100减20', 'type': 'full_cut',
               'value': '20.00', 'min_amount': '100.00'}
    payload.update(overrides)
    return client.post('/api/coupons/templates', json=payload).get_json()['data']


def _coupon_id(client, member_id):
    coupons = client.get(f'/api/coupons/members/{member_id}').get_json()['data']['coupons']
    return coupons[0]['id']


def _login(client, mobile='13800000001'):
    """顾客登录：要验证码 → 换 token（演示环境验证码回显在返回里）"""
    code = client.post('/api/public/auth/code',
                       json={'mobile': mobile}).get_json()['data']['code']
    resp = client.post('/api/public/auth/token', json={'mobile': mobile, 'code': code})
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()['data']['token']


def _auth(token):
    return {'Authorization': f'Bearer {token}'}


def _order(client, store_id, dish_id, *, token=None, coupon_id=None, quantity=1):
    payload = {
        'store_id': store_id, 'source': 'dine_in',
        'items': [{'dish_id': dish_id, 'quantity': quantity, 'option_ids': []}],
    }
    if coupon_id is not None:
        payload['user_coupon_id'] = coupon_id
    return client.post('/api/public/orders', json=payload,
                       headers=_auth(token) if token else {})


# ---------- 用券下单 ----------

def test_coupon_is_applied_and_marked_used(app, client, admin_staff, login):
    """用券下单：应付少 20、券变成已用、能反查到是哪一单用的"""
    login('admin', 'Admin123!')
    store, dish = _store(client), _dish(client)
    member = _member(client)
    _issue(client, _template(client)['id'], [member['id']])
    coupon_id = _coupon_id(client, member['id'])

    resp = _order(client, store['id'], dish['id'],
                  token=_login(client), coupon_id=coupon_id)

    assert resp.status_code == 201, resp.get_json()
    order = resp.get_json()['data']
    assert float(order['total_amount']) == 120.0
    assert float(order['discount_amount']) == 20.0
    assert float(order['payable_amount']) == 100.0

    with _ctx(client):
        coupon = db.session.get(UserCoupon, coupon_id)
        assert coupon.status == UserCoupon.STATUS_USED
        assert coupon.used_order_id == order['id']


def test_without_coupon_still_works_for_guests(app, client, admin_staff, login):
    """不登录也能下单——加了券不能把这条堵上（顾客端一期的前提）"""
    login('admin', 'Admin123!')
    store, dish = _store(client), _dish(client)

    resp = _order(client, store['id'], dish['id'])

    assert resp.status_code == 201, resp.get_json()
    assert float(resp.get_json()['data']['payable_amount']) == 120.0


# ---------- 不该用上的情况 ----------

def test_cannot_use_someone_elses_coupon(app, client, admin_staff, login):
    """别人的券不能用——不拦的话，报个手机号就能把别人的券花掉

    **而且整单回滚**：这是「下单」和「用券」在同一个事务里的意义，
    不能让顾客拿到一张没抵扣的订单。
    """
    login('admin', 'Admin123!')
    store, dish = _store(client), _dish(client)
    owner = _member(client, mobile='13800000001')
    _member(client, mobile='13800000002')
    _issue(client, _template(client)['id'], [owner['id']])
    coupon_id = _coupon_id(client, owner['id'])

    # 用另一个手机号登录，却拿别人的券 id
    resp = _order(client, store['id'], dish['id'],
                  token=_login(client, mobile='13800000002'), coupon_id=coupon_id)

    assert resp.status_code == 400
    assert '不属于' in resp.get_json()['message']
    with _ctx(client):
        assert Order.query.count() == 0          # 订单没留下
        assert db.session.get(UserCoupon, coupon_id).status == UserCoupon.STATUS_UNUSED


def test_coupon_without_login_is_rejected(app, client, admin_staff, login):
    """没登录却传了券 id → 报错，不能当没看见

    静默忽略的话，顾客以为抵扣了、按原价付了，还找不出问题在哪。
    """
    login('admin', 'Admin123!')
    store, dish = _store(client), _dish(client)
    member = _member(client)
    _issue(client, _template(client)['id'], [member['id']])
    coupon_id = _coupon_id(client, member['id'])

    resp = _order(client, store['id'], dish['id'], coupon_id=coupon_id)

    assert resp.status_code == 400
    assert '会员' in resp.get_json()['message']
    with _ctx(client):
        assert Order.query.count() == 0


def test_used_coupon_cannot_be_used_again(app, client, admin_staff, login):
    """同一张券用第二次会被拒（`CouponService.use` 里那套检查）"""
    login('admin', 'Admin123!')
    store, dish = _store(client), _dish(client)
    member = _member(client)
    _issue(client, _template(client)['id'], [member['id']])
    coupon_id = _coupon_id(client, member['id'])
    token = _login(client)

    assert _order(client, store['id'], dish['id'],
                  token=token, coupon_id=coupon_id).status_code == 201
    second = _order(client, store['id'], dish['id'], token=token, coupon_id=coupon_id)

    assert second.status_code == 400
    with _ctx(client):
        assert Order.query.count() == 1          # 第二单没建出来


# ---------- 「这单能用哪些券」 ----------

def test_usable_endpoint_filters_by_store_and_amount(app, client, admin_staff, login):
    """可用券接口：门槛不到的、不适用这家店的，都不该出现"""
    login('admin', 'Admin123!')
    store = _store(client)
    other = _store(client, code='S002', name='武林门店')
    member = _member(client)
    # 一张满 100 减 20（能用）、一张满 500 减 50（金额不够）、
    # 一张只在这家店能用的
    _issue(client, _template(client, name='满100减20')['id'], [member['id']])
    _issue(client, _template(client, name='满500减50',
                             value='50.00', min_amount='500.00')['id'], [member['id']])
    _issue(client, _template(client, name='别家专用', store_ids=[other['id']])['id'],
           [member['id']])

    resp = client.get('/api/public/me/coupons/usable',
                      query_string={'store_id': store['id'], 'amount': '120.00'},
                      headers=_auth(_login(client)))

    data = resp.get_json()['data']['coupons']
    assert [c['template_name'] for c in data] == ['满100减20']
    assert float(data[0]['discount']) == 20.0


def test_usable_endpoint_needs_login(client):
    """没登录就是 401——顾客端没有「看别人有什么券」这种入口"""
    assert client.get('/api/public/me/coupons/usable',
                      query_string={'store_id': 1, 'amount': '100.00'}).status_code == 401
