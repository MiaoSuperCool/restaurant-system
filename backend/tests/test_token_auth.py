"""员工小程序的 token 认证

设计文档第 2 条说「两条通道共用同一套 service 层和权限判断，只有「怎么认出这个人」
不同」。这个文件盯的就是那句话：**同一个接口，带 cookie 能进，带 token 也能进，
判权的结果还一样**——如果哪天有人把权限判断写成了「只在 session 下有效」，
这里的测试会红。
"""


from backend.app.extensions import db
from backend.app.models import Staff


def _login(client, username='admin', password='Admin123!'):
    """走一遍小程序登录，返回整个 data（token + 权限 + 员工）"""
    resp = client.post('/api/auth/token', json={'username': username, 'password': password})
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()['data']


def _token(client, username='admin', password='Admin123!'):
    return _login(client, username, password)['token']


def _headers(token):
    return {'Authorization': f'Bearer {token}'}


# ---------- 登录换 token ----------

def test_login_returns_token_and_permissions(client, admin_staff):
    data = _login(client)
    assert data['token']
    assert data['expires_in'] == 7 * 24 * 3600
    # 权限跟着一起下发，前端才知道该显示哪些菜单
    assert data['staff']['username'] == 'admin'
    assert 'permissions' in data and 'data_scope' in data


def test_wrong_password_gets_no_token(client, admin_staff):
    # 密码长度不够会被 schema 拦成 422，测不到「密码错误」那条路，所以给个像样的错密码
    resp = client.post('/api/auth/token',
                       json={'username': 'admin', 'password': 'wrong-password'})
    assert resp.status_code == 401
    assert 'token' not in (resp.get_json().get('data') or {})


def test_token_login_does_not_create_a_session(client, admin_staff):
    """小程序那条路**不发 cookie**——发了的话浏览器那边会莫名其妙「已登录」"""
    resp = client.post('/api/auth/token',
                       json={'username': 'admin', 'password': 'Admin123!'})
    assert 'Set-Cookie' not in resp.headers or 'session=' not in resp.headers.get('Set-Cookie', '')


# ---------- 用 token 访问受保护的接口 ----------

def test_token_works_on_protected_endpoints(client, admin_staff):
    """带 token 能进受保护的接口——**而且和带 cookie 看到的东西一样**"""
    token = _token(client)

    by_token = client.get('/api/stores', headers=_headers(token))
    assert by_token.status_code == 200

    # 同一个接口，走 session 那条路，结果应该一致
    client.post('/api/auth', json={'username': 'admin', 'password': 'Admin123!'})
    by_session = client.get('/api/stores')
    assert by_session.status_code == 200
    assert by_token.get_json()['data'] == by_session.get_json()['data']


def test_permission_check_still_applies_with_token(client, make_staff):
    """**判权不能因为换了认证方式就松掉**——服务员带了 token 也进不了员工管理"""
    make_staff('fuwuyuan1', 'waiter')
    token = _token(client, 'fuwuyuan1', 'Passw0rd!')

    assert client.get('/api/order-view-probe',
                      headers=_headers(token)).status_code in (401, 403, 404)

    # 员工列表要 staff:manage，服务员没有
    resp = client.get('/api/staff', headers=_headers(token))
    assert resp.status_code == 403


def test_token_post_skips_csrf(client, app, admin_staff):
    """带 token 的写请求不用 CSRF——小程序没有 cookie，也拿不到 csrf_token

    （CSRF 靠的是浏览器自动带 cookie，token 请求没有那个前提，
    见 extensions.py 里 ApiCSRFProtect 的说明）
    """
    token = _token(client)

    # 测试环境默认关着 CSRF（省得每个测试都去搞 token），这一条要验的正是它，
    # 所以单独打开。**注意要在拿到 token 之后再开**——登录那个请求自己不带 Bearer 头
    app.config['WTF_CSRF_ENABLED'] = True

    resp = client.post('/api/stores', headers=_headers(token),
                       json={'code': 'S900', 'name': '测试店'})
    assert resp.status_code == 201, resp.get_json()

    # 而**不带 token 的写请求照旧被 CSRF 拦下**——浏览器那一边的防护没被削弱
    blocked = client.post('/api/stores', json={'code': 'S901', 'name': '没 CSRF'})
    assert blocked.status_code == 400
    assert blocked.get_json()['data']['reason'] == 'csrf'


