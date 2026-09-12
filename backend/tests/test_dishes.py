"""菜品接口测试：CRUD、规格组/选项、字段级权限、数据范围、删除保护"""


def _create_category(client, name='面食'):
    return client.post('/api/categories', json={'name': name}).get_json()['data']


def _create_dish(client, category_id, **overrides):
    payload = {
        'category_id': category_id,
        'name': '牛肉面',
        'base_price': '15.00',
        'description': '招牌',
    }
    payload.update(overrides)
    return client.post('/api/dishes', json=payload)


NIUROU_MIAN_OPTIONS = [
    {
        'name': '份量', 'selection_type': 'single', 'is_required': True,
        'options': [
            {'name': '中份', 'extra_price': '0'},
            {'name': '大份', 'extra_price': '3'},
        ],
    },
    {
        'name': '加料', 'selection_type': 'multiple', 'is_required': False,
        'options': [
            {'name': '加蛋', 'extra_price': '2'},
            {'name': '加牛肉', 'extra_price': '6'},
        ],
    },
]


def test_create_dish_with_options(client, admin_staff, login):
    """设计文档里的例子：牛肉面 ¥15，大份 +3、加蛋 +2"""
    login('admin', 'Admin123!')
    category = _create_category(client)

    resp = _create_dish(client, category['id'], option_groups=NIUROU_MIAN_OPTIONS)
    assert resp.status_code == 201
    dish = resp.get_json()['data']

    assert dish['base_price'] == 15.0
    assert dish['category_name'] == '面食'
    assert dish['status'] == 'active'

    groups = dish['option_groups']
    assert [g['name'] for g in groups] == ['份量', '加料']
    assert groups[0]['selection_type_label'] == '单选'
    assert groups[1]['selection_type'] == 'multiple'
    assert groups[1]['is_required'] is False
    assert [o['name'] for o in groups[0]['options']] == ['中份', '大份']
    assert groups[0]['options'][1]['extra_price'] == 3.0


def test_list_excludes_options_and_filters_by_category(client, admin_staff, login):
    login('admin', 'Admin123!')
    noodles = _create_category(client, '面食')
    drinks = _create_category(client, '饮品')
    _create_dish(client, noodles['id'], option_groups=NIUROU_MIAN_OPTIONS)
    _create_dish(client, drinks['id'], name='可乐', base_price='5.00')

    # 列表不带规格结构（太重），要完整结构用详情接口
    dishes = client.get('/api/dishes').get_json()['data']['dishes']
    assert len(dishes) == 2
    assert 'option_groups' not in dishes[0]

    # 按分类筛选
    only_drinks = client.get(f'/api/dishes?category_id={drinks["id"]}').get_json()['data']['dishes']
    assert [d['name'] for d in only_drinks] == ['可乐']

    # 详情带规格
    dish_id = client.get(f'/api/dishes?category_id={noodles["id"]}').get_json()['data']['dishes'][0]['id']
    detail = client.get(f'/api/dishes/{dish_id}').get_json()['data']
    assert len(detail['option_groups']) == 2


def test_option_ids_survive_edit(client, admin_staff, login):
    """改规格时按 id 对齐，不能全删重建

    订单明细会引用选项 id——重建会让历史订单指到不存在的选项上，
    「加蛋卖了多少份」这类统计就断了。
    """
    login('admin', 'Admin123!')
    category = _create_category(client)
    dish = _create_dish(client, category['id'], option_groups=NIUROU_MIAN_OPTIONS).get_json()['data']

    size_group = dish['option_groups'][0]
    medium_id = size_group['options'][0]['id']
    large_id = size_group['options'][1]['id']

    # 大份涨价到 4、中份删掉、新增小份
    updated_groups = [
        {
            'id': size_group['id'], 'name': '份量', 'selection_type': 'single', 'is_required': True,
            'options': [
                {'id': large_id, 'name': '大份', 'extra_price': '4'},
                {'name': '小份', 'extra_price': '0'},
            ],
        },
    ]
    resp = client.put(f'/api/dishes/{dish["id"]}', json={'option_groups': updated_groups})
    assert resp.status_code == 200
    groups = resp.get_json()['data']['option_groups']

    # 只剩一个组；大份保留了原来的 id（不是重建的），中份被删，小份是新的
    assert len(groups) == 1
    assert groups[0]['id'] == size_group['id']
    by_name = {o['name']: o for o in groups[0]['options']}
    assert by_name['大份']['id'] == large_id
    assert by_name['大份']['extra_price'] == 4.0
    assert '中份' not in by_name
    assert by_name['小份']['id'] != medium_id


