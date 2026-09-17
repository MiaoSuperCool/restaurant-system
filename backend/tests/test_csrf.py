"""CSRF 流程测试：cookie token 与 session 校验值必须一致

**token 一律从 cookie 里取**，和前端 `request.ts` 的做法一致——
前端就是读 `document.cookie` 的，从 session 里取是"顺手"，
但它绕过了真正要测的那条链路（服务端下发的 cookie 到底能不能用）。
"""
import pytest


@pytest.fixture
def csrf_app(app):
    """本文件用启用 CSRF 的应用（TestingConfig 默认关闭）"""
    app.config['WTF_CSRF_ENABLED'] = True
    return app


def csrf_cookie(client):
    """走一个 GET 领到 cookie，返回里面的 signed token（前端就是这么拿的）"""
    client.get('/index')
    return client.get_cookie('csrf_token').value


def test_csrf_login_flow(csrf_app, client, admin_staff):
    """预热领取 cookie → 带 X-CSRFToken 头登录成功"""
    token = csrf_cookie(client)
    assert token, '每个响应都该把 signed token 写进 cookie'

    with client.session_transaction() as sess:
        assert sess.get('csrf_token'), 'raw token 存在 session 里（校验时拿它比）'

    resp = client.post('/api/auth',
                       json={'username': 'admin', 'password': 'Admin123!'},
                       headers={'X-CSRFToken': token})
    assert resp.status_code == 200


def test_every_issued_token_keeps_working(csrf_app, client, admin_staff):
    """连着拿到的 token，**每个都能用**——不管服务端中间又签了几个

    这条替掉了原来那条「多次请求后 token 保持稳定」的测试。那条测的是实现
    （session 里缓存了一个值），不是需求——真正的需求是
    「并发/连续请求不会因为 token 换过而失败」。

    它成立的原因：校验比的是解出来的 **raw token**（存在 session 里，不变），
    不是签名字符串。所以服务端每次重签都不影响任何在用的 token，
    当初「缓存 signed 防并发」那个担心根本不存在。

    注意**别去断言「两次拿到的串一定不一样」**：itsdangerous 的时间戳是整数秒，
    同一秒内签出来的是同一个串（这行断言一开始就是这么写错的）。
    要验「每次都是新签的」得用时间说话，见下面那条。
    """
    first = csrf_cookie(client)
    second = csrf_cookie(client)

    for token in (first, second):
        resp = client.post('/api/auth',
                           json={'username': 'admin', 'password': 'Admin123!'},
                           headers={'X-CSRFToken': token})
        assert resp.status_code == 200, f'{token[:16]}… 应该能用'


def test_csrf_wrong_token_rejected(csrf_app, client, admin_staff):
    """错误的 token 会被拒绝（400）"""
    csrf_cookie(client)
    resp = client.post('/api/auth',
                       json={'username': 'admin', 'password': 'Admin123!'},
                       headers={'X-CSRFToken': 'wrong-token'})
    assert resp.status_code == 400


def test_csrf_failure_carries_message(csrf_app, client, admin_staff):
    """CSRF 失败必须带可读的 message，不能是那个没头没脑的裸 400

    这曾经是个真问题：CSRFError 是 BadRequest(400) 的子类，没人接就落到
    flask-smorest 的默认处理，吐出 {"code":400,"status":"Bad Request"}——
    前端拦截器只认 {success, message}，用户就只看到「请求失败（400）」，
    完全不知道发生了什么。

    data.reason 是给前端拦截器用的机器可读标记：它靠这个认出「是 token 失效、
    不是业务失败」，自动换一个新 token 重试一次，用户不用手动清 cookie。
    """
    csrf_cookie(client)
    resp = client.post('/api/auth',
                       json={'username': 'admin', 'password': 'Admin123!'},
                       headers={'X-CSRFToken': 'wrong-token'})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body['success'] is False
    assert body['message'], '必须有可读的提示，不能是空字符串'
    assert body['data'] == {'reason': 'csrf'}, '前端靠这个标记决定要不要换 token 重试'


def test_csrf_token_follows_the_session_not_its_own_timer(csrf_app, client, admin_staff):
    """signed token 里那个时间戳确实会过期；但本项目不靠它，靠 session

    时间戳是 Flask-WTF 拿来判「1 小时有效期」的。以前 `set_csrf_cookie` 把 signed
    缓存在 session 里重复发，等于把时间戳冻住——一小时之后服务端**还在把那个过期的
    往外发**，于是所有写请求 400（刷新、重登都没用，只能清 cookie）。当时是用
    `WTF_CSRF_TIME_LIMIT = None` 绕开的，病根在那个缓存上，现在缓存已经去掉了：
    **每个响应都重签，时间戳永远是新的**，所以这个限制基本轮不到触发。

    配 None 是为了另一种情况：**页面长时间挂着没发过请求**（收银台一开 8 小时），
    cookie 里那个 signed 早就超过 1 小时了。默认配置下这时候会 400，
    前端虽然会自动换一个重试，但没必要让这件事发生。
    """
    import time

    # ① 把有效期压到 1 秒：手里这个旧的，放一会儿就真的废了——时间戳是干这个的
    csrf_app.config['WTF_CSRF_TIME_LIMIT'] = 1
    stale = csrf_cookie(client)

    # 睡 3 秒而不是 1.2：itsdangerous 的时间戳是整数秒，判断是 `age > max_age`，
    # 只差 1 秒的话 1 > 1 不成立，token 还不算过期
    time.sleep(3)
    assert client.post('/api/auth',
                       json={'username': 'admin', 'password': 'Admin123!'},
                       headers={'X-CSRFToken': stale}).status_code == 400

    # ② **再领一个就能用**——这一条才是「重签」的证据：
    #    如果还像以前那样缓存 signed，这里拿到的仍然是那个已经过期的，照样 400
    fresh = csrf_cookie(client)
    assert client.post('/api/auth',
                       json={'username': 'admin', 'password': 'Admin123!'},
                       headers={'X-CSRFToken': fresh}).status_code == 200

    # ③ 配 None（本项目）：重新领一个，放多久都还能用——生命周期跟着 session
    csrf_app.config['WTF_CSRF_TIME_LIMIT'] = None
    token = csrf_cookie(client)
    time.sleep(3)
    assert client.post('/api/auth',
                       json={'username': 'admin', 'password': 'Admin123!'},
                       headers={'X-CSRFToken': token}).status_code == 200


def test_bad_request_also_uses_envelope(csrf_app, client, admin_staff):
    """兜底：其他 400 也要走统一信封，别漏出裸格式"""
    token = csrf_cookie(client)

    resp = client.post('/api/auth', data='{不是合法 json',
                       content_type='application/json',
                       headers={'X-CSRFToken': token})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body is not None and 'success' in body, f'应该是统一信封，实际拿到: {body}'
