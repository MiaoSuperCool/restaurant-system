"""顾客端登录 + 个人中心 + 券中心

这里盯的是三件事：

1. **登录即注册**——手机号是新的顺手建档，不单独做注册页
2. **两套 token 不能串台**——员工的和顾客的载荷里都带 `typ`，
   员工 token 调顾客接口必须 401（两张表的 id 都是自增的，不判类型会认错人）
3. **券只能领自己的**——顾客端没有任何一个接口的 URL 里带 member_id，全靠 token 认人
"""
from datetime import datetime, timedelta, timezone

from backend.app.extensions import db
from backend.app.models import Member, MemberVerifyCode, UserCoupon


def _ctx(client):
    """要直接读库时用——测试客户端自己带着应用，不用到处传 app fixture"""
    return client.application.app_context()


def _code(client, mobile='13900000001'):
    """要一个新验证码，返回那个码（演示环境回显在 data.code 里）

    **先把上一条删掉**：同一个手机号 60 秒内只能要一次（这是功能，不是障碍），
    测试里等不起，删掉旧的等价于「已经过了一分钟」。
    """
    with _ctx(client):
        MemberVerifyCode.query.filter_by(mobile=mobile).delete()
        db.session.commit()

    resp = client.post('/api/public/auth/code', json={'mobile': mobile})
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()['data']['code']


def _login(client, mobile='13900000001', code=None):
    payload = {'mobile': mobile,
               'code': code if code is not None else _code(client, mobile)}
    return client.post('/api/public/auth/token', json=payload)


def _member_token(client, mobile='13900000001'):
    """登录一次，返回 `(token, 整个 data)`"""
    resp = _login(client, mobile)
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()['data']
    return data['token'], data


def _auth(token):
    return {'Authorization': f'Bearer {token}'}


# ---------- 发验证码 ----------

def test_code_is_echoed_in_demo_and_rate_limited(client):
    """演示环境回显验证码；同一个号 60 秒内不能再要"""
    data = client.post('/api/public/auth/code',
                       json={'mobile': '13900000001'}).get_json()['data']
    assert len(data['code']) == 6 and data['code'].isdigit()
    assert data['expires_in'] == MemberVerifyCode.TTL_SECONDS

    again = client.post('/api/public/auth/code', json={'mobile': '13900000001'})
    assert again.status_code == 400
    assert '秒后再试' in again.get_json()['message']


def test_code_echo_can_be_turned_off(client):
    """关掉回显之后验证码不出现在返回体里

    **回显在生产环境等于验证码形同虚设**——谁填一下别人的手机号就能拿到码登进去。
    演示时开着，所以这里专门验一下那个开关真的有效。
    """
    client.application.config['MEMBER_CODE_ECHO'] = False
    data = client.post('/api/public/auth/code',
                       json={'mobile': '13900000001'}).get_json()['data']
    assert 'code' not in data


def test_bad_mobile_rejected(client):
    # 长度由 schema 卡（422），这里测的是「长度对但内容不合法」——服务层拦的那道
    for bad in ('23900000001', 'abcdefghijk'):
        resp = client.post('/api/public/auth/code', json={'mobile': bad})
        assert resp.status_code == 400
        assert '格式' in resp.get_json()['message']


# ---------- 登录即注册 ----------

def test_first_login_registers(client):
    token, data = _member_token(client)
    assert data['is_new'] is True
    assert data['member']['mobile'] == '13900000001'
    assert token

    with _ctx(client):
        assert Member.query.filter_by(mobile='13900000001').count() == 1


def test_second_login_reuses_the_same_member(client):
    """第二次登录不该又建一个人——**同一个手机号就是同一个会员**"""
    first = _member_token(client)[1]
    second = _member_token(client)[1]

    assert second['is_new'] is False
    assert second['member']['id'] == first['member']['id']

    with _ctx(client):
        assert Member.query.count() == 1


def test_wrong_code_limits_attempts(client):
    """验证码错太多次就作废——不限制的话可以拿一个码暴力试六位数字"""
    code = _code(client)

    for i in range(MemberVerifyCode.MAX_ATTEMPTS):
        resp = _login(client, code='000000' if code != '000000' else '111111')
        assert resp.status_code == 400
        # 前几次要说清楚还剩几次，最后一次说「重新获取」
        if i < MemberVerifyCode.MAX_ATTEMPTS - 1:
            assert '还能试' in resp.get_json()['message']

    # 就算这时候拿对了码也不行了
    assert _login(client, code=code).status_code == 400


