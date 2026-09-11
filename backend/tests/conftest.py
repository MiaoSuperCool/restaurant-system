"""pytest 公共夹具：测试应用、客户端、测试用户"""
import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine

from backend.app import create_app
from backend.app.extensions import db
from backend.app.models import User


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


@pytest.fixture
def admin_user(app):
    """管理员账号：admin / Admin123!"""
    with app.app_context():
        user = User(
            username='admin',
            real_name='管理员',
            email='admin@example.com',
            mobile='13800138000',
            is_admin=True,
        )
        user.set_password('Admin123!')
        db.session.add(user)
        db.session.commit()
        # commit 后对象过期，refresh 一次让属性在脱离 session 后仍可读
        db.session.refresh(user)
        return user


@pytest.fixture
def normal_user(app):
    """普通员工账号：staff / Staff123!"""
    with app.app_context():
        user = User(
            username='staff',
            real_name='员工',
            email='staff@example.com',
            mobile='13800138001',
            is_admin=False,
        )
        user.set_password('Staff123!')
        db.session.add(user)
        db.session.commit()
        # commit 后对象过期，refresh 一次让属性在脱离 session 后仍可读
        db.session.refresh(user)
        return user


@pytest.fixture
def login(client):
    """登录辅助函数 fixture"""
    def _login(username, password):
        return client.post('/api/auth', json={'username': username, 'password': password})
    return _login
