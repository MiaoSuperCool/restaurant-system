"""门店菜单（多店定价）测试：默认值、覆盖、恢复、数据范围、字段级权限"""


def _create_store(client, code='S001', name='解放路店'):
    return client.post('/api/stores', json={'code': code, 'name': name}).get_json()['data']


def _create_category(client, name='面食'):
    return client.post('/api/categories', json={'name': name}).get_json()['data']


def _create_dish(client, category_id, name='牛肉面', base_price='15.00', **overrides):
    payload = {'category_id': category_id, 'name': name, 'base_price': base_price}
    payload.update(overrides)
    return client.post('/api/dishes', json=payload).get_json()['data']


def _setup(client):
    """建一家店 + 一道菜，返回 (store, dish)"""
    store = _create_store(client)
    category = _create_category(client)
    dish = _create_dish(client, category['id'])
    return store, dish


def _menu_row(client, store_id, dish_id):
    rows = client.get(f'/api/stores/{store_id}/menu').get_json()['data']['dishes']
    return next(row for row in rows if row['dish_id'] == dish_id)


def test_menu_defaults_to_dish_base_price(client, admin_staff, login):
    """没做过任何设置的门店，菜单直接沿用菜品基础价、可售、不限量"""
    login('admin', 'Admin123!')
    store, dish = _setup(client)

    row = _menu_row(client, store['id'], dish['id'])
    assert row['price'] == 15.0
    assert row['base_price'] == 15.0
    assert row['has_price_override'] is False
    assert row['has_override'] is False
    assert row['is_available'] is True
    assert row['daily_limit'] is None


def test_menu_carries_option_groups(client, admin_staff, login):
    """菜单要带规格组——点单界面靠它渲染规格选择器，不然收银员没法选大份/加料"""
    login('admin', 'Admin123!')
    store = _create_store(client)
    category = _create_category(client)
    dish = _create_dish(client, category['id'], option_groups=[
        {'name': '份量', 'selection_type': 'single', 'is_required': True,
         'options': [{'name': '标准', 'extra_price': '0'}, {'name': '大份', 'extra_price': '4'}]},
        {'name': '加料', 'selection_type': 'multiple', 'is_required': False,
         'options': [{'name': '加蛋', 'extra_price': '3'}]},
    ])

    rows = client.get(f'/api/stores/{store["id"]}/menu').get_json()['data']['dishes']
    dish_id = next(d for d in client.get('/api/dishes').get_json()['data']['dishes']
                   if d['name'] == dish['name'])['id']
    row = next(r for r in rows if r['dish_id'] == dish_id)

    groups = row['option_groups']
    assert [g['name'] for g in groups] == ['份量', '加料']
    assert groups[0]['is_required'] is True
    assert [o['name'] for o in groups[0]['options']] == ['标准', '大份']


def test_price_override_does_not_change_dish_base_price(client, admin_staff, login):
    """本店调价不该动到全公司的基础价——这正是「菜品和门店解耦」的意义"""
    login('admin', 'Admin123!')
    store, dish = _setup(client)

    resp = client.put(f'/api/stores/{store["id"]}/dishes/{dish["id"]}',
                      json={'price': '18.00'})
    assert resp.status_code == 200
    assert resp.get_json()['data']['price'] == 18.0
    assert resp.get_json()['data']['has_price_override'] is True

    row = _menu_row(client, store['id'], dish['id'])
    assert row['price'] == 18.0          # 本店卖 18
    assert row['base_price'] == 15.0     # 公司基础价还是 15

    # 换一家店看，还是基础价
    other = _create_store(client, code='S002', name='文化路店')
    assert _menu_row(client, other['id'], dish['id'])['price'] == 15.0


def test_delist_dish_for_one_store(client, admin_staff, login):
    """某家店不卖某道菜：基础价不变，只是这家店下架"""
    login('admin', 'Admin123!')
    store, dish = _setup(client)
    other = _create_store(client, code='S002', name='文化路店')

    client.put(f'/api/stores/{store["id"]}/dishes/{dish["id"]}', json={'is_available': False})

    assert _menu_row(client, store['id'], dish['id'])['is_available'] is False
    assert _menu_row(client, other['id'], dish['id'])['is_available'] is True


