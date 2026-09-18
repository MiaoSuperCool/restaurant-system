"""排班

盯四件事：

1. **班次**——同名的不许加、排过班的删不掉（只能停用）
2. **排班**——「一天两个班」是合法的（两头班），传空数组 = 那天不排
3. **周一**——不管拿哪一天去问，折出来的都是同一个周一到周日
4. **数据范围**——店长改 URL 里的 store_id 能不能排别家的人
"""
from datetime import date, timedelta

from backend.app.extensions import db
from backend.app.models import ShiftAssignment, ShiftTemplate, Staff


def _store(client, code='S001', name='解放路店'):
    return client.post('/api/stores', json={'code': code, 'name': name}).get_json()['data']


def _shift(client, store_id, name='早班', start='09:00', end='14:00', **extra):
    return client.post(f'/api/schedule/stores/{store_id}/shifts',
                       json={'name': name, 'start_time': start, 'end_time': end, **extra}
                       ).get_json()['data']


def _week(client, store_id, day=None):
    params = {'day': day} if day else {}
    return client.get(f'/api/schedule/stores/{store_id}/week', query_string=params).get_json()['data']


def _set_day(client, store_id, staff_id, work_date, shift_ids):
    return client.put(f'/api/schedule/stores/{store_id}/assignments', json={
        'staff_id': staff_id, 'work_date': work_date.isoformat(), 'shift_ids': shift_ids,
    })


# ---------- 班次 ----------

def test_create_shift(client, admin_staff, login):
    """建班次：名字、起止时间、默认启用"""
    login('admin', 'Admin123!')
    store = _store(client)

    shift = _shift(client, store['id'])

    assert shift['name'] == '早班'
    assert shift['start_time'] == '09:00'
    assert shift['end_time'] == '14:00'
    assert shift['time_range'] == '09:00-14:00'
    assert shift['is_active'] is True


def test_duplicate_shift_name_rejected(client, admin_staff, login):
    """同一家店两个「早班」→ 拒绝

    排班的下拉里出现两个同名班次，选哪个全靠猜（数据库上也有唯一约束兜着）。
    """
    login('admin', 'Admin123!')
    store = _store(client)
    _shift(client, store['id'])

    resp = client.post(f'/api/schedule/stores/{store["id"]}/shifts',
                       json={'name': '早班', 'start_time': '10:00', 'end_time': '15:00'})

    assert resp.status_code == 400
    assert '早班' in resp.get_json()['message']


def test_same_name_in_another_store_is_fine(client, admin_staff, login):
    """**同名班次在另一家店是合法的**——班次是门店级的

    西溪印象城店 10:30 才开门，它的「早班」和解放路店的不是一回事。
    """
    login('admin', 'Admin123!')
    first = _store(client, 'S001', '解放路店')
    second = _store(client, 'S002', '武林门店')

    _shift(client, first['id'])
    shift = _shift(client, second['id'], start='10:30', end='15:30')

    assert shift['store_id'] == second['id']
    assert shift['time_range'] == '10:30-15:30'


def test_shift_end_before_start_rejected(client, admin_staff, login):
    """结束时间早于开始时间 → 拒绝（跨天的班拆成两条）"""
    login('admin', 'Admin123!')
    store = _store(client)

    resp = client.post(f'/api/schedule/stores/{store["id"]}/shifts',
                       json={'name': '夜班', 'start_time': '22:00', 'end_time': '02:00'})

    assert resp.status_code == 400
    assert '结束时间' in resp.get_json()['message']


def test_delete_shift_blocked_when_scheduled(app, client, admin_staff, login, make_staff):
    """排过班的班次删不掉——挂着的排班记录会变成没头没尾的东西"""
    login('admin', 'Admin123!')
    store = _store(client)
    shift = _shift(client, store['id'])
    staff = make_staff('xiaowang', 'waiter', store_id=store['id'])
    _set_day(client, store['id'], staff.id, date.today(), [shift['id']])

    resp = client.delete(f'/api/schedule/shifts/{shift["id"]}')

    assert resp.status_code == 400
    assert '停用' in resp.get_json()['message']
    with app.app_context():
        assert db.session.get(ShiftTemplate, shift['id']) is not None


def test_delete_unused_shift(client, admin_staff, login):
    """没排过班的可以删"""
    login('admin', 'Admin123!')
    store = _store(client)
    shift = _shift(client, store['id'])

    assert client.delete(f'/api/schedule/shifts/{shift["id"]}').status_code == 200
    assert client.get(f'/api/schedule/stores/{store["id"]}/shifts'
                      ).get_json()['data']['shifts'] == []