def test_code_is_single_use(client):
    """用过的码不能再用——不然一个码能反复换 token"""
    code = _code(client)
    assert _login(client, code=code).status_code == 200
    assert _login(client, code=code).status_code == 400


def test_expired_code_rejected(client):
    code = _code(client)
    with _ctx(client):
        record = MemberVerifyCode.query.order_by(MemberVerifyCode.id.desc()).first()
        # 用 UTC 而不是本地时间：库里存的是 naive UTC，
        # 拿本地时间减 1 秒在这边还是个未来时刻，过期根本不会触发
        record.expires_at = (datetime.now(timezone.utc).replace(tzinfo=None)
                             - timedelta(seconds=1))
        db.session.commit()

    resp = _login(client, code=code)
    assert resp.status_code == 400
    assert '过期' in resp.get_json()['message']


def test_disabled_member_cannot_login(client):
    _member_token(client)
    with _ctx(client):
        member = Member.query.filter_by(mobile='13900000001').first()
        member.is_active = False
        db.session.commit()

    resp = _login(client)
    assert resp.status_code == 400
    assert '停用' in resp.get_json()['message']


# ---------- 两套 token 不能串台 ----------

def test_member_token_works_on_member_endpoints(client):
    token, _ = _member_token(client)
    resp = client.get('/api/public/me', headers=_auth(token))
    assert resp.status_code == 200
    data = resp.get_json()['data']
    assert data['mobile'] == '13900000001'
    assert data['balance']['total'] == 0        # 没充过值，给的是 0 而不是 null
    assert 'points' in data


def test_member_token_is_rejected_by_staff_endpoints(client):
    """**顾客的 token 不能调员工接口**

    这是分 `typ` 的理由：两张表的 id 都是自增的，不判类型的话
    `request_loader` 会拿着一个 member_id 去 staff 表里查，
    **可能真的查到一个无关的人**。
    """
    token, _ = _member_token(client)
    assert client.get('/api/stores', headers=_auth(token)).status_code == 401
    assert client.get('/api/orders', headers=_auth(token)).status_code == 401


def test_staff_token_is_rejected_by_member_endpoints(client, admin_staff):
    """反过来也一样：员工的 token 调顾客接口是 401"""
    staff_token = client.post('/api/auth/token',
                              json={'username': 'admin', 'password': 'Admin123!'}
                              ).get_json()['data']['token']
    assert client.get('/api/public/me', headers=_auth(staff_token)).status_code == 401


def test_member_endpoints_need_a_token(client):
    for path in ('/api/public/me', '/api/public/me/coupons'):
        assert client.get(path).status_code == 401


def test_coupon_center_is_public(client, admin_staff):
    """**券中心不登录也能看**——它是首页那个「近期活动」区的数据源

    顾客端不强制登录，一进首页就是登录墙太难看。不登录时
    `claimed_count` 按 0 算、`logged_in` 是 false；点「领取」才要求登录。
    """
    _template(client, '公开的券')

    resp = client.get('/api/public/coupons')
    assert resp.status_code == 200
    data = resp.get_json()['data']
    assert data['logged_in'] is False
    assert [c['name'] for c in data['coupons']] == ['公开的券']
    assert data['coupons'][0]['claimed_count'] == 0

    # 登录之后同一个接口多带个人信息
    token, _ = _member_token(client)
    logged = client.get('/api/public/coupons', headers=_auth(token)).get_json()['data']
    assert logged['logged_in'] is True


def test_claim_still_needs_login(client, admin_staff):
    """看得到不等于领得到——**领的时候必须登录**，不然券挂不到人头上"""
    template = _template(client, '要登录才能领')
    resp = client.post(f'/api/public/coupons/{template["id"]}/claim')
    assert resp.status_code == 401


def test_disabled_member_loses_access_immediately(client):
    """停用之后 token 还没过期也进不来——**每次请求现查**"""
    token, _ = _member_token(client)
    assert client.get('/api/public/me', headers=_auth(token)).status_code == 200

    with _ctx(client):
        member = Member.query.filter_by(mobile='13900000001').first()
        member.is_active = False
        db.session.commit()

    assert client.get('/api/public/me', headers=_auth(token)).status_code == 401


# ---------- 券中心 ----------

