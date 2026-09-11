"""用户管理接口测试：CRUD、权限、重复校验、审计保留"""


def test_admin_can_crud_user(client, admin_user, normal_user, login):
    login('admin', 'Admin123!')

    # 创建
    resp = client.post('/api/users', json={
        'username': 'newuser',
        'real_name': '新用户',
        'email': 'new@example.com',
        'mobile': '13800138002',
        'password': 'Newpass123!',
    })
    assert resp.status_code == 201
    new_id = resp.get_json()['data']['id']

    # 列表（admin + staff + newuser）
    resp = client.get('/api/users')
    assert resp.status_code == 200
    assert resp.get_json()['data']['pagination']['total'] == 3

    # 搜索
    resp = client.get('/api/users?search=newuser')
    assert resp.get_json()['data']['pagination']['total'] == 1

    # 修改
    resp = client.put(f'/api/users/{new_id}', json={'real_name': '改名后'})
    assert resp.status_code == 200
    assert resp.get_json()['data']['real_name'] == '改名后'

    # 删除
    resp = client.delete(f'/api/users/{new_id}')
    assert resp.status_code == 200
    assert resp.get_json()['success'] is True


def test_non_admin_forbidden(client, normal_user, login):
    login('staff', 'Staff123!')
    resp = client.get('/api/users')
    assert resp.status_code == 403


def test_duplicate_username_rejected(client, admin_user, normal_user, login):
    login('admin', 'Admin123!')
    resp = client.post('/api/users', json={
        'username': 'staff',  # 与已有用户重名
        'real_name': '重复',
        'email': 'dup@example.com',
        'mobile': '13800138003',
        'password': 'Dup123!',
    })
    assert resp.status_code == 400
    assert resp.get_json()['success'] is False


def test_create_user_validates_password_length(client, admin_user, login):
    login('admin', 'Admin123!')
    resp = client.post('/api/users', json={
        'username': 'shortpwd',
        'real_name': '短密码',
        'email': 'short@example.com',
        'mobile': '13800138004',
        'password': '123',  # schema 要求 min=6
    })
    assert resp.status_code == 422


def test_delete_user_keeps_audit_log(client, admin_user, normal_user, login):
    """删除用户后其审计记录保留（operator_id 置 NULL）"""
    login('admin', 'Admin123!')
    # staff 自己登录一次，产生一条 operator_id=staff 的审计
    client.post('/api/auth/logout')
    login('staff', 'Staff123!')
    client.post('/api/auth/logout')

    # admin 删除 staff
    login('admin', 'Admin123!')
    resp = client.delete(f'/api/users/{normal_user.id}')
    assert resp.status_code == 200

    # staff 的 Login 审计记录仍在，且 operator_id 已置空
    resp = client.get('/api/audit')
    logs = resp.get_json()['data']['logs']
    staff_logs = [log for log in logs
                  if log['action'] == 'Login' and log['user_name'] == 'staff']
    assert staff_logs
    assert staff_logs[0]['user_id'] is None


def test_page_param_validated(client, admin_user, login):
    """page 传负数 → 422（flask-smorest 由 PageQuerySchema 校验，不再静默夹回 1）"""
    login('admin', 'Admin123!')
    resp = client.get('/api/users?page=-5')
    assert resp.status_code == 422
    assert resp.get_json()['success'] is False
    # 非法参数仍会正常分页的兜底：不传 page 时默认第 1 页
    resp = client.get('/api/users')
    assert resp.status_code == 200
