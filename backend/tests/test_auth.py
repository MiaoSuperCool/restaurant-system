"""认证接口测试：登录 / 登出 / 参数校验"""
from backend.app.models import User


def test_login_success(client, admin_user, login):
    resp = login('admin', 'Admin123!')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['success'] is True
    assert body['data']['user']['username'] == 'admin'
    assert body['data']['user']['is_admin'] is True


def test_login_wrong_password(client, admin_user, login):
    resp = login('admin', 'WrongPass1!')
    assert resp.status_code == 401
    assert resp.get_json()['success'] is False


def test_login_unknown_user(client, login):
    resp = login('nobody', 'Whatever1!')
    assert resp.status_code == 404
    assert resp.get_json()['success'] is False


def test_login_disabled_user(app, client, normal_user, login):
    from backend.app.extensions import db
    with app.app_context():
        user = db.session.get(User, normal_user.id)
        user.is_active = False
        db.session.commit()

    resp = login('staff', 'Staff123!')
    assert resp.status_code == 400
    assert resp.get_json()['success'] is False


def test_login_missing_fields(client):
    """缺少字段走 schema 校验 → 422"""
    resp = client.post('/api/auth', json={})
    assert resp.status_code == 422


def test_logout(client, admin_user, login):
    login('admin', 'Admin123!')
    resp = client.post('/api/auth/logout')
    assert resp.status_code == 200
    assert resp.get_json()['success'] is True

    # 登出后访问受保护接口 → 401
    resp2 = client.get('/api/users')
    assert resp2.status_code == 401


def test_login_records_audit(client, admin_user, login):
    """登录成功会记一条 Login 审计"""
    login('admin', 'Admin123!')
    resp = client.get('/api/audit')
    assert resp.status_code == 200
    logs = resp.get_json()['data']['logs']
    assert any(log['action'] == 'Login' for log in logs)
