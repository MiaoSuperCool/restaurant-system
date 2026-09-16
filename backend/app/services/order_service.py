import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from flask_login import current_user
from sqlalchemy import func

from backend.app.errors import BusinessError, NotFoundError
from backend.app.extensions import db
from backend.app.models import (
    Dish,
    DishOptionGroup,
    Member,
    Order,
    OrderItem,
    OrderItemOption,
    Payment,
    Staff,
    Store,
    StoreDish,
)
from backend.app.services.audit_service import AuditService
from backend.app.services.balance_service import BalanceService

RESOURCE = 'order'


class OrderService:
    # ---------- 查询 ----------

    @staticmethod
    def get_order_by_id(order_id):
        return db.session.get(Order, order_id)

    @staticmethod
    def get_order_or_404(order_id):
        order = OrderService.get_order_by_id(order_id)
        if not order:
            raise NotFoundError('订单不存在')
        return order

    @staticmethod
    def assert_in_scope(order):
        """数据范围：本店范围的角色只能看/动自己门店的订单"""
        allowed = current_user.accessible_store_ids()
        if allowed is not None and order.store_id not in allowed:
            raise BusinessError('无权操作其他门店的订单', status_code=403)

    @staticmethod
    def assert_store_in_scope(store_id):
        allowed = current_user.accessible_store_ids()
        if allowed is not None and store_id not in allowed:
            raise BusinessError('无权操作其他门店的订单', status_code=403)

    @staticmethod
    def get_paginated_orders(page=1, per_page=10, search=None, store_ids=None,
                             store_id=None, status=None):
        query = Order.query

        # 数据范围：店长只看得到本店订单
        if store_ids is not None:
            query = query.filter(Order.store_id.in_(store_ids))
        if store_id:
            query = query.filter(Order.store_id == store_id)
        if status:
            query = query.filter(Order.status == status)
        if search:
            query = query.filter(Order.order_no.ilike(f'%{search}%'))

        return (query
                .order_by(Order.id.desc())
                .paginate(page=page, per_page=per_page, error_out=False))

    # ---------- 首页统计 ----------

    @staticmethod
    def _today_utc_range():
        """今天（服务器本地时区）对应的 UTC 时间范围

        created_at 存的是 UTC 的墙上时间（不带时区），直接拿本地日期去比会错 8 小时——
        早上 8 点之前的单子会被算成昨天。所以先按本地时区定出今天的起止，
        再换算成 UTC 去比。
        """
        now_local = datetime.now().astimezone()
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = start_local + timedelta(days=1)
        # 去掉 tzinfo 是为了能和库里存的「naive UTC」直接比大小
        return (start_local.astimezone(timezone.utc).replace(tzinfo=None),
                end_local.astimezone(timezone.utc).replace(tzinfo=None))

    @staticmethod
    def get_today_stats(store_ids=None):
        """首页看板：今天的订单数、营业额、待接单数

        store_ids 为 None 表示不限门店（老板/运营看全公司），
        否则只看这些店（店长看本店）。
        """
        start, end = OrderService._today_utc_range()

        base = Order.query.filter(Order.created_at >= start, Order.created_at < end)
        if store_ids is not None:
            base = base.filter(Order.store_id.in_(store_ids))

        # 营业额 = 收到的钱 − 退出去的钱，取消的单子不算。
        # 只算 paid_amount 的话退过款的单子会把营业额撑高，那个数没法拿去交差
        revenue = (db.session.query(func.coalesce(
                       func.sum(Order.paid_amount - Order.refunded_amount), 0))
                   .filter(Order.created_at >= start, Order.created_at < end,
                           Order.status != Order.STATUS_CANCELLED))
        if store_ids is not None:
            revenue = revenue.filter(Order.store_id.in_(store_ids))

        return {
            'order_count': base.count(),
            'revenue': float(revenue.scalar() or 0),
            'pending_count': base.filter(Order.status == Order.STATUS_PENDING).count(),
        }

    # ---------- 下单 ----------

    @staticmethod
    def next_order_no(store):
        """单号：门店码-日期-当日序号，如 S001-20260912-0001

        做成可读的而不是 UUID——顾客电话里报单号、店员在屏幕上一眼找单子都要用。

        竞态说明：两个收银员同时下单理论上可能撞号，靠 order_no 的唯一约束兜底
        （撞了整笔事务回滚，用户重试即可）。6 家店每分钟 20 单的量级下概率极低；
        真要做稳，生产环境该换成 Redis INCR 或数据库序列。
        """
        prefix = f'{store.code}-{datetime.now().strftime("%Y%m%d")}-'
        last = (Order.query
                .filter(Order.order_no.like(f'{prefix}%'))
                .order_by(Order.order_no.desc())
                .first())
        seq = int(last.order_no[len(prefix):]) + 1 if last else 1
        return f'{prefix}{seq:04d}'

    @staticmethod
    def build_order_item(dish, override, quantity, option_ids):
        """校验规格 + 算这一行的钱，返回一条 OrderItem（含它选的规格）

        **价格全部从数据库现算**：本店实际价（门店覆盖价或基础价）+ 各选项加价。
        前端传来的任何金额都不采信。

        **`option_ids` 里重复出现 = 要几份**：`[5, 5]` 就是「加蛋 ×2」。
        `option_ids` 本来就是数组，这样请求结构不用多一层嵌套，购物车的
        选中列表也天然支持。单个选项最终落成**一条** OrderItemOption，
        `quantity` 记份数——不是落两条重复的行，那样统计和展示都要自己去合并。

        公开方法而不是私有的：演示数据脚本（app/demo.py）也要用它造订单，
        不能另写一份算价逻辑——两处各算各的，迟早会漂移。
        """
        groups = list(dish.option_groups)
        option_map = {
            option.id: (group, option)
            for group in groups for option in group.options
        }

        # 选中的选项必须真的属于这道菜
        unknown = sorted(set(option_ids) - set(option_map))
        if unknown:
            raise BusinessError(f'「{dish.name}」没有这些规格选项（option_id={unknown}）')

        # 按组归集：group_id -> {option_id: 份数}，dict 保序（按第一次出现的先后）
        picked_by_group = {}
        for option_id in option_ids:
            group, _option = option_map[option_id]
            counts = picked_by_group.setdefault(group.id, {})
            counts[option_id] = counts.get(option_id, 0) + 1

        # 必选选了吗、单选有没有多选或要了两份
        for group in groups:
            counts = picked_by_group.get(group.id, {})
            if group.is_required and not counts:
                raise BusinessError(f'「{dish.name}」的「{group.name}」是必选项，请先选')
            if group.selection_type == DishOptionGroup.TYPE_SINGLE and (
                    len(counts) > 1 or any(n > 1 for n in counts.values())):
                # 同一个选项传两次也算「选了多个」——单选组里要求两份没有意义
                raise BusinessError(f'「{dish.name}」的「{group.name}」只能选一个')

        # 按规格组的顺序铺平，选项快照读起来和菜单上的顺序一致
        ordered = []                       # [(group, option, 份数), ...]
        for group in groups:
            for option_id, count in picked_by_group.get(group.id, {}).items():
                ordered.append((group, option_map[option_id][1], count))

        options_text = ','.join(
            f'{option.name}×{count}' if count > 1 else option.name
            for _group, option, count in ordered
        )

        # 单价 = 本店实际价 + 规格加价合计（加价是单价，要乘份数）
        unit_price = override.effective_price if override else dish.base_price
        unit_price = Decimal(unit_price)
        for _group, option, count in ordered:
            unit_price += Decimal(option.extra_price) * count

        item = OrderItem(
            dish_id=dish.id,
            dish_name=dish.name,
            unit_price=unit_price,
            quantity=quantity,
            subtotal=unit_price * quantity,
            options_text=options_text,
        )
        item.options = [
            OrderItemOption(
                dish_option_id=option.id,
                dish_option_group_name=group.name,
                dish_option_name=option.name,
                extra_price=option.extra_price,     # 单价快照
                quantity=count,
            )
            for group, option, count in ordered
        ]
        return item

    @staticmethod
    def build_order(store, items_data, source, remark='', operator=None, member_id=None):
        """下单的核心：校验菜品、算价、生成单号
        它和create_order的关系是“造“和“存”，这里最后返回一个order对象，但是它不 db.session.add()，也不 commit()
        它调用上面的build_order_item，生成一整单

        **内部代点单和顾客自助下单都走这里。** 算价逻辑只能有一份——
        两条路径各算各的，迟早会算出两个数（而这是钱的事）。

        调用方负责权限和数据范围：内部下单要查登录员工的范围，
        顾客下单走公开接口，没有范围一说（顾客本来就在某一家店里）。
        """
        order = Order(
            order_no=OrderService.next_order_no(store),
            # 顾客端查订单的凭据（见 Order.query_token 的注释）
            query_token=secrets.token_hex(12),
            store_id=store.id,
            source=source,
            remark=remark,
            member_id=member_id,
        )
        if operator:
            order.operator_id = operator.id
            order.operator_name = operator.real_name or operator.username

        total = Decimal('0')
        for raw in items_data:
            dish = db.session.get(Dish, raw['dish_id'])
            if not dish:
                raise NotFoundError(f'菜品不存在（dish_id={raw["dish_id"]}）')
            if dish.status != Dish.STATUS_ACTIVE:
                raise BusinessError(f'「{dish.name}」已停售，点不了')

            override = StoreDish.query.filter_by(
                store_id=store.id, dish_id=dish.id
            ).first()
            if override and not override.is_available:
                raise BusinessError(f'「{dish.name}」在这家门店已下架，点不了')

            item = OrderService.build_order_item(
                dish, override, raw['quantity'], raw['option_ids'] or []
            )
            order.items.append(item)
            total += item.subtotal

        order.total_amount = total
        order.discount_amount = Decimal('0')   # 优惠券是二期的事
        order.payable_amount = total
        order.paid_amount = Decimal('0')
        return order

    @staticmethod
    def create_order(data):
        try:
            store = db.session.get(Store, data['store_id'])
            if not store:
                raise NotFoundError('门店不存在')
            OrderService.assert_store_in_scope(store.id)

            # 操作人：传了 operator_id 就是「实际操作人」（公用账号场景下选的人）；
            # 没传就用当前登录账号
            operator = None
            if data.get('operator_id'):
                operator = db.session.get(Staff, data['operator_id'])
                if not operator:
                    raise NotFoundError('操作人不存在')
            elif current_user.is_authenticated:
                operator = current_user

            # 会员：传了就得真的存在。挂个不存在的 id，后面储值支付会
            # 莫名其妙地失败——不如在这里就说清楚
            member_id = data.get('member_id')
            if member_id and not db.session.get(Member, member_id):
                raise NotFoundError('会员不存在')

            # 单开一个事务：订单和明细要么一起成功，要么一起失败
            order = OrderService.build_order(
                store, data['items'], data['source'],
                data.get('remark', ''), operator, member_id,
            )
            db.session.add(order)
            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='CREATE_ORDER',
                resource=RESOURCE,
                status='success',
                new_value=order.to_dict(with_items=True),
            )

            return order
        except Exception:
            db.session.rollback()
            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='CREATE_ORDER',
                resource=RESOURCE,
                status='failed',
            )
            raise

    # ---------- 状态流转 ----------

    @staticmethod
    def _transition(order_id, target_status, action):
        try:
            order = OrderService.get_order_or_404(order_id)
            OrderService.assert_in_scope(order)

            if not order.can_transition_to(target_status):
                raise BusinessError(
                    f'订单当前是「{order.STATUS_LABELS[order.status]}」，'
                    f'不能改成「{order.STATUS_LABELS[target_status]}」'
                )

            old_value = order.to_dict()
            order.status = target_status
            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action=action,
                resource=RESOURCE,
                status='success',
                old_value=old_value,
                new_value=order.to_dict(),
            )
            return order
        except Exception:
            db.session.rollback()
            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action=action,
                resource=RESOURCE,
                status='failed',
            )
            raise

    @staticmethod
    def accept_order(order_id):
        """接单：pending → accepted"""
        return OrderService._transition(order_id, Order.STATUS_ACCEPTED, 'ACCEPT_ORDER')

    @staticmethod
    def complete_order(order_id):
        """完成：accepted → completed"""
        return OrderService._transition(order_id, Order.STATUS_COMPLETED, 'COMPLETE_ORDER')

    @staticmethod
    def cancel_order(order_id):
        """取消订单

        已经收过钱的单子不能直接取消——钱得先退回去。退款走独立的审批单
        （refund），所以这里拦住并说明，避免出现「订单取消了但钱还在我们账上」。

        判断用的是「净收款」而不是 paid_amount：全部退完之后，这单就该能取消了。
        """
        order = OrderService.get_order_or_404(order_id)
        OrderService.assert_in_scope(order)

        if order.refundable_amount > 0:
            raise BusinessError(
                f'订单还有未退的收款 ¥{order.refundable_amount:.2f}，不能直接取消；'
                f'请先走退款流程把钱退回去'
            )

        return OrderService._transition(order_id, Order.STATUS_CANCELLED, 'CANCEL_ORDER')

    # ---------- 收款 ----------

    @staticmethod
    def _assert_can_use_balance(order):
        """用储值付账前的三道检查

        储值支付和别的支付方式有个根本区别：**钱不是「收进来」，是从顾客自己的
        账户里划走**。所以得先确认「这个账户存在、能用、而且这单还没动过它」——
        任何一条不成立，这笔钱从哪来说不清。
        """
        if order.member_id is None:
            raise BusinessError('这单没关联会员，用不了储值；先在点单时选会员')

        if not order.member.is_active:
            raise BusinessError('该会员已停用，不能动用储值')

        # 一个订单最多一笔储值支付：拆成两笔在账上没有任何意义
        # （真要分两次扣，为什么不一次扣完？），却会让退款时的
        # 「按原消费比例退回」不知道该挂在哪一笔上
        if any(p.method == Payment.METHOD_BALANCE for p in order.payments):
            raise BusinessError('这单已经用过储值了，不能再扣一次')

    @staticmethod
    def add_payment(order_id, data):
        """记一笔收款（一个订单可以有多笔：组合支付、定金+尾款）

        这里只负责记账，不负责真的去调微信支付——线上支付的对接在
        payment gateway 那一层（一期用模拟网关，见 docs/spike/）。
        """
        try:
            order = OrderService.get_order_or_404(order_id)
            OrderService.assert_in_scope(order)

            if order.status == Order.STATUS_CANCELLED:
                raise BusinessError('订单已取消，不能再收款')

            amount = Decimal(data['amount'])
            if order.paid_amount + amount > order.payable_amount:
                remaining = order.payable_amount - order.paid_amount
                raise BusinessError(
                    f'收款金额超过未付部分（还剩 ¥{remaining:.2f}）'
                )

            # 储值支付：钱不是「收进来」，而是从顾客自己的账户里划走。
            # 扣款和下面记 Payment 在同一个事务里——一起成、一起败
            if data['method'] == Payment.METHOD_BALANCE:
                OrderService._assert_can_use_balance(order)
                BalanceService.deduct(
                    order.member_id, amount, order=order,
                    remark=f'订单 {order.order_no} 储值支付',
                )

            # 支付流水号：挂在订单号后面，一眼能看出是哪一单的第几笔
            seq = len(order.payments) + 1
            payment = Payment(
                order_id=order.id,
                method=data['method'],
                amount=amount,
                payment_no=f'{order.order_no}-P{seq:02d}',
            )
            payment.mark_success(
                transaction_no=data.get('transaction_no', ''),
                operator_id=current_user.id,
                operator_name=current_user.username,
            )

            order.payments.append(payment)
            order.paid_amount = order.paid_amount + amount

            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='COLLECT_PAYMENT',
                resource=RESOURCE,
                status='success',
                new_value=payment.to_dict(),
            )

            return payment
        except Exception:
            db.session.rollback()
            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='COLLECT_PAYMENT',
                resource=RESOURCE,
                status='failed',
            )
            raise
