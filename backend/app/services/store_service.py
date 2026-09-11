from flask_login import current_user

from backend.app.errors import BusinessError, NotFoundError
from backend.app.extensions import db
from backend.app.models import Store
from backend.app.services import AuditService

RESOURCE = 'store'


class StoreService:
    @staticmethod
    def get_all_stores():
        return Store.query.order_by(Store.code).all()

    @staticmethod
    def get_store_by_id(store_id):
        return db.session.get(Store, store_id)

    @staticmethod
    def get_paginated_stores(page=1, per_page=10, search=None):
        query = Store.query

        if search:
            query = query.filter(
                db.or_(
                    Store.code.ilike(f'%{search}%'),
                    Store.name.ilike(f'%{search}%'),
                    Store.address.ilike(f'%{search}%'),
                )
            )

        return (query
                .order_by(Store.code)
                .paginate(page=page, per_page=per_page, error_out=False))

    @staticmethod
    def create_store(data):
        try:
            if Store.query.filter_by(code=data.get('code')).first():
                raise BusinessError(f"门店编码 {data.get('code')} 已存在")

            if Store.query.filter_by(name=data.get('name')).first():
                raise BusinessError(f"门店名称 {data.get('name')} 已存在")

            store = Store(
                code=data['code'],
                name=data['name'],
                store_type=data['store_type'],
                address=data.get('address', ''),
                phone=data.get('phone', ''),
                business_status=data['business_status'],
                run_mode=data['run_mode'],
                remark=data.get('remark', ''),
            )

            db.session.add(store)
            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='CREATE_STORE',
                resource=RESOURCE,
                status='success',
                new_value=store.to_dict(),
            )

            return store
        except Exception:
            db.session.rollback()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='CREATE_STORE',
                resource=RESOURCE,
                status='failed',
            )

            raise

    @staticmethod
    def update_store(store_id, data):
        try:
            store = StoreService.get_store_by_id(store_id)
            if not store:
                raise NotFoundError('门店不存在')

            # 先留一份改动前的快照，审计日志要记变动前后值
            old_value = store.to_dict()

            if 'code' in data and data['code'] != store.code:
                if Store.query.filter_by(code=data['code']).first():
                    raise BusinessError(f"门店编码 {data['code']} 已存在")
                store.code = data['code']

            if 'name' in data and data['name'] != store.name:
                if Store.query.filter_by(name=data['name']).first():
                    raise BusinessError(f"门店名称 {data['name']} 已存在")
                store.name = data['name']

            for field in ('store_type', 'address', 'phone',
                          'business_status', 'run_mode', 'remark'):
                if field in data:
                    setattr(store, field, data[field])

            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='UPDATE_STORE',
                resource=RESOURCE,
                status='success',
                old_value=old_value,
                new_value=store.to_dict(),
            )

            return store

        except Exception:
            db.session.rollback()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='UPDATE_STORE',
                resource=RESOURCE,
                status='failed',
            )

            raise

    @staticmethod
    def delete_store(store_id):
        try:
            store = StoreService.get_store_by_id(store_id)
            if not store:
                raise NotFoundError('门店不存在')

            # 门店一旦挂上订单/员工/门店菜品就不能删，否则历史数据成孤儿。
            # 一期这些表还没建，等建好后在这里加引用检查，届时改用「已停业」软下架。
            old_value = store.to_dict()

            db.session.delete(store)
            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='DELETE_STORE',
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
                action='DELETE_STORE',
                resource=RESOURCE,
                status='failed',
            )

            raise
