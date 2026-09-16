"""pytest 公共夹具：测试应用、客户端、测试员工账号、权限种子"""
import itertools
from contextlib import contextmanager

import pytest
from flask_login import login_user
from sqlalchemy import event
from sqlalchemy.engine import Engine

from backend.app import create_app
from backend.app.extensions import db
from backend.app.models import Staff


@pytest.fixture(scope='session', autouse=True)
def enable_sqlite_foreign_keys():
    """SQLite 默认不启用外键约束，这里全局打开（SET NULL 级联依赖它）"""
    @event.listens_for(Engine, 'connect')
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()


@pytest.fixture
def app():
    """测试应用：SQLite 内存库，每个用例独立建表/删表"""
    app = create_app('testing')
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def seed_roles(app):
    """每个用例都先把权限目录和预置角色灌进库

    自动执行：绝大多数用例都要用到角色（判权、数据范围），
    单独写夹具容易漏。种子本身幂等，重复跑没有副作用。
    """
    from backend.app.rbac import seed_rbac
    with app.app_context():
        seed_rbac()


@pytest.fixture
def make_staff(app):
    """按角色造员工的工厂：make_staff('laoban', role_code='store_manager', store_id=1)

    返回的对象脱离 app_context 后只能读已加载的属性（id/username 等），
    要用角色得在应用上下文里查。
    """
    _counter = itertools.count(1)

    def _make(username, role_code, store_id=None, password='Passw0rd!', **extra):
        from backend.app.models import Role, Staff
        with app.app_context():
            staff = Staff(
                username=username,
                real_name=extra.pop('real_name', username),
                email=extra.pop('email', f'{username}@example.com'),
                mobile=extra.pop('mobile', f'1390000{next(_counter):04d}'),
                store_id=store_id,
                **extra,
            )
            staff.set_password(password)
            role = Role.query.filter_by(code=role_code).first()
            assert role is not None, f'角色 {role_code} 不存在，检查 rbac.py'
            staff.roles = [role]
            db.session.add(staff)
            db.session.commit()
            db.session.refresh(staff)
            return staff
    return _make


@pytest.fixture
def admin_staff(app):
    """超级管理员账号：admin / Admin123!"""
    with app.app_context():
        staff = Staff(
            username='admin',
            real_name='管理员',
            email='admin@example.com',
            mobile='13800138000',
            is_admin=True,
        )
        staff.set_password('Admin123!')
        db.session.add(staff)
        db.session.commit()
        # commit 后对象过期，refresh 一次让属性在脱离 session 后仍可读
        db.session.refresh(staff)
        return staff


@pytest.fixture
def normal_staff(app):
    """普通员工账号：staff / Staff123!"""
    with app.app_context():
        staff = Staff(
            username='staff',
            real_name='员工',
            email='staff@example.com',
            mobile='13800138001',
            is_admin=False,
        )
        staff.set_password('Staff123!')
        db.session.add(staff)
        db.session.commit()
        # commit 后对象过期，refresh 一次让属性在脱离 session 后仍可读
        db.session.refresh(staff)
        return staff


@pytest.fixture
def login(client):
    """登录辅助函数 fixture"""
    def _login(username, password):
        return client.post('/api/auth', json={'username': username, 'password': password})
    return _login


@pytest.fixture
def as_admin(app, admin_staff):
    """在「已登录 admin」的请求上下文里执行一段代码

    用法：`with as_admin(): SomeService.do_something(...)`

    绝大多数测试走 HTTP 接口就够了。但有些 service 方法**暂时还没有接口**
    （比如余额扣款、积分抵扣——它们要等接进订单流程才有入口），核心逻辑不能
    等到那时候才测，就用这个夹具造出「已登录」的上下文直接调。

    service 里要读 `current_user`（记审计），所以必须有请求上下文 + 登录态。
    """
    @contextmanager
    def _ctx():
        with app.test_request_context():
            login_user(db.session.get(Staff, admin_staff.id))
            yield
    return _ctx