def test_garbage_token_is_treated_as_not_logged_in(client, admin_staff):
    for bad in ('not-a-token', 'a.b.c', ''):
        resp = client.get('/api/stores', headers=_headers(bad))
        assert resp.status_code == 401, f'{bad!r} 不该被放行'


# ---------- 撤销 ----------

def test_logout_invalidates_the_token(client, admin_staff):
    """登出之后旧 token 立刻作废——无状态 token 的「撤销」就是这一下"""
    token = _token(client)
    assert client.get('/api/stores', headers=_headers(token)).status_code == 200

    assert client.post('/api/auth/logout', headers=_headers(token)).status_code == 200

    assert client.get('/api/stores', headers=_headers(token)).status_code == 401


def test_logout_kicks_other_devices_too(client, app, admin_staff):
    """登出会把这个人**所有**旧 token 一起作废

    门店的公用平板就是这个场景：上一个人登出，下一个人才拿得到干净的状态。
    """
    first = _token(client)
    second = _token(client)

    client.post('/api/auth/logout', headers=_headers(first))

    assert client.get('/api/stores', headers=_headers(first)).status_code == 401
    assert client.get('/api/stores', headers=_headers(second)).status_code == 401


def test_changing_password_invalidates_tokens(client, app, admin_staff):
    """改密码 = 把之前的凭据全都作废，不然后面改的密码等于没改"""
    token = _token(client)
    assert client.get('/api/stores', headers=_headers(token)).status_code == 200

    with app.app_context():
        staff = db.session.get(Staff, admin_staff.id)
        staff.set_password('NewPass123!')
        staff.token_version = (staff.token_version or 0) + 1
        db.session.commit()

    assert client.get('/api/stores', headers=_headers(token)).status_code == 401


def test_disabled_account_loses_access_immediately(client, app, admin_staff):
    """账号一停用，token 还没过期也进不来——**秒开秒停靠的就是每次现查**

    要是把身份全塞进 token、不查库，这里就只能等它自然过期。
    """
    token = _token(client)
    assert client.get('/api/stores', headers=_headers(token)).status_code == 200

    with app.app_context():
        staff = db.session.get(Staff, admin_staff.id)
        staff.is_active = False
        db.session.commit()

    assert client.get('/api/stores', headers=_headers(token)).status_code == 401


def test_expired_token_is_rejected(client, app, admin_staff):
    """过期就作废。**改有效期来测**——不 mock 时间也不 sleep

    itsdangerous 判过期是 `age > max_age`，两边都是整数秒，
    所以 max_age=0 在「同一秒内」仍然算没过期。要立刻过期得给负数
    （CSRF 那条测试也踩过同一个边界）
    """
    from backend.app.utils import token as token_utils

    token = _token(client)
    app.config['MP_TOKEN_MAX_AGE'] = -1

    with app.app_context():
        # 注意用的是 parse_staff_token 而不是 parse_token：
        # 后者只验签不判过期（有效期按类型定，得先解开载荷才知道是哪种），
        # 判过期在 parse_staff_token / parse_member_token 里各判各的
        assert token_utils.parse_staff_token(token) is None
    assert client.get('/api/stores', headers=_headers(token)).status_code == 401


def test_token_login_works_with_csrf_on(client, app, admin_staff):
    """**换 token 的登录接口必须豁免 CSRF**——不然小程序连门都进不来

    网页端登录能过 CSRF，是因为它先领了 csrf cookie；小程序没有 cookie 那套东西，
    这个接口不豁免的话它永远拿不到自己的第一个 token。
    （这条是拿 curl 打这个接口时发现的：带着 JSON 却没带 csrf_token，被 400 挡了。）
    """
    app.config['WTF_CSRF_ENABLED'] = True

    resp = client.post('/api/auth/token',
                       json={'username': 'admin', 'password': 'Admin123!'})
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()['data']['token']

    # 而**网页端的登录接口照旧要 CSRF**——豁免的是新开的那条通道，不是把所有登录都放开
    assert client.post('/api/auth',
                       json={'username': 'admin', 'password': 'Admin123!'}).status_code == 400