def test_sort_order_follows_array_position(client, admin_staff, login):
    """前端不传排序数字，靠数组顺序表达——传进来的先后就是显示顺序

    （曾经给 sort_order 兜底成 0，结果所有组都是 0，运营调的顺序存不下来）
    """
    login('admin', 'Admin123!')
    category = _create_category(client)

    dish = _create_dish(client, category['id'], option_groups=[
        {'name': '辣度', 'options': [{'name': '微辣', 'extra_price': '0'}]},
        {'name': '份量', 'options': [{'name': '大份', 'extra_price': '3'}]},
    ]).get_json()['data']

    assert [g['name'] for g in dish['option_groups']] == ['辣度', '份量']
    assert [g['sort_order'] for g in dish['option_groups']] == [0, 1]

    # 前端把两组调换顺序再提交，顺序要真的变
    def _to_payload(group):
        """只挑 schema 认识的字段回传（多传字段会被未知字段校验拦下，这是故意的）"""
        return {
            'id': group['id'], 'name': group['name'],
            'selection_type': group['selection_type'],
            'is_required': group['is_required'],
            'options': [
                {'id': o['id'], 'name': o['name'], 'extra_price': str(o['extra_price'])}
                for o in group['options']
            ],
        }

    reversed_groups = [_to_payload(dish['option_groups'][1]), _to_payload(dish['option_groups'][0])]
    resp = client.put(f'/api/dishes/{dish["id"]}', json={'option_groups': reversed_groups})
    assert [g['name'] for g in resp.get_json()['data']['option_groups']] == ['份量', '辣度']


def test_stale_option_id_rejected(client, admin_staff, login):
    """传了不属于这道菜的选项 id → 404，不能静默当成新选项建一个"""
    login('admin', 'Admin123!')
    category = _create_category(client)
    dish = _create_dish(client, category['id']).get_json()['data']

    resp = client.put(f'/api/dishes/{dish["id"]}', json={'option_groups': [
        {'name': '份量', 'options': [{'id': 99999, 'name': '大份', 'extra_price': '3'}]},
    ]})
    assert resp.status_code == 404


def test_option_group_needs_at_least_one_option(client, admin_staff, login):
    """空的规格组会让顾客卡在一个没得选的必选组上 → 422"""
    login('admin', 'Admin123!')
    category = _create_category(client)
    resp = _create_dish(client, category['id'], option_groups=[
        {'name': '份量', 'options': []},
    ])
    assert resp.status_code == 422


def test_unknown_category_rejected(client, admin_staff, login):
    login('admin', 'Admin123!')
    assert _create_dish(client, 99999).status_code == 404