def test_daily_limit(client, admin_staff, login):
    login('admin', 'Admin123!')
    store, dish = _setup(client)

    resp = client.put(f'/api/stores/{store["id"]}/dishes/{dish["id"]}',
                      json={'daily_limit': 20})
    assert resp.status_code == 200
    assert resp.get_json()['data']['daily_limit'] == 20

    # 0 或负数没有意义，直接拒绝
    assert client.put(f'/api/stores/{store["id"]}/dishes/{dish["id"]}',
                      json={'daily_limit': 0}).status_code == 422


def test_reset_to_default(client, admin_staff, login):
    """清除覆盖有两种写法：DELETE 整个覆盖，或者把 price 传 null"""
    login('admin', 'Admin123!')
    store, dish = _setup(client)
    url = f'/api/stores/{store["id"]}/dishes/{dish["id"]}'

    client.put(url, json={'price': '18.00', 'is_available': False})
    assert _menu_row(client, store['id'], dish['id'])['has_override'] is True

    # 传 null 只取消价格覆盖，下架状态保留
    client.put(url, json={'price': None})
    row = _menu_row(client, store['id'], dish['id'])
    assert row['price'] == 15.0
    assert row['has_price_override'] is False
    assert row['is_available'] is False
    assert row['has_override'] is True

    # DELETE 整个覆盖，回到全默认
    assert client.delete(url).status_code == 200
    row = _menu_row(client, store['id'], dish['id'])
    assert row['is_available'] is True
    assert row['has_override'] is False

    # 已经没了再删一次 → 404
    assert client.delete(url).status_code == 404


def test_empty_body_does_not_create_record(client, admin_staff, login):
    """一个字段都没传就别建空记录——没有行本来就等于「用默认值」"""
    login('admin', 'Admin123!')
    store, dish = _setup(client)

    resp = client.put(f'/api/stores/{store["id"]}/dishes/{dish["id"]}', json={})
    assert resp.status_code == 200
    assert resp.get_json()['data'] is None
    assert _menu_row(client, store['id'], dish['id'])['has_override'] is False


def test_discontinued_dish_not_in_menu(client, admin_staff, login):
    """已停售是全公司的，任何门店的菜单里都不该出现"""
    login('admin', 'Admin123!')
    store, dish = _setup(client)
    client.put(f'/api/dishes/{dish["id"]}', json={'status': 'discontinued'})

    assert client.get(f'/api/stores/{store["id"]}/menu').get_json()['data']['dishes'] == []


def test_menu_filters(client, admin_staff, login):
    login('admin', 'Admin123!')
    store = _create_store(client)
    noodles = _create_category(client, '面食')
    drinks = _create_category(client, '饮品')
    _create_dish(client, noodles['id'], name='牛肉面')
    _create_dish(client, drinks['id'], name='可乐', base_price='5.00')

    all_rows = client.get(f'/api/stores/{store["id"]}/menu').get_json()['data']['dishes']
    assert len(all_rows) == 2

    only_drinks = client.get(
        f'/api/stores/{store["id"]}/menu?category_id={drinks["id"]}'
    ).get_json()['data']['dishes']
    assert [r['name'] for r in only_drinks] == ['可乐']

    searched = client.get(
        f'/api/stores/{store["id"]}/menu?search=牛肉'
    ).get_json()['data']['dishes']
    assert [r['name'] for r in searched] == ['牛肉面']


def test_missing_store_or_dish(client, admin_staff, login):
    login('admin', 'Admin123!')
    _store, dish = _setup(client)
    store = _create_store(client, code='S003', name='第三家店')

    assert client.get('/api/stores/99999/menu').status_code == 404
    assert client.put(f'/api/stores/99999/dishes/{dish["id"]}',
                      json={'price': '1.00'}).status_code == 404
    assert client.put(f'/api/stores/{store["id"]}/dishes/99999',
                      json={'price': '1.00'}).status_code == 404


