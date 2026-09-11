"""CSRF 流程测试：cookie token 与 session 校验值必须一致"""
import pytest


@pytest.fixture
def csrf_app(app):
    """本文件用启用 CSRF 的应用（TestingConfig 默认关闭）"""
    app.config['WTF_CSRF_ENABLED'] = True
    return app


def test_csrf_login_flow(csrf_app, client, admin_user):
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


def test_csrf_token_stable_across_requests(csrf_app, client, admin_user):
    """多次请求后 token 保持稳定（并发请求不会因 token 更换而校验失败）"""
    client.get('/index')
    with client.session_transaction() as sess:
        first = sess.get('csrf_token_signed')

    client.get('/index')
    with client.session_transaction() as sess:
        second = sess.get('csrf_token_signed')

    assert first == second


def test_csrf_wrong_token_rejected(csrf_app, client, admin_user):
    """错误的 token 会被拒绝（400）"""
    client.get('/index')
    resp = client.post('/api/auth',
                       json={'username': 'admin', 'password': 'Admin123!'},
                       headers={'X-CSRFToken': 'wrong-token'})
    assert resp.status_code == 400
