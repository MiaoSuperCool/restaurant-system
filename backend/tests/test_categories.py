"""菜品分类接口测试：CRUD、名称唯一、门店适用范围、删除保护、权限"""


def _create_category(client, **overrides):
    payload = {'name': '主食', 'icon': '🍜'}
    payload.update(overrides)
    return client.post('/api/categories', json=payload)


def _create_store(client, code='S001', name='解放路店'):
    return client.post('/api/stores', json={'code': code, 'name': name}).get_json()['data']


def test_admin_can_crud_category(client, admin_staff, login):
    login('admin', 'Admin123!')

    resp = _create_category(client)
    assert resp.status_code == 201
    category = resp.get_json()['data']
    assert category['name'] == '主食'
    # 没指定门店 = 全公司通用
    assert category['is_all_stores'] is True
    assert category['store_ids'] == []
    category_id = category['id']

    assert client.get('/api/categories').get_json()['data']['pagination']['total'] == 1
    assert client.get('/api/categories/options').get_json()['data']['categories'][0]['name'] == '主食'

    resp = client.put(f'/api/categories/{category_id}', json={'name': '面食'})
    assert resp.status_code == 200
    assert resp.get_json()['data']['name'] == '面食'

    assert client.delete(f'/api/categories/{category_id}').status_code == 200
    assert client.get('/api/categories').get_json()['data']['pagination']['total'] == 0


def test_new_category_goes_last(client, admin_staff, login):
    """不传排序时默认排到最后，运营不用一上来就填数字"""
    login('admin', 'Admin123!')
    first = _create_category(client, name='主食').get_json()['data']
    second = _create_category(client, name='饮品').get_json()['data']

    assert first['sort_order'] < second['sort_order']


def test_duplicate_name_rejected(client, admin_staff, login):
    login('admin', 'Admin123!')
    _create_category(client)
    resp = _create_category(client, icon='🥤')
    assert resp.status_code == 400
    assert '主食' in resp.get_json()['message']


def test_store_scope(client, admin_staff, login):
    """分类可以限定只在某些门店显示；不选 = 全公司通用"""
    login('admin', 'Admin123!')
    store = _create_store(client)

    resp = _create_category(client, store_ids=[store['id']])
    data = resp.get_json()['data']
    assert data['is_all_stores'] is False
    assert data['store_ids'] == [store['id']]
    assert data['store_names'] == ['解放路店']

    # 改回全公司通用：传空数组
    resp = client.put(f'/api/categories/{data["id"]}', json={'store_ids': []})
    assert resp.get_json()['data']['is_all_stores'] is True


def test_unknown_store_rejected(client, admin_staff, login):
    login('admin', 'Admin123!')
    assert _create_category(client, store_ids=[99999]).status_code == 404


def test_delete_blocked_when_category_has_dishes(client, admin_staff, login):
    """分类下面还有菜品就不能删，否则那些菜成了没分类的孤儿"""
    login('admin', 'Admin123!')
    category = _create_category(client).get_json()['data']
    client.post('/api/dishes', json={
        'category_id': category['id'], 'name': '牛肉面', 'base_price': '15.00',
    })

    resp = client.delete(f'/api/categories/{category["id"]}')
    assert resp.status_code == 400
    assert '菜品 1 条' in resp.get_json()['message']

    # 菜品挪走后就能删了
    other = _create_category(client, name='面食').get_json()['data']
    dish_id = client.get('/api/dishes').get_json()['data']['dishes'][0]['id']
    client.put(f'/api/dishes/{dish_id}', json={'category_id': other['id']})
    assert client.delete(f'/api/categories/{category["id"]}').status_code == 200


def test_requires_menu_permission(client, normal_staff, make_staff, login):
    """没有 menu:view 读不了，没有 menu:create 建不了"""
    login('staff', 'Staff123!')
    assert client.get('/api/categories').status_code == 403
    assert _create_category(client).status_code == 403
    client.post('/api/auth/logout')

    # 收银员有 menu:view（点单要看菜单）但没有 menu:create
    make_staff('shouyin', 'cashier')
    login('shouyin', 'Passw0rd!')
    assert client.get('/api/categories').status_code == 200
    assert _create_category(client).status_code == 403


def test_store_scope_role_cannot_touch_categories(client, admin_staff, make_staff, login):
    """店长有 menu:update，但那是给「本店菜单」用的，不能顺着它改全公司的分类

    分类接口复用的就是 menu:* 这组码——`menu:create` / `menu:delete` 只发给了
    全公司范围的角色，所以建和删本来就拦得住；但店长**有** `menu:update`
    （他每天要改本店菜单），光靠权限码挡不住，必须在服务层再查一次数据范围。
    """
    login('admin', 'Admin123!')
    store = _create_store(client)
    category = _create_category(client).get_json()['data']
    client.post('/api/auth/logout')

    make_staff('dianzhang', 'store_manager', store_id=store['id'])
    login('dianzhang', 'Passw0rd!')

    # 看得了（有 menu:view）
    assert client.get('/api/categories').status_code == 200
    # 建不了（没有 menu:create，装饰器就拦下了）
    assert _create_category(client, name='店长想建').status_code == 403

    # 改不了 —— 这条是关键，他的权限码是够的
    resp = client.put(f'/api/categories/{category["id"]}', json={'name': '店长想改'})
    assert resp.status_code == 403
    assert '全公司' in resp.get_json()['message']

    # 改适用范围也不行（把自家店塞进「只在大店卖」的分类里）
    resp = client.put(f'/api/categories/{category["id"]}', json={'store_ids': [store['id']]})
    assert resp.status_code == 403

    # 关掉整个分类更不行
    resp = client.put(f'/api/categories/{category["id"]}', json={'is_visible': False})
    assert resp.status_code == 403

    # 三次都没改进去
    client.post('/api/auth/logout')
    login('admin', 'Admin123!')
    after = client.get('/api/categories').get_json()['data']['categories'][0]
    assert after['name'] == '主食'
    assert after['is_visible'] is True
    assert after['is_all_stores'] is True
