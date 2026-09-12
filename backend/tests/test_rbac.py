"""权限与数据范围测试

分两层验证：
- 权限码：能不能干这件事（permission_required）
- 数据范围：能碰哪些数据（本店 / 全部）

设计文档反复强调「前端只负责显不显示，后端负责能不能干 + 能碰哪些数据」，
这个文件测的就是后半句。
"""
from backend.app.rbac import PERMISSIONS, ROLES


def _create_store(client, code, name):
    return client.post('/api/stores', json={'code': code, 'name': name}).get_json()['data']


def _two_stores(client):
    """建两家店，返回 (解放路店, 文化路店)"""
    return (_create_store(client, 'S001', '解放路店'),
            _create_store(client, 'S002', '文化路店'))


def test_seed_rbac_is_idempotent(app):
    """种子可以反复跑：不重复建、数量稳定（改了 rbac.py 之后靠它同步）"""
    from backend.app.models import Permission, Role
    from backend.app.rbac import seed_rbac

    with app.app_context():
        created_permissions, created_roles, _ = seed_rbac()
        # 夹具已经播过一次种，再跑应该是 0 新建
        assert (created_permissions, created_roles) == (0, 0)
        assert Permission.query.count() == len(PERMISSIONS)
        assert Role.query.count() == len(ROLES)


def test_role_hierarchy_is_superset():
    """角色之间是层层包含的，下属能干的事上司必须也能干

    设计文档原话是「值班经理是受限版店长」。这条不变量曾经被破坏过：
    店长漏了 order:create，结果值班经理能点单、店长反而不能——
    一个下属有而上司没有的权限，在真实门店里会直接卡住营业。
    """
    specs = {spec['code']: spec for spec in ROLES}

    def perms(code):
        wanted = specs[code]['permissions']
        if wanted == '*':
            return {c for c, _, _ in PERMISSIONS}
        return set(wanted)

    # 服务员、后厨 ⊆ 收银员 ⊆ 值班经理 ⊆ 店长
    # （服务员和后厨是平级，各自只会收银员权限的一个子集）
    assert perms('waiter') <= perms('cashier'), '服务员的能力应该是收银员的子集'
    assert perms('kitchen') <= perms('cashier'), '后厨的能力应该是收银员的子集'
    assert perms('cashier') <= perms('shift_manager'), '值班经理应该是收银员的超集'
    assert perms('shift_manager') <= perms('store_manager'), '店长应该是值班经理的超集'


def test_every_role_permission_code_exists():
    """角色矩阵里写错权限码要在代码层面就拦住，不能等到运行时少给一个权限"""
    known = {code for code, _, _ in PERMISSIONS}
    for spec in ROLES:
        if spec['permissions'] == '*':
            continue
        unknown = set(spec['permissions']) - known
        assert not unknown, f"角色「{spec['name']}」引用了不存在的权限码：{unknown}"


def test_store_manager_sees_only_own_store(client, admin_staff, make_staff, login):
    """店长（本店范围）：门店列表和下拉选项都只看得到自己那家"""
    login('admin', 'Admin123!')
    s1, _s2 = _two_stores(client)
    client.post('/api/auth/logout')

    make_staff('dianzhang', 'store_manager', store_id=s1['id'])
    login('dianzhang', 'Passw0rd!')

    body = client.get('/api/stores').get_json()['data']
    assert body['pagination']['total'] == 1
    assert body['stores'][0]['code'] == 'S001'

    options = client.get('/api/stores/options').get_json()['data']['stores']
    assert [s['code'] for s in options] == ['S001']


def test_ops_manager_sees_all_stores(client, admin_staff, make_staff, login):
    """运营主管（全部范围）：6 家店都看得到"""
    login('admin', 'Admin123!')
    _two_stores(client)
    client.post('/api/auth/logout')

    make_staff('yunying', 'ops_manager')
    login('yunying', 'Passw0rd!')

    assert client.get('/api/stores').get_json()['data']['pagination']['total'] == 2


def test_only_boss_can_manage_stores(client, admin_staff, make_staff, login):
    """门店增删改是 store:manage——按设计文档只有老板有，运营主管只有 store:view"""
    login('admin', 'Admin123!')
    s1, _s2 = _two_stores(client)
    client.post('/api/auth/logout')

    make_staff('yunying', 'ops_manager')
    login('yunying', 'Passw0rd!')

    # 看得到
    assert client.get('/api/stores').status_code == 200
    # 但改不了
    resp = client.put(f'/api/stores/{s1["id"]}', json={'name': '运营想改'})
    assert resp.status_code == 403
    assert '门店管理' in resp.get_json()['message']


