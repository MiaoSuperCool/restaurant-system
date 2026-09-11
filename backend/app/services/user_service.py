from flask_login import current_user

from backend.app import BusinessError
from backend.app.errors import NotFoundError
from backend.app.extensions import db
from backend.app.models import User
from backend.app.services import AuditService


class UserService:
    @staticmethod
    def get_all_users():
        return User.query.all()

    @staticmethod
    def get_all_count():
        return User.query.count()

    @staticmethod
    def get_user_by_id(user_id):
        return db.session.get(User, user_id)

    @staticmethod
    def get_user_by_username(username):
        return User.query.filter_by(username=username).first()

    @staticmethod
    def get_paginated_users(page=1, per_page=10, search=None):
        query = User.query

        if search:
            query = query.filter(
                db.or_(
                    User.username.like(f'%{search}%'),
                    User.real_name.like(f'%{search}%'),
                    User.email.like(f'%{search}%'),
                )
            )
        return query.paginate(page=page, per_page=per_page, error_out=False)

    # 创建用户功能============================
    @staticmethod
    def create_user(data):
        try:
            if User.query.filter_by(username=data.get('username')).first():
                raise BusinessError('用户名已存在')

            if User.query.filter_by(email=data.get('email')).first():
                raise BusinessError('邮箱已存在')

            if User.query.filter_by(mobile=data.get('mobile')).first():
                raise BusinessError('手机号已被使用')

            password = data.get('password')
            if len(password) < 6:
                raise BusinessError('密码不能少于6位')

            user = User(
                username=data.get('username'),
                real_name=data.get('real_name'),
                email=data.get('email'),
                mobile=data.get('mobile'),
                is_active=data.get('is_active', True),
                is_admin=data.get('is_admin', False)
            )
            user.set_password(password)

            db.session.add(user)
            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='CREATE_USER',
                status='success',
                new_value=user.to_dict()
            )

            return user
        except Exception:
            db.session.rollback()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='CREATE_USER',
                status='failed'
            )

            raise


    # 编辑角色========================================
    @staticmethod
    def update_user(user_id, data):
        try:
            user = UserService.get_user_by_id(user_id)
            if not user:
                raise NotFoundError('用户不存在')

            old_data = UserService.get_user_by_id(user_id)

            # 修改需要检测的字段
            if 'username' in data and data['username'] != user.username:
                if User.query.filter_by(username=data['username']).first():
                    raise BusinessError('用户名已存在')   # 原为静默跳过,现改为明确报错
                user.username = data['username']

            if 'email' in data and data['email'] != user.email:
                if User.query.filter_by(email=data['email']).first():
                    raise BusinessError('邮箱已存在')
                user.email = data['email']

            if 'mobile' in data and data['mobile'] != user.mobile:
                if User.query.filter_by(mobile=data['mobile']).first():
                    raise BusinessError('手机号已被使用')
                user.mobile = data['mobile']

            password = data.get('password','')
            if 'password' in data and password:
                if len(password) < 6:
                    raise BusinessError('密码不能少于6位')
                user.set_password(password)

            # 修改其他字段
            if 'real_name' in data and data['real_name'] != user.real_name:
                user.real_name = data['real_name']

            if 'is_active' in data:
                user.is_active = data['is_active']

            if 'is_admin' in data:
               user.is_admin = data['is_admin']

            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='UPDATE_USER',
                status='success',
                old_value=old_data.to_dict(),
                new_value=user.to_dict()
            )

            return user

        except Exception:
            db.session.rollback()
            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='UPDATE_USER',
                status='failed'
            )

            raise


    @staticmethod
    def delete_user(user_id):
        try:
            user = UserService.get_user_by_id(user_id)

            if not user:
                raise NotFoundError('用户不存在')

            if user.id == current_user.id:
                raise BusinessError('不能删除自己的账号')

            old_data = user.to_dict()

            db.session.delete(user)
            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='DELETE_USER',
                status='success',
                old_value=old_data
            )

            return True
        except Exception:
            db.session.rollback()
            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='DELETE_USER',
                status='failed'
            )
            raise




