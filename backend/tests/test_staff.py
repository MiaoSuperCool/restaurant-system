"""员工账号接口测试：CRUD、权限、重复校验、门店归属、审计保留"""


def _create_store(client, code='S001', name='解放路店'):
    return client.post('/api/stores', json={'code': code, 'name': name}).get_json()['data']


def _create_staff(client, **overrides):
    payload = {
        'username': 'newstaff',
        'real_name': '新员工',
        'email': 'new@example.com',
        'mobile': '13800138002',
        'password': 'Newpass123!',
    }
    payload.update(overrides)
    return client.post('/api/staff', json=payload)


def test_admin_can_crud_staff(client, admin_staff, normal_staff, login):
    login('admin', 'Admin123!')

    # 创建
    resp = _create_staff(client)
    assert resp.status_code == 201
    new_id = resp.get_json()['data']['id']

    # 列表（admin + staff + newstaff）
    resp = client.get('/api/staff')
    assert resp.status_code == 200
    assert resp.get_json()['data']['pagination']['total'] == 3

    # 搜索
    resp = client.get('/api/staff?search=newstaff')
    assert resp.get_json()['data']['pagination']['total'] == 1

    # 修改
    resp = client.put(f'/api/staff/{new_id}', json={'real_name': '改名后'})
    assert resp.status_code == 200
    assert resp.get_json()['data']['real_name'] == '改名后'

    # 删除
    resp = client.delete(f'/api/staff/{new_id}')
    assert resp.status_code == 200
    assert resp.get_json()['success'] is True


def test_non_admin_forbidden(client, normal_staff, login):
    login('staff', 'Staff123!')
    resp = client.get('/api/staff')
    assert resp.status_code == 403


def test_duplicate_username_rejected(client, admin_staff, normal_staff, login):
    login('admin', 'Admin123!')
    resp = _create_staff(client, username='staff')  # 与已有员工重名
    assert resp.status_code == 400
    assert '用户名' in resp.get_json()['message']


def test_create_staff_validates_password_length(client, admin_staff, login):
    login('admin', 'Admin123!')
    assert _create_staff(client, password='123').status_code == 422  # schema 要求 min=6


def test_staff_belongs_to_store(client, admin_staff, login):
    """归属门店会带上门店名一起返回，列表里不用前端再查一次"""
    login('admin', 'Admin123!')
    store = _create_store(client)

    resp = _create_staff(client, store_id=store['id'])
    assert resp.status_code == 201
    body = resp.get_json()['data']
    assert body['store_id'] == store['id']
    assert body['store_name'] == '解放路店'

    # 总部账号（运营/财务/老板）不归属门店，store_id 留空是合法的
    resp = _create_staff(client, username='hq', email='hq@example.com',
                         mobile='13800138009', store_id=None)
    assert resp.status_code == 201
    assert resp.get_json()['data']['store_name'] is None


def test_staff_store_must_exist(client, admin_staff, login):
    login('admin', 'Admin123!')
    resp = _create_staff(client, store_id=99999)
    assert resp.status_code == 404


def test_invalid_employment_type_rejected(client, admin_staff, login):
    login('admin', 'Admin123!')
    assert _create_staff(client, employment_type='intern').status_code == 422


def test_part_time_account_is_shared(client, admin_staff, login):
    """兼职/公用账号是账号属性，不是独立角色——后续权限按收银员/服务员套"""
    login('admin', 'Admin123!')
    resp = _create_staff(client, employment_type='part_time', is_shared=True)
    body = resp.get_json()['data']
    assert body['employment_type'] == 'part_time'
    assert body['employment_type_label'] == '兼职'
    assert body['is_shared'] is True


def test_delete_staff_keeps_audit_log(client, admin_staff, normal_staff, login):
    """删除员工后其审计记录保留（operator_id 置 NULL）"""
    login('admin', 'Admin123!')
    # staff 自己登录一次，产生一条 operator_id=staff 的审计
    client.post('/api/auth/logout')
    login('staff', 'Staff123!')
    client.post('/api/auth/logout')

    # admin 删除 staff
    login('admin', 'Admin123!')
    resp = client.delete(f'/api/staff/{normal_staff.id}')
    assert resp.status_code == 200

    # staff 的 Login 审计记录仍在，且 operator_id 已置空
    resp = client.get('/api/audit')
    logs = resp.get_json()['data']['logs']
    staff_logs = [log for log in logs
                  if log['action'] == 'Login' and log['operator_name'] == 'staff']
    assert staff_logs
    assert staff_logs[0]['operator_id'] is None


def test_page_param_validated(client, admin_staff, login):
    """page 传负数 → 422（flask-smorest 由 PageQuerySchema 校验，不再静默夹回 1）"""
    login('admin', 'Admin123!')
    resp = client.get('/api/staff?page=-5')
    assert resp.status_code == 422
    assert resp.get_json()['success'] is False
    # 非法参数仍会正常分页的兜底：不传 page 时默认第 1 页
    resp = client.get('/api/staff')
    assert resp.status_code == 200