def test_store_manager_manages_only_own_store_staff(client, admin_staff, make_staff, login):
    """数据范围落在员工管理上：店长管得了本店员工，管不了别店和总部账号"""
    login('admin', 'Admin123!')
    s1, s2 = _two_stores(client)
    # 别家店的员工 + 一个总部账号
    other_staff = client.post('/api/staff', json={
        'username': 'bieshia', 'real_name': '别家店员工',
        'email': 'bieshia@example.com', 'mobile': '13911110001',
        'password': 'Passw0rd!', 'store_id': s2['id'],
    }).get_json()['data']
    hq_staff = client.post('/api/staff', json={
        'username': 'zongbu', 'real_name': '总部账号',
        'email': 'zongbu@example.com', 'mobile': '13911110002',
        'password': 'Passw0rd!', 'store_id': None,
    }).get_json()['data']
    client.post('/api/auth/logout')

    make_staff('dianzhang', 'store_manager', store_id=s1['id'])
    login('dianzhang', 'Passw0rd!')

    # 列表里只有本店员工：admin（无门店）和总部账号都看不到
    body = client.get('/api/staff').get_json()['data']
    assert [s['username'] for s in body['staff']] == ['dianzhang']

    # 改不了别家店的员工，也改不了总部账号
    assert client.put(f'/api/staff/{other_staff["id"]}', json={'real_name': '改名'}).status_code == 403
    assert client.put(f'/api/staff/{hq_staff["id"]}', json={'real_name': '改名'}).status_code == 403

    # 建不了别家店的员工，也建不了总部账号
    assert client.post('/api/staff', json={
        'username': 'xinren', 'real_name': '新人', 'email': 'xinren@example.com',
        'mobile': '13911110003', 'password': 'Passw0rd!', 'store_id': s2['id'],
    }).status_code == 403
    assert client.post('/api/staff', json={
        'username': 'zongbu2', 'real_name': '总部新人', 'email': 'zongbu2@example.com',
        'mobile': '13911110004', 'password': 'Passw0rd!', 'store_id': None,
    }).status_code == 403


def test_audit_requires_permission(client, admin_staff, make_staff, login):
    """审计日志是老板专属（audit:view），店长看不了"""
    login('admin', 'Admin123!')
    s1, _s2 = _two_stores(client)
    client.post('/api/auth/logout')

    make_staff('dianzhang', 'store_manager', store_id=s1['id'])
    login('dianzhang', 'Passw0rd!')

    resp = client.get('/api/audit')
    assert resp.status_code == 403
    assert '审计日志' in resp.get_json()['message']


def test_role_change_takes_effect_immediately(client, admin_staff, make_staff, login):
    """给员工分配角色后，权限立刻生效——判权每次都查角色，不缓存"""
    login('admin', 'Admin123!')
    s1, _s2 = _two_stores(client)

    # 先建一个没有任何角色的收银员
    cashier = client.post('/api/staff', json={
        'username': 'shouyin', 'real_name': '收银员',
        'email': 'shouyin@example.com', 'mobile': '13911110005',
        'password': 'Passw0rd!', 'store_id': s1['id'],
    }).get_json()['data']
    assert cashier['roles'] == []

    # 管理员把「收银员」角色分配给他
    roles = client.get('/api/roles').get_json()['data']['roles']
    cashier_role = next(r for r in roles if r['code'] == 'cashier')
    resp = client.put(f'/api/staff/{cashier["id"]}', json={'role_ids': [cashier_role['id']]})
    assert resp.status_code == 200
    assert resp.get_json()['data']['roles'][0]['name'] == '收银员'

    client.post('/api/auth/logout')
    login('shouyin', 'Passw0rd!')

    # 收银员有 order:create 等交易权限，但没有 store:view
    assert client.get('/api/stores').status_code == 403
    assert client.get('/api/staff').status_code == 403


def test_login_returns_permissions_and_scope(client, make_staff, login):
    """登录返回权限码和数据范围，前端靠它决定显示哪些菜单"""
    make_staff('dianzhang', 'store_manager', store_id=None)
    resp = login('dianzhang', 'Passw0rd!')
    data = resp.get_json()['data']

    assert data['data_scope'] == 'store'
    assert 'dish:price:edit' in data['permissions']
    assert 'store:manage' not in data['permissions']


def test_superuser_bypasses_permission_checks(client, admin_staff, login):
    """is_admin 是旁路：绕过所有权限码检查（只留给初始管理员账号）

    顺带验证 /index 也返回登录态和权限——前端页面刷新后靠它同步最新权限。
    """
    login('admin', 'Admin123!')
    data = client.get('/index').get_json()['data']

    assert data['data_scope'] == 'all'
    assert 'system:config' in data['permissions']   # 连没人分配过的权限也有
    assert data['staff']['is_admin'] is True


def test_index_returns_same_session_shape_as_login(client, make_staff, login):
    """/index 和登录接口返回同一份登录态结构，前端刷新时能直接覆盖"""
    make_staff('dianzhang', 'store_manager', store_id=None)

    login_data = login('dianzhang', 'Passw0rd!').get_json()['data']
    index_data = client.get('/index').get_json()['data']

    assert index_data['staff'] == login_data['staff']
    assert index_data['permissions'] == login_data['permissions']
    assert index_data['data_scope'] == login_data['data_scope']
