import os
import sys

import click
from flask.cli import FlaskGroup

# Windows 控制台默认 GBK 编码，无法输出 emoji，统一转为 UTF-8
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except (AttributeError, ValueError):
    pass

from wsgi import app

from backend.app import create_app


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
