"""审计日志接口测试：权限与详情"""


def test_admin_can_list_audit(client, admin_staff, login):
    login('admin', 'Admin123!')
    resp = client.get('/api/audit')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['success'] is True
    assert 'logs' in body['data']
    assert 'pagination' in body['data']


def test_non_admin_forbidden(client, normal_staff, login):
    login('staff', 'Staff123!')
    resp = client.get('/api/audit')
    assert resp.status_code == 403


def test_audit_detail_not_found(client, admin_staff, login):
    login('admin', 'Admin123!')
    resp = client.get('/api/audit/99999')
    assert resp.status_code == 404
    assert resp.get_json()['success'] is False


def test_audit_search(client, admin_staff, login):
    login('admin', 'Admin123!')
    # 登录本身产生一条 Login 审计
    resp = client.get('/api/audit?search=Login')
    assert resp.status_code == 200
    logs = resp.get_json()['data']['logs']
    assert any(log['action'] == 'Login' for log in logs)