def test_field_level_permissions(app, client, admin_staff, make_staff, login):
    """有 menu:update 不等于能改价格——改价和上下架各有专门的权限码

    预置角色里恰好没有「只改菜名不能改价」的组合，所以这里临时造一个角色，
    验证这个机制本身是生效的（三期做多角色管理时会真的用到）。
    """
    from backend.app.extensions import db
    from backend.app.models import Permission, Role

    login('admin', 'Admin123!')
    category = _create_category(client)
    dish = _create_dish(client, category['id']).get_json()['data']

    # 造一个「能改菜品、不能改价也不能上下架」的角色
    with app.app_context():
        role = Role(code='menu_editor', name='菜单编辑', data_scope='all', description='')
        role.permissions = Permission.query.filter(
            Permission.code.in_(['menu:view', 'menu:update'])
        ).all()
        db.session.add(role)
        db.session.commit()
    client.post('/api/auth/logout')

    make_staff('bianji', 'menu_editor')
    login('bianji', 'Passw0rd!')

    # 改菜名可以
    resp = client.put(f'/api/dishes/{dish["id"]}', json={'name': '红烧牛肉面'})
    assert resp.status_code == 200
    assert resp.get_json()['data']['name'] == '红烧牛肉面'

    # 改价不行
    resp = client.put(f'/api/dishes/{dish["id"]}', json={'base_price': '18.00'})
    assert resp.status_code == 403
    assert '改价' in resp.get_json()['message']

    # 上下架也不行
    resp = client.put(f'/api/dishes/{dish["id"]}', json={'status': 'discontinued'})
    assert resp.status_code == 403
    assert '上下架' in resp.get_json()['message']

    # 传了但没变（和自己当前值一样）不算改，不该报错
    assert client.put(f'/api/dishes/{dish["id"]}', json={'name': '红烧牛肉面'}).status_code == 200


def test_store_scope_cannot_touch_company_dishes(client, admin_staff, make_staff, login):
    """菜品基础是全公司数据，本店范围的店长改不了——他改的是「门店菜品」"""
    login('admin', 'Admin123!')
    store = client.post('/api/stores', json={'code': 'S001', 'name': '解放路店'}).get_json()['data']
    category = _create_category(client)
    dish = _create_dish(client, category['id'], option_groups=NIUROU_MIAN_OPTIONS).get_json()['data']
    client.post('/api/auth/logout')

    make_staff('dianzhang', 'store_manager', store_id=store['id'])
    login('dianzhang', 'Passw0rd!')

    # 看得了（有 menu:view）
    assert client.get('/api/dishes').status_code == 200
    assert client.get(f'/api/dishes/{dish["id"]}').status_code == 200

    # 但改不了
    resp = client.put(f'/api/dishes/{dish["id"]}', json={'name': '店长想改'})
    assert resp.status_code == 403
    assert '全公司' in resp.get_json()['message']
    assert client.delete(f'/api/dishes/{dish["id"]}').status_code == 403


def test_delete_blocked_when_dish_is_referenced(app, client, admin_staff, login):
    """菜品还在门店菜单里挂着就不能删（更别说以后有订单引用）"""
    from sqlalchemy import Column, ForeignKey, Integer, Table

    from backend.app.extensions import db

    login('admin', 'Admin123!')
    category = _create_category(client)
    dish = _create_dish(client, category['id']).get_json()['data']

    tmp = Table(
        '_tmp_dish_ref', db.metadata,
        Column('id', Integer, primary_key=True),
        Column('dish_id', Integer, ForeignKey('dish.id')),
    )
    try:
        with app.app_context():
            tmp.create(db.engine)
            db.session.execute(tmp.insert().values(dish_id=dish['id']))
            db.session.commit()

        resp = client.delete(f'/api/dishes/{dish["id"]}')
        assert resp.status_code == 400
        assert '已停售' in resp.get_json()['message']
    finally:
        with app.app_context():
            tmp.drop(db.engine, checkfirst=True)
        db.metadata.remove(tmp)


def test_cascade_deletes_options_not_blocking(client, admin_staff, login):
    """规格组/选项是菜品的从属物（CASCADE），不该拦住菜品删除"""
    login('admin', 'Admin123!')
    category = _create_category(client)
    dish = _create_dish(client, category['id'], option_groups=NIUROU_MIAN_OPTIONS).get_json()['data']

    # 有 2 个规格组 + 4 个选项，但都属于这道菜，所以能删
    assert client.delete(f'/api/dishes/{dish["id"]}').status_code == 200