def _template(client, name='新人券', **overrides):
    """用员工账号建一张券模板（券还是运营建的，顾客只负责领）"""
    assert client.post('/api/auth',
                       json={'username': 'admin', 'password': 'Admin123!'}
                       ).status_code == 200
    payload = {'name': name, 'type': 'full_cut', 'value': '10.00',
               'min_amount': '0', 'is_claimable': True}
    payload.update(overrides)
    resp = client.post('/api/coupons/templates', json=payload)
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()['data']


def test_coupon_center_lists_claimable(client, admin_staff):
    _template(client, '能领的券')
    _template(client, '不公开的券', is_claimable=False)

    token, _ = _member_token(client)
    coupons = client.get('/api/public/coupons',
                         headers=_auth(token)).get_json()['data']['coupons']
    assert [c['name'] for c in coupons] == ['能领的券']
    assert coupons[0]['can_claim'] is True
    assert coupons[0]['claimed_count'] == 0


def test_claim_then_see_it_in_my_wallet(client, admin_staff):
    template = _template(client)
    token, _ = _member_token(client)

    resp = client.post(f'/api/public/coupons/{template["id"]}/claim', headers=_auth(token))
    assert resp.status_code == 201, resp.get_json()

    wallet = client.get('/api/public/me/coupons',
                        headers=_auth(token)).get_json()['data']['coupons']
    assert [c['template_name'] for c in wallet] == ['新人券']

    with _ctx(client):
        # **自领的券 issued_by_name 是空的**——那个字段的语义就是「谁发的」，
        # 空 = 顾客自己领的，不需要再加一个标记字段
        assert UserCoupon.query.first().issued_by_name == ''


def test_per_member_limit(client, admin_staff):
    """每人限领 2 张；**领不到时要说清楚为什么**"""
    template = _template(client, '限领两张', per_member_limit=2)
    token, _ = _member_token(client)
    url = f'/api/public/coupons/{template["id"]}/claim'

    assert client.post(url, headers=_auth(token)).status_code == 201
    assert client.post(url, headers=_auth(token)).status_code == 201

    third = client.post(url, headers=_auth(token))
    assert third.status_code == 400
    assert '每人限领 2 张' in third.get_json()['message']

    # 券中心里也要看得出「为什么领不了」，而不是干脆不显示
    listed = client.get('/api/public/coupons',
                        headers=_auth(token)).get_json()['data']['coupons']
    assert listed[0]['can_claim'] is False
    assert listed[0]['claimed_count'] == 2


def test_member_limit_is_per_person(client, admin_staff):
    """限领是**按人**算的——另一个人照样能领"""
    template = _template(client, '限领一张', per_member_limit=1)
    url = f'/api/public/coupons/{template["id"]}/claim'

    a_token, _ = _member_token(client, '13900000001')
    b_token, _ = _member_token(client, '13900000002')
    assert client.post(url, headers=_auth(a_token)).status_code == 201
    assert client.post(url, headers=_auth(b_token)).status_code == 201


def test_claim_respects_total_quantity(client, admin_staff):
    """领完了就领不到了——**总量约束对自领同样有效**"""
    template = _template(client, '限量一张', total_quantity=1)
    url = f'/api/public/coupons/{template["id"]}/claim'

    a_token, _ = _member_token(client, '13900000001')
    b_token, _ = _member_token(client, '13900000002')

    assert client.post(url, headers=_auth(a_token)).status_code == 201
    resp = client.post(url, headers=_auth(b_token))
    assert resp.status_code == 400
    assert '领完' in resp.get_json()['message']


def test_cannot_claim_expired_template(client, admin_staff):
    template = _template(client, '过期的券', valid_to='2020-01-01T00:00:00')
    token, _ = _member_token(client)

    resp = client.post(f'/api/public/coupons/{template["id"]}/claim', headers=_auth(token))
    assert resp.status_code == 400
    assert '过期' in resp.get_json()['message']


def test_cannot_claim_a_template_that_is_not_claimable(client, admin_staff):
    template = _template(client, '不公开的券', is_claimable=False)
    token, _ = _member_token(client)

    resp = client.post(f'/api/public/coupons/{template["id"]}/claim', headers=_auth(token))
    assert resp.status_code == 400
    assert '不能自己领' in resp.get_json()['message']


