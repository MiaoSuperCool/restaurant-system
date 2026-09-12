from flask_login import current_user
from sqlalchemy import func

from backend.app.errors import BusinessError, NotFoundError
from backend.app.extensions import db
from backend.app.models import Store
from backend.app.services.audit_service import AuditService

RESOURCE = 'store'


class StoreService:
    @staticmethod
    def get_all_stores(store_ids=None):
        """store_ids 为 None 表示不限门店（全部范围）；列表则只返回其中的门店"""
        query = Store.query
        if store_ids is not None:
            query = query.filter(Store.id.in_(store_ids))
        return query.order_by(Store.code).all()

    @staticmethod
    def get_all_count():
        return Store.query.count()

    @staticmethod
    def assert_in_scope(store):
        """数据范围检查：本店范围的角色只能碰自己归属的门店

        门店管理接口（改/删）用得上。权限码管的「能不能管门店」，
        这里管的是「能管哪几家」。
        """
        allowed = current_user.accessible_store_ids()
        if allowed is not None and store.id not in allowed:
            raise BusinessError('无权操作其他门店的数据', status_code=403)

    @staticmethod
    def get_store_by_id(store_id):
        return db.session.get(Store, store_id)

    @staticmethod
    def get_paginated_stores(page=1, per_page=10, search=None, store_ids=None):
        query = Store.query

        # 数据范围：店长/值班经理只看得到自己那家店，运营主管和老板不限
        if store_ids is not None:
            query = query.filter(Store.id.in_(store_ids))

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

            StoreService.assert_in_scope(store)

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

    # 引用门店的表的友好名（拼进报错文案给用户看）。
    # 没登记的表的退回用表名——这样新表加进来不会漏检，只是文案还没那么好读。
    REFERENCE_LABELS = {
        'order': '订单',
        'order_item': '订单明细',
        'staff': '员工',
        'store_dish': '门店菜品',
        'store_inventory': '库存',
    }

    @staticmethod
    def get_blocking_references(store_id):
        """统计所有指向该门店的外键引用，返回 {引用对象: 行数}

        实现方式是扫描 SQLAlchemy metadata 里的全部外键，而不是手写一张检查清单：
        以后新建订单、员工、门店菜品等表时，只要它们带了指向 store.id 的外键，
        这里就自动覆盖，不需要回来改代码——手写清单迟早会漏。

        返回空 dict 表示没有任何业务数据引用它，可以安全物理删除。
        """
        references = {}
        for table in db.metadata.tables.values():
            store_columns = [
                fk.parent for fk in table.foreign_keys
                if fk.column.table.name == Store.__tablename__ and fk.column.name == 'id'
            ]
            if not store_columns:
                continue

            count = (db.session.query(func.count())
                     .select_from(table)
                     .filter(db.or_(*[column == store_id for column in store_columns]))
                     .scalar())
            if count:
                label = StoreService.REFERENCE_LABELS.get(table.name, table.name)
                references[label] = references.get(label, 0) + count
        return references

    @staticmethod
    def delete_store(store_id):
        try:
            store = StoreService.get_store_by_id(store_id)
            if not store:
                raise NotFoundError('门店不存在')

            StoreService.assert_in_scope(store)

            # 门店一旦挂上订单/员工/门店菜品就不能删，否则那些历史数据会变成
            # 找不到门店的孤儿，对账也就对不上了。这时正确的下线方式是
            # 把营业状态改成「已停业」（closed），而不是删记录。
            references = StoreService.get_blocking_references(store_id)
            if references:
                detail = '、'.join(
                    f'{name} {count} 条' for name, count in references.items()
                )
                raise BusinessError(
                    f'门店「{store.name}」还有业务数据（{detail}），不能删除；'
                    f'如需下线请把营业状态改为「已停业」'
                )

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
