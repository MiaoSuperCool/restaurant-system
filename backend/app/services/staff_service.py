from flask_login import current_user

from backend.app.errors import BusinessError, NotFoundError
from backend.app.extensions import db
from backend.app.models import Staff, Store
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
    def get_paginated_staff(page=1, per_page=10, search=None):
        query = Staff.query

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
                staff.store_id = data['store_id']

            password = data.get('password') or ''
            if password:
                if len(password) < 6:
                    raise BusinessError('密码不能少于6位')
                staff.set_password(password)

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