def test_wallet_only_returns_my_own_coupons(client, admin_staff):
    """券包只给本人的——**顾客端没有哪个接口的 URL 里带 member_id**

    带的话改一个数字就能看别人的券包。这条就是盯这件事：
    两个人各领一张，互相看不到对方的。
    """
    template = _template(client)
    url = f'/api/public/coupons/{template["id"]}/claim'

    a_token, a = _member_token(client, '13900000001')
    b_token, b = _member_token(client, '13900000002')
    client.post(url, headers=_auth(a_token))

    a_wallet = client.get('/api/public/me/coupons', headers=_auth(a_token)).get_json()['data']
    b_wallet = client.get('/api/public/me/coupons', headers=_auth(b_token)).get_json()['data']

    assert a_wallet['pagination']['total'] == 1
    assert b_wallet['pagination']['total'] == 0
    assert a_wallet['coupons'][0]['member_id'] == a['member']['id']
    assert a['member']['id'] != b['member']['id']


# ---------- 登录之后下单 ----------

def _a_dish(client):
    """建一道没规格的菜（点单不用过规格选择），返回门店和菜品"""
    assert client.post('/api/auth',
                       json={'username': 'admin', 'password': 'Admin123!'}
                       ).status_code == 200
    store = client.post('/api/stores',
                        json={'code': 'S001', 'name': '解放路店'}).get_json()['data']
    category = client.post('/api/categories', json={'name': '小食'}).get_json()['data']
    dish = client.post('/api/dishes', json={
        'category_id': category['id'], 'name': '凉拌黄瓜', 'base_price': '12.00',
    }).get_json()['data']
    return store, dish


def _public_order(client, store_id, dish_id, token=None):
    return client.post('/api/public/orders',
                       json={'store_id': store_id, 'source': 'dine_in',
                             'items': [{'dish_id': dish_id, 'quantity': 2, 'option_ids': []}]},
                       headers=_auth(token) if token else {})


def test_order_attaches_member_when_logged_in(client, app, admin_staff):
    """**登录了下单就挂上会员**——不挂的话这一单和这个人没关系

    没登录照样能下单（这一端不强制登录），区别就在 member_id 空不空。
    """
    store, dish = _a_dish(client)
    token, login = _member_token(client)

    # 没登录下的单：散客单
    guest = _public_order(client, store['id'], dish['id']).get_json()['data']
    assert guest['member_id'] is None

    # 登录之后下的单：挂在这个人名下
    mine = _public_order(client, store['id'], dish['id'], token).get_json()['data']
    assert mine['member_id'] == login['member']['id']


def test_paying_earns_points(client, app, admin_staff):
    """**付了钱就返积分**——顾客端和员工端两条收款路径共用同一条规则

    这条以前是漏的：`PublicService.pay` 自己建 Payment，没走
    `OrderService.add_payment` 里那段返积分的逻辑。结果是顾客登录着买了东西，
    单子明明挂在他名下，积分一分不涨。
    """
    store, dish = _a_dish(client)
    token, login = _member_token(client)
    order = _public_order(client, store['id'], dish['id'], token).get_json()['data']

    assert client.post(f'/api/public/orders/{order["order_no"]}/pay'
                       f'?token={order["query_token"]}',
                       json={'method': 'wechat'}, headers=_auth(token)).status_code == 200

    account = client.get('/api/public/me', headers=_auth(token)).get_json()['data']
    # ¥12 × 2 = ¥24，消费 1 元返 1 分
    assert account['points']['balance'] == 24


def test_guest_order_earns_no_points(client, app, admin_staff):
    """散客单不返分——返给谁？"""
    store, dish = _a_dish(client)
    order = _public_order(client, store['id'], dish['id']).get_json()['data']

    assert client.post(f'/api/public/orders/{order["order_no"]}/pay'
                       f'?token={order["query_token"]}',
                       json={'method': 'wechat'}).status_code == 200

    with _ctx(client):
        from backend.app.models import PointsTxn
        assert PointsTxn.query.count() == 0


def test_customer_cannot_pay_by_balance(client, app, admin_staff):
    """**顾客端只认微信支付**——传储值会被明确拒掉

    以前这里来者不拒：传 `balance` 既不扣余额也不报错，钱没从任何地方出，
    单子却显示付了。**静默不扣钱比报错糟得多。**
    """
    store, dish = _a_dish(client)
    token, _ = _member_token(client)
    order = _public_order(client, store['id'], dish['id'], token).get_json()['data']

    resp = client.post(f'/api/public/orders/{order["order_no"]}/pay'
                       f'?token={order["query_token"]}',
                       json={'method': 'balance'}, headers=_auth(token))
    assert resp.status_code == 400
    assert '只支持微信支付' in resp.get_json()['message']