def test_inactive_shift_stays_out_of_the_grid(app, client, admin_staff, login):
    """停用只停「以后不再排」：配置列表里还在，排班的下拉里没了"""
    login('admin', 'Admin123!')
    store = _store(client)
    shift = _shift(client, store['id'])
    client.put(f'/api/schedule/shifts/{shift["id"]}', json={'is_active': False})

    listed = client.get(f'/api/schedule/stores/{store["id"]}/shifts').get_json()['data']['shifts']
    assert [s['is_active'] for s in listed] == [False]

    week = _week(client, store['id'])
    assert week['shifts'] == []


# ---------- 一周的格子 ----------

def test_week_snaps_to_monday(client, admin_staff, login):
    """拿这一周里的**任意一天**去问，折出来都是同一个周一到周日

    前端翻页时直接问「上一周某一天」，不用自己算周一。
    """
    login('admin', 'Admin123!')
    store = _store(client)
    wednesday = date(2026, 9, 16)          # 周三
    monday = wednesday - timedelta(days=2)

    week = _week(client, store['id'], wednesday.isoformat())

    assert week['start'] == monday.isoformat()
    assert week['end'] == (monday + timedelta(days=6)).isoformat()
    assert len(week['days']) == 7
    assert [d['weekday'] for d in week['days']] == [
        '周一', '周二', '周三', '周四', '周五', '周六', '周日']


def test_assignments_line_up_with_days(app, client, admin_staff, login, make_staff):
    """格子里的数组和 `days` **按下标一一对应**

    前端直接 `row.assignments[dayIndex]` 就能渲染。错位一天的话，
    排的班全都显示在前一天上，而且看起来完全不像 bug。
    """
    login('admin', 'Admin123!')
    store = _store(client)
    morning = _shift(client, store['id'], '早班', '09:00', '14:00')
    evening = _shift(client, store['id'], '晚班', '16:00', '21:00')
    staff = make_staff('xiaowang', 'waiter', store_id=store['id'])

    wednesday = date(2026, 9, 16)
    tuesday = date(2026, 9, 15)
    _set_day(client, store['id'], staff.id, tuesday, [morning['id']])
    _set_day(client, store['id'], staff.id, wednesday, [morning['id'], evening['id']])

    week = _week(client, store['id'], wednesday.isoformat())
    row = week['rows'][0]

    assert [d['date'] for d in week['days']][1] == tuesday.isoformat()
    assert [a['shift_name'] for a in row['assignments'][1]] == ['早班']
    assert [a['shift_name'] for a in row['assignments'][2]] == ['早班', '晚班']
    assert row['assignments'][0] == []      # 周一没排


def test_week_only_lists_active_staff_of_this_store(client, admin_staff, login, make_staff):
    """班表里只有本店的在职员工——别的店的人、停用的账号都不该出现"""
    login('admin', 'Admin123!')
    first = _store(client, 'S001', '解放路店')
    second = _store(client, 'S002', '武林门店')
    make_staff('zaizhi', 'waiter', store_id=first['id'])
    make_staff('lidian', 'waiter', store_id=second['id'])
    make_staff('lizhi', 'waiter', store_id=first['id'], is_active=False)

    week = _week(client, first['id'])

    assert [row['staff_name'] for row in week['rows']] == ['zaizhi']


# ---------- 排班 ----------

def test_two_shifts_in_one_day(app, client, admin_staff, login, make_staff):
    """**一天两个班是合法的**——餐饮里的「两头班」

    早上来备菜、中午歇、晚上再来。拦掉的话店长只能记假数据。
    """
    login('admin', 'Admin123!')
    store = _store(client)
    morning = _shift(client, store['id'], '早班', '09:00', '14:00')
    evening = _shift(client, store['id'], '晚班', '16:00', '21:00')
    staff = make_staff('xiaowang', 'waiter', store_id=store['id'])

    resp = _set_day(client, store['id'], staff.id, date.today(),
                    [morning['id'], evening['id']])

    assert resp.status_code == 200
    assert len(resp.get_json()['data']['assignments']) == 2
    with app.app_context():
        assert ShiftAssignment.query.filter_by(staff_id=staff.id).count() == 2


def test_set_day_is_idempotent(app, client, admin_staff, login, make_staff):
    """同样的内容再点一次**不产生新记录**

    按 id 对齐而不是全删重建：重建会换掉记录 id，而排班记录将来要挂
    「这天实际出勤了没有」之类的东西，id 一变那些就全断了。
    """
    login('admin', 'Admin123!')
    store = _store(client)
    shift = _shift(client, store['id'])
    staff = make_staff('xiaowang', 'waiter', store_id=store['id'])
    today = date.today()

    first = _set_day(client, store['id'], staff.id, today, [shift['id']])
    second = _set_day(client, store['id'], staff.id, today, [shift['id']])

    assert (first.get_json()['data']['assignments'][0]['id']
            == second.get_json()['data']['assignments'][0]['id'])
    with app.app_context():
        assert ShiftAssignment.query.filter_by(staff_id=staff.id).count() == 1


