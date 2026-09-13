"""CSRF 流程测试：cookie token 与 session 校验值必须一致"""
import pytest


@pytest.fixture
def csrf_app(app):
    """本文件用启用 CSRF 的应用（TestingConfig 默认关闭）"""
    app.config['WTF_CSRF_ENABLED'] = True
    return app


def test_csrf_login_flow(csrf_app, client, admin_staff):
    """预热领取 cookie → 带 X-CSRFToken 头登录成功"""
    # 第一次 GET：after_request 生成 signed token 写入 session 缓存和 cookie
    client.get('/index')

    # 从 session 取 signed token（模拟前端从 cookie 读到的值）
    with client.session_transaction() as sess:
        token = sess.get('csrf_token_signed')
        raw_token = sess.get('csrf_token')
    assert token, 'session 里应该有 signed token'
    assert raw_token, 'session 里应该有 raw token（Flask-WTF 校验用）'

    # 登录响应里的 cookie 与 session 的 signed token 一致
    resp = client.post('/api/auth',
                       json={'username': 'admin', 'password': 'Admin123!'},
                       headers={'X-CSRFToken': token})
    assert resp.status_code == 200
    set_cookie = resp.headers.get('Set-Cookie', '')
    assert f'csrf_token={token}' in set_cookie, 'cookie 与 session 的 signed token 必须一致'


def test_csrf_token_stable_across_requests(csrf_app, client, admin_staff):
    """多次请求后 token 保持稳定（并发请求不会因 token 更换而校验失败）"""
    client.get('/index')
    with client.session_transaction() as sess:
        first = sess.get('csrf_token_signed')

    client.get('/index')
    with client.session_transaction() as sess:
        second = sess.get('csrf_token_signed')

    assert first == second


def test_csrf_wrong_token_rejected(csrf_app, client, admin_staff):
    """错误的 token 会被拒绝（400）"""
    client.get('/index')
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
    client.get('/index')
    resp = client.post('/api/auth',
                       json={'username': 'admin', 'password': 'Admin123!'},
                       headers={'X-CSRFToken': 'wrong-token'})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body['success'] is False
    assert body['message'], '必须有可读的提示，不能是空字符串'
    assert body['data'] == {'reason': 'csrf'}, '前端靠这个标记决定要不要换 token 重试'


def test_bad_request_also_uses_envelope(csrf_app, client, admin_staff):
    """兜底：其他 400 也要走统一信封，别漏出裸格式"""
    client.get('/index')
    with client.session_transaction() as sess:
        token = sess.get('csrf_token_signed')

    resp = client.post('/api/auth', data='{不是合法 json',
                       content_type='application/json',
                       headers={'X-CSRFToken': token})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body is not None and 'success' in body, f'应该是统一信封，实际拿到: {body}'
