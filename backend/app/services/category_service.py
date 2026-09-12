from flask_login import current_user
from sqlalchemy import func

from backend.app.errors import BusinessError, NotFoundError
from backend.app.extensions import db
from backend.app.models import Category, Store
from backend.app.services.audit_service import AuditService
from backend.app.utils.references import describe_references, find_referencing_rows

RESOURCE = 'category'


class CategoryService:
    @staticmethod
    def get_all_categories():
        return Category.query.order_by(Category.sort_order, Category.id).all()

    @staticmethod
    def get_category_by_id(category_id):
        return db.session.get(Category, category_id)

    @staticmethod
    def get_paginated_categories(page=1, per_page=10, search=None):
        query = Category.query
        if search:
            query = query.filter(Category.name.ilike(f'%{search}%'))
        return (query
                .order_by(Category.sort_order, Category.id)
                .paginate(page=page, per_page=per_page, error_out=False))

    @staticmethod
    def _next_sort_order():
        """新建的分类默认排在最后，运营再拖顺序"""
        current_max = db.session.query(func.max(Category.sort_order)).scalar()
        return (current_max or 0) + 1

    @staticmethod
    def _resolve_stores(store_ids):
        """门店适用范围：空列表 = 全公司通用（不是「哪家店都不显示」）

        「哪家店都不显示」用 is_visible=False 表达，那样更直白。
        """
        if not store_ids:
            return []
        stores = Store.query.filter(Store.id.in_(store_ids)).all()
        missing = set(store_ids) - {store.id for store in stores}
        if missing:
            raise NotFoundError(f'门店不存在（store_id={sorted(missing)}）')
        return stores

    @staticmethod
    def _assert_name_unique(category_id, name):
        existing = Category.query.filter_by(name=name).first()
        if existing and existing.id != category_id:
            raise BusinessError(f'分类「{name}」已存在')

    @staticmethod
    def create_category(data):
        try:
            CategoryService._assert_name_unique(None, data['name'])
            stores = CategoryService._resolve_stores(data.get('store_ids'))

            category = Category(
                name=data['name'],
                icon=data.get('icon', ''),
                is_visible=data['is_visible'],
                sort_order=(data.get('sort_order')
                            if data.get('sort_order') is not None
                            else CategoryService._next_sort_order()),
            )
            category.stores = stores

            db.session.add(category)
            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='CREATE_CATEGORY',
                resource=RESOURCE,
                status='success',
                new_value=category.to_dict(),
            )

            return category
        except Exception:
            db.session.rollback()
            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='CREATE_CATEGORY',
                resource=RESOURCE,
                status='failed',
            )
            raise

    @staticmethod
    def update_category(category_id, data):
        try:
            category = CategoryService.get_category_by_id(category_id)
            if not category:
                raise NotFoundError('分类不存在')

            old_value = category.to_dict()

            if 'name' in data and data['name'] != category.name:
                CategoryService._assert_name_unique(category_id, data['name'])
                category.name = data['name']

            for field in ('icon', 'is_visible', 'sort_order'):
                if field in data:
                    setattr(category, field, data[field])

            if 'store_ids' in data:
                category.stores = CategoryService._resolve_stores(data['store_ids'])

            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='UPDATE_CATEGORY',
                resource=RESOURCE,
                status='success',
                old_value=old_value,
                new_value=category.to_dict(),
            )

            return category
        except Exception:
            db.session.rollback()
            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='UPDATE_CATEGORY',
                resource=RESOURCE,
                status='failed',
            )
            raise

    @staticmethod
    def delete_category(category_id):
        try:
            category = CategoryService.get_category_by_id(category_id)
            if not category:
                raise NotFoundError('分类不存在')

            # 分类下面还有菜品就不能删，否则那些菜会变成没有分类的孤儿。
            # 先把菜品挪走或删掉，再删分类。
            references = find_referencing_rows(Category, category_id)
            if references:
                raise BusinessError(
                    f'分类「{category.name}」下面还有{describe_references(references)}，'
                    f'不能删除；请先把它们移到别的分类'
                )

            old_value = category.to_dict()

            db.session.delete(category)
            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='DELETE_CATEGORY',
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
                action='DELETE_CATEGORY',
                resource=RESOURCE,
                status='failed',
            )
            raise