def test_store_manager_is_limited_to_own_store(client, admin_staff, make_staff, login):
    """数据范围：店长只看得到、也只改得了自己那家店的菜单"""
    login('admin', 'Admin123!')
    own_store, dish = _setup(client)
    other_store = _create_store(client, code='S002', name='文化路店')
    # 给别家店设个覆盖价，验证店长看不到
    client.put(f'/api/stores/{other_store["id"]}/dishes/{dish["id"]}', json={'price': '99.00'})
    client.post('/api/auth/logout')

    make_staff('dianzhang', 'store_manager', store_id=own_store['id'])
    login('dianzhang', 'Passw0rd!')

    # 自己店：看得到、改得了（店长有 menu:update + dish:price:edit，都是本店范围）
    assert client.get(f'/api/stores/{own_store["id"]}/menu').status_code == 200
    resp = client.put(f'/api/stores/{own_store["id"]}/dishes/{dish["id"]}',
                      json={'price': '16.00'})
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()['data']['price'] == 16.0

    # 别家店：看不了也改不了
    resp = client.get(f'/api/stores/{other_store["id"]}/menu')
    assert resp.status_code == 403
    assert '其他门店' in resp.get_json()['message']

    resp = client.put(f'/api/stores/{other_store["id"]}/dishes/{dish["id"]}',
                      json={'price': '1.00'})
    assert resp.status_code == 403
    assert '其他门店的菜单' in resp.get_json()['message']


def test_price_change_needs_dish_price_edit(app, client, admin_staff, make_staff, login):
    """有 menu:update 不等于能改价——和菜品那边同一套字段级权限

    店长三种权限都有，所以这里临时造一个「能管菜单、不能改价」的角色。
    """
    from backend.app.extensions import db
    from backend.app.models import Permission, Role

    login('admin', 'Admin123!')
    store, dish = _setup(client)
    url = f'/api/stores/{store["id"]}/dishes/{dish["id"]}'
    # 管理员先把本店价格定成 18，好验证「重复提交同一个值不算改」
    client.put(url, json={'price': '18.00'})
    client.post('/api/auth/logout')

    with app.app_context():
        role = Role(code='menu_only', name='菜单维护', data_scope='all', description='')
        role.permissions = Permission.query.filter(
            Permission.code.in_(['menu:view', 'menu:update'])
        ).all()
        db.session.add(role)
        db.session.commit()

    make_staff('weihu', 'menu_only')
    login('weihu', 'Passw0rd!')

    # 改上下架和限量可以
    assert client.put(url, json={'daily_limit': 10}).status_code == 200

    # 改价不行
    resp = client.put(url, json={'price': '20.00'})
    assert resp.status_code == 403
    assert '改价' in resp.get_json()['message']

    # 下架需要 dish:online，这个角色也没有
    resp = client.put(url, json={'is_available': False})
    assert resp.status_code == 403
    assert '上下架' in resp.get_json()['message']

    # 传了价格但和当前值一样，不算「改」，不该报错
    assert client.put(url, json={'price': '18.00'}).status_code == 200


def test_store_dish_field_permission_dict_is_single_source(app, client, admin_staff, make_staff,
                                                           login, monkeypatch):
    """门店菜单这边同一套：往 FIELD_PERMISSIONS 加字段，检查自动跟上

    和菜品基础那边是一对。门店这边多一份 FIELD_DEFAULTS——这家店还没建覆盖
    记录时，各字段的「当前值」不一样（价格默认「没覆盖」，上架默认 true）。
    """
    from backend.app.extensions import db
    from backend.app.models import Permission, Role
    from backend.app.services.store_dish_service import StoreDishService

    login('admin', 'Admin123!')
    store, dish = _setup(client)
    url = f'/api/stores/{store["id"]}/dishes/{dish["id"]}'
    client.post('/api/auth/logout')

    # 临时把「每日限量」也划进受管字段
    monkeypatch.setitem(StoreDishService.FIELD_PERMISSIONS, 'daily_limit', 'dish:price:edit')
    monkeypatch.setitem(StoreDishService.FIELD_LABELS, 'daily_limit', '每日限量')
    monkeypatch.setitem(StoreDishService.FIELD_DEFAULTS, 'daily_limit', None)

    # 造一个「能管菜单、没有 dish:price:edit」的角色
    with app.app_context():
        role = Role(code='menu_only_b', name='菜单维护B', data_scope='all', description='')
        role.permissions = Permission.query.filter(
            Permission.code.in_(['menu:view', 'menu:update'])
        ).all()
        db.session.add(role)
        db.session.commit()

    make_staff('weihu_b', 'menu_only_b')
    login('weihu_b', 'Passw0rd!')

    resp = client.put(url, json={'daily_limit': 20})
    assert resp.status_code == 403
    assert '每日限量' in resp.get_json()['message']


