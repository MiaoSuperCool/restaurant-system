"""门店接口测试：CRUD、权限、编码唯一、枚举校验、审计留痕"""


def _create_store(client, **overrides):
    payload = {
        'code': 'S001',
        'name': '解放路店',
        'store_type': 'dine_in',
        'address': '解放路 1 号',
        'phone': '0571-88880001',
    }
    payload.update(overrides)
    return client.post('/api/stores', json=payload)


def test_admin_can_crud_store(client, admin_user, login):
    login('admin', 'Admin123!')

    # 创建：未传的字段用 schema 默认值（营业中 / 新系统）
    resp = _create_store(client)
    assert resp.status_code == 201
    store = resp.get_json()['data']
    assert store['code'] == 'S001'
    assert store['business_status'] == 'open'
    assert store['run_mode'] == 'new'
    store_id = store['id']

    # 列表
    resp = client.get('/api/stores')
    assert resp.status_code == 200
    assert resp.get_json()['data']['pagination']['total'] == 1

    # 搜索命中地址
    resp = client.get('/api/stores?search=解放路')
    assert resp.get_json()['data']['pagination']['total'] == 1

    # 修改：只传一个字段，其余不动
    resp = client.put(f'/api/stores/{store_id}', json={'business_status': 'resting'})
    assert resp.status_code == 200
    body = resp.get_json()['data']
    assert body['business_status'] == 'resting'
    assert body['name'] == '解放路店'

    # 删除
    resp = client.delete(f'/api/stores/{store_id}')
    assert resp.status_code == 200
    assert client.get('/api/stores').get_json()['data']['pagination']['total'] == 0


def test_login_required(client, app):
    resp = client.get('/api/stores')
    assert resp.status_code == 401


def test_non_admin_can_read_but_not_write(client, normal_user, login):
    """普通员工能拉门店列表（各表单要选归属门店），但改不了"""
    login('staff', 'Staff123!')

    assert client.get('/api/stores').status_code == 200
    assert client.get('/api/stores/options').status_code == 200

    assert _create_store(client).status_code == 403


def test_duplicate_code_and_name_rejected(client, admin_user, login):
    login('admin', 'Admin123!')
    _create_store(client)

    # 编码重复
    resp = _create_store(client, name='另一家店')
    assert resp.status_code == 400
    assert 'S001' in resp.get_json()['message']

    # 名称重复
    resp = _create_store(client, code='S002')
    assert resp.status_code == 400
    assert '解放路店' in resp.get_json()['message']


def test_invalid_enum_rejected(client, admin_user, login):
    """store_type / business_status 只接受模型里定义的取值 → 422"""
    login('admin', 'Admin123!')
    assert _create_store(client, store_type='takeaway').status_code == 422
    assert _create_store(client, business_status='sleeping').status_code == 422


def test_update_missing_store_404(client, admin_user, login):
    login('admin', 'Admin123!')
    resp = client.put('/api/stores/99999', json={'name': '不存在'})
    assert resp.status_code == 404


def test_options_endpoint(client, admin_user, login):
    """下拉选项：不分页，只带表单需要的字段"""
    login('admin', 'Admin123!')
    _create_store(client)
    _create_store(client, code='S002', name='文化路店', business_status='closed')

    resp = client.get('/api/stores/options')
    assert resp.status_code == 200
    stores = resp.get_json()['data']['stores']
    assert [s['code'] for s in stores] == ['S001', 'S002']
    assert stores[1]['business_status_label'] == '已停业'


def test_store_changes_are_audited(client, admin_user, login):
    """改门店要留痕，且 resource 标成 store（审计日志覆盖关键动作）"""
    login('admin', 'Admin123!')
    store_id = _create_store(client).get_json()['data']['id']
    client.put(f'/api/stores/{store_id}', json={'name': '解放路旗舰店'})

    resp = client.get('/api/audit?search=STORE')
    logs = resp.get_json()['data']['logs']
    update_logs = [log for log in logs if log['action'] == 'UPDATE_STORE']
    assert update_logs
    assert update_logs[0]['resource'] == 'store'
    # 变动前后值都在
    assert update_logs[0]['old_value']['name'] == '解放路店'
    assert update_logs[0]['new_value']['name'] == '解放路旗舰店'


def test_delete_blocked_when_store_is_referenced(app, client, admin_user, login):
    """门店一旦被别的表引用就不能删（否则历史数据成孤儿），该走「已停业」

    测试用一张临时表模拟订单/员工等关联表——这样不用等那些表真的建出来，
    就能验证「扫外键」这套检查是有效的，而不是一句空跑的代码。
    """
    from sqlalchemy import Column, ForeignKey, Integer, Table

    from backend.app.extensions import db

    login('admin', 'Admin123!')
    store_id = _create_store(client).get_json()['data']['id']

    # 造一张带 store_id 外键的临时表，并让它引用这家门店
    tmp = Table(
        '_tmp_store_ref', db.metadata,
        Column('id', Integer, primary_key=True),
        Column('store_id', Integer, ForeignKey('store.id')),
    )
    try:
        with app.app_context():
            tmp.create(db.engine)
            db.session.execute(tmp.insert().values(store_id=store_id))
            db.session.commit()

        # 有引用 → 400，且提示改用停业
        resp = client.delete(f'/api/stores/{store_id}')
        assert resp.status_code == 400
        message = resp.get_json()['message']
        assert '_tmp_store_ref 1 条' in message
        assert '已停业' in message

        # 引用清掉后就能正常删除
        with app.app_context():
            db.session.execute(tmp.delete())
            db.session.commit()
        assert client.delete(f'/api/stores/{store_id}').status_code == 200
    finally:
        with app.app_context():
            tmp.drop(db.engine, checkfirst=True)
        # 从 metadata 摘掉，免得污染后面用例的 create_all
        db.metadata.remove(tmp)


def test_unreferenced_store_can_still_be_deleted(client, admin_user, login):
    """没用过的门店（建错了、测试用的）仍然可以真删，不必被迫停业"""
    login('admin', 'Admin123!')
    store_id = _create_store(client).get_json()['data']['id']
    assert client.delete(f'/api/stores/{store_id}').status_code == 200
