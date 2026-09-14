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
    # 这家店还没建覆盖记录时，各字段的「当前值」是什么——和 StoreDish 列上的
    # 默认语义一致：没有行 = 没覆盖价（用基础价）、可售。
    # 提出来是因为下面判「值有没有变」要用，而默认值每个字段各不相同。
    FIELD_DEFAULTS = {
        'price': None,
        'is_available': True,
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
        # 顾客看不到下架的菜品但是店长可以看到，它们共用一套_query_menu逻辑，所以筛选是否下架
        # 这个步骤应该单独放到顾客端菜单这里

    @staticmethod
    def _query_menu(store_id, category_id=None, search=None):
        """按门店查菜单并合并本店覆盖——内部和顾客端共用的查询
        它的作用是从菜品表出发，砍掉不该出现的，按分类排好，再把这家店的
        覆盖值贴上去"""
        query = Dish.query.filter(Dish.status == Dish.STATUS_ACTIVE)
        # 第一步从菜品表出发，砍掉停售的，因为停售的不仅顾客不能看到，一家店的老板在点单页或门店菜单页也不应该看到
        # 但是在菜品页是可以看到的

        # 分类一级的两个开关都在这里生效，缺一个都会出现「界面上关了、
        # 菜单里还在卖」：
        #   - is_visible=False → 这个分类整个不上菜单（准备中/暂时下掉）
        #   - 适用门店：一行都没指定 = 全公司通用；指定了就只在这些店出现
        #     （比如「商务套餐」只在大店卖）
        #
        # 注意这对**内部和顾客端同时生效**——不是只管顾客那边。
        # 店长的菜单里也不该出现自家不卖的分类。
        query = query.join(Dish.category).filter(
            # 连上分类表以便下面使用分类字段过滤
            Category.is_visible.is_(True),
            db.or_(
                ~Category.stores.any(),
                Category.stores.any(Store.id == store_id),
                # 这里筛选的是要么这个分类没有绑定任何店铺（对所有店铺可见，~是取反的意思），要么它明确绑定了当前这个店铺
            ),
        )

        if category_id:
            query = query.filter(Dish.category_id == category_id)
        if search:
            query = query.filter(Dish.name.ilike(f'%{search}%'))

        # 下面要读每道菜的分类和规格组，不预加载的话是 N+1 查询
        # （50 道菜 = 100 次额外查询）。点单界面每次都要拉整份菜单，
        # 这里省下来的很实在。
        #
        # 排序先分类后菜品：顾客端的分类栏是从这份列表里「现推」的
        # （分类首次出现的位置就是它在分类栏里的位置，见 mp-customer 的
        # menu.vue），所以分类顺序必须在这里定死。只按 Dish.sort_order 排的话，
        # 运营在后台拖的 Category.sort_order 对顾客端毫无影响——分类栏的顺序
        # 会变成「哪个分类里有一道最靠前的菜」，跟运营看到的对不上。
        dishes = (query
                  .options(
                      joinedload(Dish.category),
                      selectinload(Dish.option_groups).selectinload(DishOptionGroup.options),
                  )
                  .order_by(Category.sort_order, Dish.sort_order, Dish.id)
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
        # 查「这家店对这道菜有没有做过特殊设置」——有就返回那条StoreDish，没有返回 None
        # upsert_override用它决定是新建还是原地改，delete_override用它决定有没有东西可删
        return StoreDish.query.filter_by(store_id=store_id, dish_id=dish_id).first()

    # ---------- 改 ----------

    @staticmethod
    def _assert_field_permissions(data, override):
        """改价、上下架要额外的权限码——和菜品基础那边同一套规则

        和 DishService._assert_field_permission 是一个思路：field 名单只从
        FIELD_PERMISSIONS 取，不另抄一份；权限码用下标取，不兜底。

        这个函数的作用是：检查「这次请求真正改动的字段，当前用户有没有权限改」，没有就抛 403
        先遍历 FIELD_PERMISSIONS 的 key，请求里没有这个字段则跳过，如果有，和旧值比较，如果和旧值一样也跳过
        价格的旧值要看**覆盖价**而不是菜品基础价——本店本来就没覆盖价时，
        传进来的 None 不算「改动」，这跟「传个和基础价一样的数字」是两回事。
        """
        for field in StoreDishService.FIELD_PERMISSIONS:
            if field not in data:
                continue

            old_value = (getattr(override, field) if override
                         else StoreDishService.FIELD_DEFAULTS[field])
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
    def _is_blank(override):
        """三个字段全是默认值——这行等于没设置过"""
        return (override.price is None
                and override.is_available
                and override.daily_limit is None)

    @staticmethod
    def upsert_override(store_id, dish_id, data):
        """设置某门店对某道菜的覆盖（没有记录就建一条）

        传 price=null 表示取消本店价格覆盖、改回菜品基础价；
        **价格填成和基础价一样也算**——「取消覆盖」和「覆盖成一个恰好相同的值」
        在界面上看不出区别，留着只会让人纳闷「我明明改回去了，怎么还划着横线」。

        上下架切回可售、限量清空同理。三样都回到默认值的话，这一行会被删掉——
        它已经不代表任何特殊设置了。
        """
        try:
            StoreDishService.get_store_or_404(store_id)
            StoreDishService.assert_in_scope(store_id)

            dish = db.session.get(Dish, dish_id)
            if not dish:
                raise NotFoundError('菜品不存在')

            override = StoreDishService.get_override(store_id, dish_id)

            # 「填成和基础价一样」翻译成「取消价格覆盖」，得赶在权限检查之前——
            # 这两件事算不算「改动」不一样：
            #   本店本来没覆盖、填了个和基础价一样的数 → 什么都没变，不该要权限
            #   本店覆盖成 38、现在改回基础价     → 真的改了，得要 dish:price:edit
            if data.get('price') is not None and data['price'] == dish.base_price:
                data = {**data, 'price': None}

            StoreDishService._assert_field_permissions(data, override)

            if override is None:
                # 一个字段都没传就不必建空记录——没有行本来就等于「用默认值」
                if not data:
                    return None
                # is_available 显式给默认值：列上的 default 要到 INSERT 时才应用，
                # 不然下面判「是不是全默认」的时候它还是个 None，读起来绕
                override = StoreDish(store_id=store_id, dish_id=dish_id, is_available=True)
                old_value = None
            else:
                old_value = override.to_dict()

            for field in ('price', 'is_available', 'daily_limit'):
                if field in data:
                    setattr(override, field, data[field])

            # 三样都回到默认值 = 这行等于没设置过。已经存在的删掉，刚建的干脆不存
            if StoreDishService._is_blank(override):
                if override.id is not None:
                    db.session.delete(override)
                override = None
            elif override.id is None:
                db.session.add(override)

            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='UPDATE_STORE_DISH',
                resource=RESOURCE,
                status='success',
                old_value=old_value,
                new_value=override.to_dict() if override else None,
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
        """清除本店覆盖，恢复成「用菜品基础价、可售、不限量」，也即是门店菜单那个恢复默认按钮的作用

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
