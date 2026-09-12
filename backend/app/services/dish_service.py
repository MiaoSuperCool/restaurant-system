from flask_login import current_user
from sqlalchemy import func

from backend.app.errors import BusinessError, NotFoundError
from backend.app.extensions import db
from backend.app.models import Category, Dish, DishOption, DishOptionGroup, Role
from backend.app.rbac import permission_name
from backend.app.services.audit_service import AuditService
from backend.app.utils.references import describe_references, find_referencing_rows

RESOURCE = 'dish'


class DishService:
    # 改这几个字段不只是「改菜品」，各自还有专门的权限码。
    # 设计文档把改价、上下架单独列出来，就是因为这两件事风险最高——
    # 门店里能改菜名的人，不一定该能改价格。
    FIELD_PERMISSIONS = {
        'base_price': 'dish:price:edit',
        'status': 'dish:online',
    }
    FIELD_LABELS = {
        'base_price': '价格',
        'status': '上下架状态',
    }

    # ---------- 查询 ----------

    @staticmethod
    def get_dish_by_id(dish_id):
        return db.session.get(Dish, dish_id)

    @staticmethod
    def get_paginated_dishes(page=1, per_page=10, search=None, category_id=None):
        query = Dish.query
        if category_id:
            query = query.filter(Dish.category_id == category_id)
        if search:
            query = query.filter(Dish.name.ilike(f'%{search}%'))
        return (query
                .order_by(Dish.sort_order, Dish.id)
                .paginate(page=page, per_page=per_page, error_out=False))

    @staticmethod
    def _next_sort_order():
        current_max = db.session.query(func.max(Dish.sort_order)).scalar()
        return (current_max or 0) + 1

    # ---------- 校验 ----------

    @staticmethod
    def _assert_company_scope(action):
        """菜品基础是全公司共用的数据，改它需要「全部」范围的角色

        各店的价格和上下架在「门店菜品」(store_dish) 里覆盖。
        店长的 menu:update 是针对本店的——改的是门店菜品，不是这里。
        """
        if current_user.data_scope != Role.SCOPE_ALL:
            raise BusinessError(
                f'菜品基础是全公司共用的数据，本店范围的账号不能{action}；'
                f'调整本店菜单请用「门店菜品」',
                status_code=403,
            )

    @staticmethod
    def _assert_field_permission(field, new_value, old_value):
        """改价、改上下架各有专门的权限码，不是有 menu:update 就能改"""
        if new_value == old_value:
            return
        code = DishService.FIELD_PERMISSIONS.get(field)
        if code and not current_user.has_permission(code):
            raise BusinessError(
                f'没有「{permission_name(code)}」权限，'
                f'不能改{DishService.FIELD_LABELS[field]}',
                status_code=403,
            )

    @staticmethod
    def _resolve_category(category_id):
        category = db.session.get(Category, category_id)
        if not category:
            raise NotFoundError(f'菜品分类不存在（category_id={category_id}）')
        return category

    # ---------- 规格组 / 选项 ----------

    @staticmethod
    def _sync_options(dish, groups_data):
        """按 id 对齐地更新规格结构：改的原地改、新的新增、没出现的删掉

        **不能「全删了重建」**：订单明细会引用选项 id，重建会让历史订单指到
        不存在的选项上，那样「加蛋卖了多少份」这类统计就断了。
        """
        original_groups = list(dish.option_groups)
        group_by_id = {group.id: group for group in original_groups}
        kept_group_ids = set()

        for group_index, group_data in enumerate(groups_data):
            group_id = group_data.get('id')
            if group_id is not None and group_id not in group_by_id:
                raise NotFoundError(f'规格组不存在（id={group_id}）')

            group = group_by_id.get(group_id)
            if group is None:
                group = DishOptionGroup()
                dish.option_groups.append(group)
            else:
                kept_group_ids.add(group.id)

            group.name = group_data['name']
            group.selection_type = group_data['selection_type']
            group.is_required = group_data['is_required']
            # 没显式给顺序就按提交上来的先后排——前端不传数字，靠数组顺序表达
            group.sort_order = (group_data.get('sort_order')
                                if group_data.get('sort_order') is not None
                                else group_index)

            original_options = list(group.options)
            option_by_id = {option.id: option for option in original_options}
            kept_option_ids = set()

            for option_index, option_data in enumerate(group_data['options']):
                option_id = option_data.get('id')
                if option_id is not None and option_id not in option_by_id:
                    raise NotFoundError(f'规格选项不存在（id={option_id}）')

                option = option_by_id.get(option_id)
                if option is None:
                    option = DishOption()
                    group.options.append(option)
                else:
                    kept_option_ids.add(option.id)

                option.name = option_data['name']
                option.extra_price = option_data['extra_price']
                option.sort_order = (option_data.get('sort_order')
                                     if option_data.get('sort_order') is not None
                                     else option_index)

            for option in original_options:
                if option.id not in kept_option_ids:
                    group.options.remove(option)

        for group in original_groups:
            if group.id not in kept_group_ids:
                dish.option_groups.remove(group)

    # ---------- 增删改 ----------

    @staticmethod
    def create_dish(data):
        try:
            DishService._assert_company_scope('新增菜品')

            category = DishService._resolve_category(data['category_id'])

            dish = Dish(
                category=category,
                name=data['name'],
                image=data.get('image', ''),
                description=data.get('description', ''),
                base_price=data['base_price'],
                status=data['status'],
                sort_order=(data.get('sort_order')
                            if data.get('sort_order') is not None
                            else DishService._next_sort_order()),
            )
            DishService._sync_options(dish, data.get('option_groups') or [])

            db.session.add(dish)
            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='CREATE_DISH',
                resource=RESOURCE,
                status='success',
                new_value=dish.to_dict(with_options=True),
            )

            return dish
        except Exception:
            db.session.rollback()
            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='CREATE_DISH',
                resource=RESOURCE,
                status='failed',
            )
            raise

    @staticmethod
    def update_dish(dish_id, data):
        try:
            dish = DishService.get_dish_by_id(dish_id)
            if not dish:
                raise NotFoundError('菜品不存在')

            DishService._assert_company_scope('修改菜品')

            old_value = dish.to_dict(with_options=True)

            if 'category_id' in data and data['category_id'] != dish.category_id:
                dish.category = DishService._resolve_category(data['category_id'])

            for field in ('name', 'image', 'description', 'sort_order'):
                if field in data:
                    setattr(dish, field, data[field])

            for field in ('base_price', 'status'):
                if field in data:
                    DishService._assert_field_permission(field, data[field], getattr(dish, field))
                    setattr(dish, field, data[field])

            if 'option_groups' in data:
                DishService._sync_options(dish, data['option_groups'])

            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='UPDATE_DISH',
                resource=RESOURCE,
                status='success',
                old_value=old_value,
                new_value=dish.to_dict(with_options=True),
            )

            return dish
        except Exception:
            db.session.rollback()
            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='UPDATE_DISH',
                resource=RESOURCE,
                status='failed',
            )
            raise

    @staticmethod
    def delete_dish(dish_id):
        try:
            dish = DishService.get_dish_by_id(dish_id)
            if not dish:
                raise NotFoundError('菜品不存在')

            DishService._assert_company_scope('删除菜品')

            # 还在门店菜单里挂着（或已经被订单引用）就不能删。
            # 只是不想卖了应该改 status 为「已停售」，历史订单还得认得这道菜。
            references = find_referencing_rows(Dish, dish_id)
            if references:
                raise BusinessError(
                    f'菜品「{dish.name}」还有{describe_references(references)}，不能删除；'
                    f'不想卖的话请把状态改为「已停售」'
                )

            old_value = dish.to_dict(with_options=True)

            db.session.delete(dish)
            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='DELETE_DISH',
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
                action='DELETE_DISH',
                resource=RESOURCE,
                status='failed',
            )
            raise
