from flask_login import current_user
from sqlalchemy.orm import joinedload, selectinload

from backend.app.errors import BusinessError, NotFoundError
from backend.app.extensions import db
from backend.app.models import Category, Dish, DishOptionGroup, Store, StoreDish
from backend.app.rbac import permission_name
from backend.app.services.audit_service import AuditService

RESOURCE = 'store_dish'


class StoreDishService:
    # 改这几个字段各自要额外的权限码，不是有 menu:update 就行。
    # 和 DishService 同一套思路：能改菜名的人不一定该能改价格。
    FIELD_PERMISSIONS = {
        'price': 'dish:price:edit',
        'is_available': 'dish:online',
    }
    FIELD_LABELS = {
        'price': '价格',
        'is_available': '上下架状态',
    }

    # ---------- 查询 ----------

    @staticmethod
    def get_store_or_404(store_id):
        store = db.session.get(Store, store_id)
        if not store:
            raise NotFoundError('门店不存在')
        return store

    @staticmethod
    def assert_in_scope(store_id):
        """数据范围：本店范围的角色只能碰自己门店的菜单"""
        allowed = current_user.accessible_store_ids()
        if allowed is not None and store_id not in allowed:
            raise BusinessError('无权操作其他门店的菜单', status_code=403)

    @staticmethod
    def get_menu(store_id, category_id=None, search=None):
        """某门店的完整菜单：每道在售菜品 + 本店的覆盖值

        返回的是「菜品基础 + 门店覆盖」合并后的结果——调用方不需要自己
        去判断 price 是不是 None，麻烦都在这里解决掉。
        """
        # 门店得存在，而且得在数据范围内——查询入口和写入口一样要守这两个检查，
        # 不然店长能拉到别家店的菜单（只是看，但价格和上下架本来就是敏感信息）
        StoreDishService.get_store_or_404(store_id)
        StoreDishService.assert_in_scope(store_id)
        return StoreDishService._query_menu(store_id, category_id, search)

    @staticmethod
    def get_public_menu(store_id):
        """顾客端看的菜单

        和内部菜单的区别：
        - **不查数据范围**：顾客本来就在店里，没有「能看哪些店」一说
        - **只看营业中的门店**：休息中/已停业的店点不了单，菜单也不该给
        - **过滤掉本店下架的菜**：收银台上摆着点不了的菜只是添乱，
          顾客端更不该出现

        算价和规格结构完全复用内部那套——菜单接口给的价就是下单用的价，
        不能有两套。
        """
        store = StoreDishService.get_store_or_404(store_id)
        if store.business_status != Store.STATUS_OPEN:
            raise BusinessError(
                f'「{store.name}」{store.STATUS_LABELS.get(store.business_status)}，暂时不接单'
            )
        return [row for row in StoreDishService._query_menu(store_id)
                if row['is_available']]

    @staticmethod
    def _query_menu(store_id, category_id=None, search=None):
        """按门店查菜单并合并本店覆盖——内部和顾客端共用的查询"""
        query = Dish.query.filter(Dish.status == Dish.STATUS_ACTIVE)

        # 分类的「适用门店」在这里生效：分类可以只在部分门店出现
        # （比如「商务套餐」只在大店卖）。
        # 一行都没指定 = 全公司通用；指定了就只在这些店的菜单里出现。
        #
        # 注意这对**内部和顾客端同时生效**——不是只管顾客那边。
        # 店长的菜单里也不该出现自家不卖的分类。
        query = query.join(Dish.category).filter(
            db.or_(
                ~Category.stores.any(),
                Category.stores.any(Store.id == store_id),
            )
        )

        if category_id:
            query = query.filter(Dish.category_id == category_id)
        if search:
            query = query.filter(Dish.name.ilike(f'%{search}%'))

        # 下面要读每道菜的分类和规格组，不预加载的话是 N+1 查询
        # （50 道菜 = 100 次额外查询）。点单界面每次都要拉整份菜单，
        # 这里省下来的很实在。
        dishes = (query
                  .options(
                      joinedload(Dish.category),
                      selectinload(Dish.option_groups).selectinload(DishOptionGroup.options),
                  )
                  .order_by(Dish.sort_order, Dish.id)
                  .all())

        # 一次把这家店的覆盖全查出来，避免每道菜查一次（N+1）
        overrides = {
            row.dish_id: row
            for row in StoreDish.query.filter_by(store_id=store_id).all()
        }

        return [StoreDishService._merge(dish, overrides.get(dish.id)) for dish in dishes]

    @staticmethod
    def _merge(dish, override):
        """菜品基础 + 本店覆盖 → 一行菜单"""
        return {
            'dish_id': dish.id,
            'name': dish.name,
            'image': dish.image,
            'description': dish.description,
            'category_id': dish.category_id,
            'category_name': dish.category.name if dish.category else None,
            'base_price': float(dish.base_price) if dish.base_price is not None else 0,
            # 本店实际售价
            'price': float(override.effective_price) if override else float(dish.base_price),
            'has_price_override': bool(override and override.has_price_override),
            'is_available': override.is_available if override else True,
            'daily_limit': override.daily_limit if override else None,
            # 给前端判断「是不是改过默认值」用，改过的行才显示「恢复默认」按钮
            'has_override': override is not None,
            # 规格组：点单界面要用它渲染规格选择器
            'option_groups': [group.to_dict() for group in dish.option_groups],
        }

    @staticmethod
    def get_override(store_id, dish_id):
        return StoreDish.query.filter_by(store_id=store_id, dish_id=dish_id).first()

    # ---------- 改 ----------

    @staticmethod
    def _assert_field_permissions(data, override):
        """价格的旧值要看覆盖价而不是菜品基础价——改回基础价也算改价"""
        for field in ('price', 'is_available'):
            if field not in data:
                continue
            if field == 'price':
                old_value = override.price if override else None
            else:
                old_value = override.is_available if override else True

            if data[field] == old_value:
                continue

            code = StoreDishService.FIELD_PERMISSIONS[field]
            if not current_user.has_permission(code):
                raise BusinessError(
                    f'没有「{permission_name(code)}」权限，'
                    f'不能改{StoreDishService.FIELD_LABELS[field]}',
                    status_code=403,
                )

    @staticmethod
    def upsert_override(store_id, dish_id, data):
        """设置某门店对某道菜的覆盖（没有记录就建一条）

        传 price=null 表示取消本店覆盖、改回菜品基础价。
        """
        try:
            StoreDishService.get_store_or_404(store_id)
            StoreDishService.assert_in_scope(store_id)

            dish = db.session.get(Dish, dish_id)
            if not dish:
                raise NotFoundError('菜品不存在')

            override = StoreDishService.get_override(store_id, dish_id)
            StoreDishService._assert_field_permissions(data, override)

            if override is None:
                # 一个字段都没传就不必建空记录——没有行本来就等于「用默认值」
                if not data:
                    return None
                override = StoreDish(store_id=store_id, dish_id=dish_id)
                db.session.add(override)
                old_value = None
            else:
                old_value = override.to_dict()

            for field in ('price', 'is_available', 'daily_limit'):
                if field in data:
                    setattr(override, field, data[field])

            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='UPDATE_STORE_DISH',
                resource=RESOURCE,
                status='success',
                old_value=old_value,
                new_value=override.to_dict(),
            )

            return override
        except Exception:
            db.session.rollback()
            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='UPDATE_STORE_DISH',
                resource=RESOURCE,
                status='failed',
            )
            raise

    @staticmethod
    def delete_override(store_id, dish_id):
        """清除本店覆盖，恢复成「用菜品基础价、可售、不限量」

        注意这是删除覆盖配置，不是删除菜品——菜品本身还在，只是这家店
        不再对它做特殊设置。
        """
        try:
            StoreDishService.get_store_or_404(store_id)
            StoreDishService.assert_in_scope(store_id)

            override = StoreDishService.get_override(store_id, dish_id)
            if not override:
                raise NotFoundError('这家门店对这道菜没有特殊设置')

            old_value = override.to_dict()

            db.session.delete(override)
            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='DELETE_STORE_DISH',
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
                action='DELETE_STORE_DISH',
                resource=RESOURCE,
                status='failed',
            )
            raise

    @staticmethod
    def get_categories_for_filter():
        """菜单页的分类筛选项"""
        return Category.query.order_by(Category.sort_order, Category.id).all()
