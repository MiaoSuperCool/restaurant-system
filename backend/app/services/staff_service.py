from flask_login import current_user

from backend.app.errors import BusinessError, NotFoundError
from backend.app.extensions import db
from backend.app.models import Role, Staff, Store
from backend.app.services.audit_service import AuditService

RESOURCE = 'staff'


class StaffService:
    @staticmethod
    def get_all_staff():
        return Staff.query.all()

    @staticmethod
    def get_all_count():
        return Staff.query.count()

    @staticmethod
    def get_staff_by_id(staff_id):
        return db.session.get(Staff, staff_id)

    @staticmethod
    def get_staff_by_username(username):
        return Staff.query.filter_by(username=username).first()

    @staticmethod
    def get_paginated_staff(page=1, per_page=10, search=None, store_ids=None):
        query = Staff.query

        # 数据范围：店长只看到本店员工。store_id 为 NULL 的总部账号
        # 天然落在 in_() 之外，所以店长也看不到总部账号，符合设计文档。
        if store_ids is not None:
            query = query.filter(Staff.store_id.in_(store_ids))

        if search:
            query = query.filter(
                db.or_(
                    Staff.username.ilike(f'%{search}%'),
                    Staff.real_name.ilike(f'%{search}%'),
                    Staff.email.ilike(f'%{search}%'),
                    Staff.mobile.ilike(f'%{search}%'),
                )
            )

        return (query
                .order_by(Staff.id)
                .paginate(page=page, per_page=per_page, error_out=False))

    @staticmethod
    def _assert_store_exists(store_id):
        """归属门店必须真实存在；传 None 表示总部账号（运营/财务/老板），允许"""
        if store_id is None:
            return
        if not db.session.get(Store, store_id):
            raise NotFoundError(f'归属门店不存在（store_id={store_id}）')

    @staticmethod
    def assert_can_manage(store_id):
        """数据范围检查：本店范围的店长只能管本店员工

        store_id 传 None 表示总部账号——本店范围的角色管不了，会走到 403。
        权限码（staff:manage / staff:manage:all）管的是「能不能管员工」，
        这里管的是「能管哪家店的员工」。
        """
        allowed = current_user.accessible_store_ids()
        if allowed is not None and store_id not in allowed:
            raise BusinessError('无权管理其他门店的员工', status_code=403)

    @staticmethod
    def _resolve_roles(role_ids):
        """把 role_ids 解析成 Role 对象列表；有不存在的 id 直接报 404，不静默忽略

        resolve 这个词在编程里基本都是这个意思——把一种引用变成实际的东西，
        域名解析成 IP、路径解析成绝对路径、id 解析成实体。
        """
        if not role_ids:
            return []
        roles = Role.query.filter(Role.id.in_(role_ids)).all()
        missing = set(role_ids) - {role.id for role in roles}
        if missing:
            raise NotFoundError(f'角色不存在（role_id={sorted(missing)}）')
        return roles

    @staticmethod
    def _assert_unique(staff_id, field, value):
        """检查 username/email/mobile 是否与他人重复；staff_id 为 None 表示新建"""
        if value is None:
            return
        existing = Staff.query.filter_by(**{field: value}).first()
        if existing and existing.id != staff_id:
            raise BusinessError(f'{Staff.FIELD_LABELS[field]} {value} 已存在')

    @staticmethod
    def create_staff(data):
        try:
            for field in ('username', 'email', 'mobile'):
                StaffService._assert_unique(None, field, data.get(field))

            password = data.get('password') or ''
            if len(password) < 6:
                raise BusinessError('密码不能少于6位')

            StaffService._assert_store_exists(data.get('store_id'))
            StaffService.assert_can_manage(data.get('store_id'))
            roles = StaffService._resolve_roles(data.get('role_ids'))

            staff = Staff(
                username=data['username'],
                real_name=data['real_name'],
                email=data['email'],
                mobile=data['mobile'],
                store_id=data.get('store_id'),
                employment_type=data['employment_type'],
                is_shared=data['is_shared'],
                is_active=data['is_active'],
                is_admin=data['is_admin'],
            )
            staff.set_password(password)
            staff.roles = roles

            db.session.add(staff)
            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='CREATE_STAFF',
                resource=RESOURCE,
                status='success',
                new_value=staff.to_dict(),
            )

            return staff
        except Exception:
            db.session.rollback()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='CREATE_STAFF',
                resource=RESOURCE,
                status='failed',
            )

            raise

    @staticmethod
    def update_staff(staff_id, data):
        try:
            staff = StaffService.get_staff_by_id(staff_id)
            if not staff:
                raise NotFoundError('员工不存在')

            StaffService.assert_can_manage(staff.store_id)

            # 先留一份改动前的快照，审计日志要记变动前后值
            old_value = staff.to_dict()

            for field in ('username', 'email', 'mobile'):
                if field in data and data[field] != getattr(staff, field):
                    StaffService._assert_unique(staff_id, field, data[field])
                    setattr(staff, field, data[field])

            if 'real_name' in data and data['real_name'] != staff.real_name:
                staff.real_name = data['real_name']

            if 'store_id' in data and data['store_id'] != staff.store_id:
                StaffService._assert_store_exists(data['store_id'])
                # 调岗也要守住范围：本店范围的店长不能把人挪到别店，也不能挪成总部账号
                StaffService.assert_can_manage(data['store_id'])
                staff.store_id = data['store_id']

            if 'role_ids' in data:
                staff.roles = StaffService._resolve_roles(data['role_ids'])

            password = data.get('password') or ''
            if password:
                if len(password) < 6:
                    raise BusinessError('密码不能少于6位')
                staff.set_password(password)
                # 改密码 = 把这个人手里所有旧 token 作废。
                # 「改密码」这个动作本身就是在说「之前那些凭据不算数了」，
                # 不跟着踢 token 的话，改了密码等于没改（旧 token 还能用到过期）
                staff.token_version = (staff.token_version or 0) + 1

            for field in ('employment_type', 'is_shared', 'is_active', 'is_admin'):
                if field in data:
                    setattr(staff, field, data[field])

            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='UPDATE_STAFF',
                resource=RESOURCE,
                status='success',
                old_value=old_value,
                new_value=staff.to_dict(),
            )

            return staff

        except Exception:
            db.session.rollback()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='UPDATE_STAFF',
                resource=RESOURCE,
                status='failed',
            )

            raise

    @staticmethod
    def delete_staff(staff_id):
        try:
            staff = StaffService.get_staff_by_id(staff_id)
            if not staff:
                raise NotFoundError('员工不存在')

            if staff.id == current_user.id:
                raise BusinessError('不能删除自己的账号')

            StaffService.assert_can_manage(staff.store_id)

            old_value = staff.to_dict()

            db.session.delete(staff)
            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='DELETE_STAFF',
                resource=RESOURCE,
                status='success',
                old_value=old_value,
            )

            return True
        except Exception:
            db.session.rollback()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='DELETE_STAFF',
                resource=RESOURCE,
                status='failed',
            )

            raise