def test_category_store_scope_filters_menu(client, admin_staff, login):
    """分类的「适用门店」要真的过滤菜单，不能只是存着好看

    这个功能曾经是「存了、也显示了，但没生效」——管理界面上写着
    「适用门店：解放路店」，顾客在别的店照样看得到那些菜。
    """
    login('admin', 'Admin123!')
    store_a = _create_store(client, code='S001', name='解放路店')
    store_b = _create_store(client, code='S002', name='文化路店')

    # 只在大店卖的「商务套餐」
    limited = client.post('/api/categories', json={
        'name': '商务套餐', 'store_ids': [store_a['id']],
    }).get_json()['data']
    limited_dish = _create_dish(client, limited['id'], name='商务套餐A', base_price='58.00')

    # 全公司通用的「面食」
    common = _create_category(client, '面食')
    common_dish = _create_dish(client, common['id'], name='牛肉面')

    names_a = [r['name'] for r in
               client.get(f'/api/stores/{store_a["id"]}/menu').get_json()['data']['dishes']]
    names_b = [r['name'] for r in
               client.get(f'/api/stores/{store_b["id"]}/menu').get_json()['data']['dishes']]

    # 适用门店里点了名的，两个分类都看得到
    assert limited_dish['name'] in names_a
    assert common_dish['name'] in names_a

    # 没点名的店，只有通用分类的菜
    assert limited_dish['name'] not in names_b
    assert common_dish['name'] in names_b


def test_category_store_scope_filters_public_menu(client, admin_staff, login):
    """顾客端也要生效——这条规则不该只管内部菜单"""
    login('admin', 'Admin123!')
    store_a = _create_store(client, code='S001', name='解放路店')
    store_b = _create_store(client, code='S002', name='文化路店')

    limited = client.post('/api/categories', json={
        'name': '限定分类', 'store_ids': [store_a['id']],
    }).get_json()['data']
    dish = _create_dish(client, limited['id'], name='限定菜', base_price='10.00')

    names_a = [d['name'] for d in
               client.get(f'/api/public/stores/{store_a["id"]}/menu').get_json()['data']['dishes']]
    names_b = [d['name'] for d in
               client.get(f'/api/public/stores/{store_b["id"]}/menu').get_json()['data']['dishes']]

    assert dish['name'] in names_a
    assert dish['name'] not in names_b


def test_removing_store_scope_makes_category_universal(client, admin_staff, login):
    """把适用范围改回空数组，分类就恢复成全公司通用"""
    login('admin', 'Admin123!')
    store_a = _create_store(client, code='S001', name='解放路店')
    store_b = _create_store(client, code='S002', name='文化路店')

    category = client.post('/api/categories', json={
        'name': '临时限定', 'store_ids': [store_a['id']],
    }).get_json()['data']
    dish = _create_dish(client, category['id'], name='某道菜', base_price='10.00')

    def visible_at(store):
        rows = client.get(f'/api/stores/{store["id"]}/menu').get_json()['data']['dishes']
        return dish['name'] in [r['name'] for r in rows]

    assert visible_at(store_a) is True
    assert visible_at(store_b) is False

    # 清空适用范围 → 全公司通用
    client.put(f'/api/categories/{category["id"]}', json={'store_ids': []})
    assert visible_at(store_b) is True


def test_store_dish_changes_are_audited(client, admin_staff, login):
    """调价、上下架属于要留痕的关键动作"""
    login('admin', 'Admin123!')
    store, dish = _setup(client)
    url = f'/api/stores/{store["id"]}/dishes/{dish["id"]}'

    client.put(url, json={'price': '18.00'})
    client.delete(url)

    logs = client.get('/api/audit?search=STORE_DISH').get_json()['data']['logs']
    actions = [log['action'] for log in logs]
    assert 'UPDATE_STORE_DISH' in actions
    assert 'DELETE_STORE_DISH' in actions
    update_log = next(log for log in logs if log['action'] == 'UPDATE_STORE_DISH')
    assert update_log['new_value']['price'] == 18.0
