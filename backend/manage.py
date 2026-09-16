import os
import sys

import click
from flask.cli import FlaskGroup

# 把项目根目录放进 sys.path，这样 `python manage.py ...` 在 backend 目录下直接跑就行。
#
# 为什么 flask 命令不需要这句而这里需要：`flask run` 会自己从 wsgi.py 往上找，
# 发现 backend/ 是个包就把项目根插进 sys.path；而直接跑脚本没有这套机制，
# 不插的话 `from backend.app import ...` 会报 ModuleNotFoundError。
# 模板原来靠手动往 venv 的 site-packages 写 .pth 文件解决——换个环境就踩坑。
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Windows 控制台默认 GBK 编码，无法输出 emoji，统一转为 UTF-8
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except (AttributeError, ValueError):
    pass

from wsgi import app  # noqa: E402

from backend.app import create_app  # noqa: E402


def create_app_cli():
    return create_app(os.getenv('FLASK_ENV', 'development'))


@click.command(cls=FlaskGroup, create_app=create_app_cli)
def cli():
    """管理脚本入口"""
    pass


# 自定义命令：创建管理员
@cli.command('create-admin')
@click.option('--email', prompt='管理员邮箱',
              default=app.config.get('ADMIN_EMAIL', 'admin@example.com'))
@click.option('--password', prompt='管理员密码', hide_input=True,
              default=app.config.get('ADMIN_PASSWORD', 'Admin123!'))
@click.option('--username', prompt='管理员用户名',
              default=app.config.get('ADMIN_USERNAME', 'admin'))
@click.option('--name', prompt='管理员姓名', default='系统管理员')
@click.option('--mobile', prompt='管理员手机号', default='13800138000')
def create_admin(password, username, name, email, mobile):
    """创建超级管理员（is_admin=True，绕过权限码检查）"""
    from backend.app import db
    from backend.app.models.staff import Staff

    if Staff.query.filter_by(mobile=mobile).first():
        click.echo('❌ 手机号已存在')
        # click.echo输出的信息会显示在命令行（终端）里，它相比与print支持颜色，以及进度条显示
        return

    # 检查用户名是否已存在
    if Staff.query.filter_by(username=username).first():
        click.echo('❌ 用户名已存在')
        return

    staff = Staff(username=username,
                  real_name=name,
                  email=email,
                  mobile=mobile,
                  is_admin=True,
                  )
    staff.set_password(password)
    db.session.add(staff)
    db.session.commit()
    click.echo(f'✅ 管理员创建成功: {username}')


# 同步权限码与预置角色
@cli.command('seed-rbac')
def seed_rbac_command():
    """同步权限目录与预置角色（幂等，可反复执行）

    改了 backend/app/rbac.py 里的权限码或角色矩阵之后跑一次，
    新增的权限码会补进库，预置角色的权限会被改回设计文档定义的样子。

    注意：新建数据库后必须跑一次，否则所有角色都没有权限——
    只有 is_admin 的超级管理员账号能用。
    """
    from backend.app.rbac import seed_rbac

    created_permissions, created_roles, updated_roles = seed_rbac()
    click.echo(
        f'✅ 权限同步完成：新增权限 {created_permissions} 个，'
        f'新建角色 {created_roles} 个，更新角色 {updated_roles} 个'
    )


# 灌演示数据
@cli.command('seed-demo')
@click.option('--reset', is_flag=True, help='先清空已有的订单/支付数据再重建')
def seed_demo_command(reset):
    """灌演示数据：6 家门店、一套完整菜单、各角色账号、一批订单

    别人 clone 下来跑一遍这个，系统里就有东西可看了。

    幂等：门店/菜品/账号已存在就跳过，可以反复执行；
    订单每次都会新增，要重来一遍加 --reset。

    注意先后顺序：新建库要先 flask db upgrade → flask seed-rbac → 再灌演示数据。
    """
    if reset:
        click.confirm('⚠️ --reset 会删掉所有订单和支付记录，确定吗？', abort=True)

    from backend.app.demo import DEMO_PASSWORD, seed_demo

    stats = seed_demo(reset=reset)
    click.echo(
        f"✅ 演示数据就绪：门店 {stats['stores']}、分类 {stats['categories']}、"
        f"菜品 {stats['dishes']}、账号 {stats['staff']}、会员 {stats['members']}、"
        f"门店定价 {stats['overrides']}、券模板 {stats['coupon_templates']}、"
        f"发出的券 {stats['coupons']}、订单 {stats['orders']}、"
        f"支付 {stats['payments']}"
    )
    if stats['staff']:
        click.echo(f'   演示账号密码统一是 {DEMO_PASSWORD}')
        click.echo('   老板 laoban / 运营 yunying / 财务 caiwu / 店长 dianzhang')
        click.echo('   值班 zhiban / 收银 shouyin / 服务 fuwuyuan / 后厨 houcu')


# 重置数据库
@cli.command('reset-db')
@click.confirmation_option(prompt='⚠️ 确定要重置数据库吗？所有数据将被删除！')
def reset_db():
    """重置数据库（危险操作）"""
    from backend.app import db
    db.drop_all()
    db.create_all()
    click.echo('✅ 数据库已重置')


if __name__ == '__main__':
    cli()