def test_removing_one_shift_keeps_the_other(app, client, admin_staff, login, make_staff):
    """两个班去掉一个，**另一个的记录 id 不变**（这也是按 id 对齐的意义）"""
    login('admin', 'Admin123!')
    store = _store(client)
    morning = _shift(client, store['id'], '早班', '09:00', '14:00')
    evening = _shift(client, store['id'], '晚班', '16:00', '21:00')
    staff = make_staff('xiaowang', 'waiter', store_id=store['id'])
    today = date.today()
    _set_day(client, store['id'], staff.id, today, [morning['id'], evening['id']])

    with app.app_context():
        kept = ShiftAssignment.query.filter_by(
            staff_id=staff.id, shift_id=morning['id']).one().id

    result = _set_day(client, store['id'], staff.id, today, [morning['id']])

    assignments = result.get_json()['data']['assignments']
    assert [a['shift_name'] for a in assignments] == ['早班']
    assert assignments[0]['id'] == kept


def test_empty_list_clears_the_day(app, client, admin_staff, login, make_staff):
    """传空数组 = 那天休息"""
    login('admin', 'Admin123!')
    store = _store(client)
    shift = _shift(client, store['id'])
    staff = make_staff('xiaowang', 'waiter', store_id=store['id'])
    today = date.today()
    _set_day(client, store['id'], staff.id, today, [shift['id']])

    result = _set_day(client, store['id'], staff.id, today, [])

    assert result.get_json()['data']['assignments'] == []
    with app.app_context():
        assert ShiftAssignment.query.filter_by(staff_id=staff.id).count() == 0


def test_cannot_schedule_staff_from_another_store(client, admin_staff, login, make_staff):
    """**不能把别家的人排到自己店里**——跨店借调是另一个功能"""
    login('admin', 'Admin123!')
    first = _store(client, 'S001', '解放路店')
    second = _store(client, 'S002', '武林门店')
    shift = _shift(client, first['id'])
    outsider = make_staff('bieshide', 'waiter', store_id=second['id'])

    resp = _set_day(client, first['id'], outsider.id, date.today(), [shift['id']])

    assert resp.status_code == 400
    assert '不属于这家店' in resp.get_json()['message']


def test_shared_account_stays_out_of_the_schedule(client, admin_staff, login, make_staff):
    """**公用账号不进班表**——那台设备背后不是一个具体的人

    「前厅公用账号」是服务员共用的那台收银机，谁当班不是它当班。
    列表里显示它、或者能给它排班，都是把设备当成人在管。
    """
    login('admin', 'Admin123!')
    store = _store(client)
    shift = _shift(client, store['id'])
    make_staff('xiaowang', 'waiter', store_id=store['id'])
    device = make_staff('gongyong', 'waiter', store_id=store['id'], is_shared=True)

    week = _week(client, store['id'])
    assert [row['staff_name'] for row in week['rows']] == ['xiaowang']

    resp = _set_day(client, store['id'], device.id, date.today(), [shift['id']])
    assert resp.status_code == 400
    assert '公用账号' in resp.get_json()['message']


def test_cannot_schedule_a_shift_from_another_store(client, admin_staff, login, make_staff):
    """也不能拿别家的班次往自己店里排"""
    login('admin', 'Admin123!')
    first = _store(client, 'S001', '解放路店')
    second = _store(client, 'S002', '武林门店')
    foreign_shift = _shift(client, second['id'], '西溪早班', '10:30', '15:30')
    staff = make_staff('xiaowang', 'waiter', store_id=first['id'])

    resp = _set_day(client, first['id'], staff.id, date.today(), [foreign_shift['id']])

    assert resp.status_code == 400


# ---------- 数据范围与权限 ----------

def test_store_manager_cannot_schedule_another_store(client, make_staff, login, admin_staff):
    """店长改 URL 里的 store_id 去排别家的班 → 403

    这是这一块唯一的漏洞口子，堵不上就等于没有数据范围。
    """
    login('admin', 'Admin123!')
    mine = _store(client, 'S001', '解放路店')
    other = _store(client, 'S002', '武林门店')
    _shift(client, mine['id'])
    make_staff('dianzhang', 'store_manager', store_id=mine['id'])

    login('dianzhang', 'Passw0rd!')
    assert client.get(f'/api/schedule/stores/{other["id"]}/week').status_code == 403
    assert client.post(f'/api/schedule/stores/{other["id"]}/shifts',
                       json={'name': '早班', 'start_time': '09:00', 'end_time': '14:00'}
                       ).status_code == 403


def test_store_list_does_not_need_store_view(client, make_staff, login, admin_staff):
    """排班页的门店下拉**不能要求 store:view**

    服务员只有 `schedule:view`，没有 `store:view`——走 `/api/stores/options`
    的话他打开排班页会弹「没有门店查看权限」，而页面本身他是该能进的。
    """
    login('admin', 'Admin123!')
    store = _store(client)
    make_staff('xiaowang', 'waiter', store_id=store['id'])

    login('xiaowang', 'Passw0rd!')
    assert client.get('/api/stores/options').status_code == 403      # 这就是不能用它的原因
    data = client.get('/api/schedule/stores').get_json()['data']
    assert [s['id'] for s in data['stores']] == [store['id']]


def test_store_list_is_scoped(client, make_staff, login, admin_staff):
    """门店下拉也按数据范围收窄：店长只看到自己那家"""
    login('admin', 'Admin123!')
    mine = _store(client, 'S001', '解放路店')
    _store(client, 'S002', '武林门店')
    make_staff('dianzhang', 'store_manager', store_id=mine['id'])

    login('dianzhang', 'Passw0rd!')
    data = client.get('/api/schedule/stores').get_json()['data']
    assert [s['name'] for s in data['stores']] == ['解放路店']


def test_waiter_can_look_but_not_touch(client, make_staff, login, admin_staff):
    """服务员**能看班表**（得知道自己哪天来），但排不了班

    「看」和「排」是两个权限码：`schedule:view` / `schedule:manage`。
    """
    login('admin', 'Admin123!')
    store = _store(client)
    _shift(client, store['id'])
    waiter = make_staff('xiaowang', 'waiter', store_id=store['id'])

    login('xiaowang', 'Passw0rd!')
    assert client.get(f'/api/schedule/stores/{store["id"]}/week').status_code == 200
    assert _set_day(client, store['id'], waiter.id, date.today(), []).status_code == 403


def test_boss_has_both_view_and_manage(client, make_staff, login, admin_staff):
    """**老板两个码都有**——只有 manage 没有 view 的话，前端按 view 决定
    显不显示菜单，老板就看不到排班页（这个坑在报表那边踩过一次）"""
    login('admin', 'Admin123!')
    store = _store(client)
    make_staff('laoban', 'boss')

    login('laoban', 'Passw0rd!')
    assert client.get(f'/api/schedule/stores/{store["id"]}/week').status_code == 200
    assert client.get(f'/api/schedule/stores/{store["id"]}/shifts').status_code == 200


# ---------- 我的班表 ----------

def test_my_schedule(client, admin_staff, login, make_staff):
    """「我哪天上班」：只给有班的日子，今天/明天直接标好"""
    login('admin', 'Admin123!')
    store = _store(client)
    shift = _shift(client, store['id'])
    today = date.today()
    me = make_staff('xiaowang', 'waiter', store_id=store['id'])
    other = make_staff('xiaoli', 'waiter', store_id=store['id'])
    _set_day(client, store['id'], me.id, today, [shift['id']])
    _set_day(client, store['id'], me.id, today + timedelta(days=1), [shift['id']])
    _set_day(client, store['id'], other.id, today, [shift['id']])

    login('xiaowang', 'Passw0rd!')
    data = client.get('/api/schedule/me').get_json()['data']

    assert [d['relative'] for d in data['days']] == ['今天', '明天']
    assert data['total'] == 2
    assert data['days'][0]['shifts'][0]['shift_name'] == '早班'


def test_my_schedule_ignores_the_past(client, admin_staff, login, make_staff):
    """过去的班不返回——「我哪天上班」问的是往后"""
    login('admin', 'Admin123!')
    store = _store(client)
    shift = _shift(client, store['id'])
    me = make_staff('xiaowang', 'waiter', store_id=store['id'])
    _set_day(client, store['id'], me.id, date.today() - timedelta(days=3), [shift['id']])

    login('xiaowang', 'Passw0rd!')
    assert client.get('/api/schedule/me').get_json()['data']['total'] == 0


def test_staff_is_deleted_with_his_assignments(app, client, admin_staff, login, make_staff):
    """员工删了，**他的排班跟着走**（CASCADE）——排班是「给这个人排的」

    人没了这条记录没有任何意义。反过来说，班次是 RESTRICT：
    那条记录还有意义（「有人上过这个班」），所以删不掉。
    """
    login('admin', 'Admin123!')
    store = _store(client)
    shift = _shift(client, store['id'])
    staff = make_staff('xiaowang', 'waiter', store_id=store['id'])
    _set_day(client, store['id'], staff.id, date.today(), [shift['id']])

    with app.app_context():
        db.session.delete(db.session.get(Staff, staff.id))
        db.session.commit()
        assert ShiftAssignment.query.count() == 0
        assert db.session.get(ShiftTemplate, shift['id']) is not None
