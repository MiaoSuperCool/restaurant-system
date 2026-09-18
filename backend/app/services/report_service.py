"""经营报表：把订单、支付、菜品汇总成管理层看的数

**先把口径说清楚**（一张报表不写口径，两个人能数出相差一倍的数）：

    营业日    按**下单时间**（`Order.created_at`）算，不是收款时间。
              餐饮的日报问的是「这个营业日做了多少生意」，和订单号里的日期、
              和日结对账（`ReconciliationService._check_order`）都是同一个口径
    营业额    已收 − 已退，**排除已取消的单**。只算 `paid_amount` 的话，
              退过款的单会把营业额撑高，那个数没法拿去交差
    单量      同上，排除已取消
    客单价    营业额 ÷ 单量
    时段      按**本地时间**的小时分组——「几点最忙」问的是店里墙上那个钟

**为什么把订单拉回来在 Python 里按天/按时段切，不在 SQL 里分组**：
库里存的是 UTC，而报表要的是本地时间的「天」和「小时」。SQL 里转时区要么
装 MySQL 时区表（`CONVERT_TZ` 依赖 `mysql.time_zone_name` 有数据），
要么硬编码一个 `+8`——前者部署时容易漏，后者哪天换个时区的门店就错了。
拉回来只有（时间、金额、状态）三列，演示量级（几千行）完全够用。

**量级再大**（比如 6 家店 30 天十万单）就得换做法：SQL 侧按 UTC 天分好组，
再把边界那几个小时挪一下；或者干脆做日报预聚合表。现在不值得。
"""
import logging
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func

from backend.app.errors import BusinessError
from backend.app.extensions import db
from backend.app.models import Order, OrderItem, Payment, Store

logger = logging.getLogger(__name__)

CENT = Decimal('0.01')

# 报表最多往回看多少天。**不是技术限制，是防手滑**：
# 传个 3650，上面那句「拉回来在 Python 里切」就变成拉十万行
MAX_DAYS = 90

# 菜品排行取前几名。全列出来没人看，而且一屏放不下
TOP_DISH_LIMIT = 10


def _money(value):
    return float(Decimal(value or 0).quantize(CENT))


def _local_day_range(start, end):
    """本地自然日 [start, end] → 库里存的 naive UTC 区间 [起, 止)

    `end` 是**含**的（报表里选「1 号到 7 号」自然是两头都算），
    所以内部要 +1 天再取左闭右开。

    和 `ReconciliationService._local_day_range` 是同一个转换，
    两处都写着是因为一个按单日、一个按区间——真要多处共用再抽出来。
    """
    local_tz = datetime.now().astimezone().tzinfo
    start_local = datetime.combine(start, time.min, tzinfo=local_tz)
    end_local = datetime.combine(end + timedelta(days=1), time.min, tzinfo=local_tz)
    return (start_local.astimezone(timezone.utc).replace(tzinfo=None),
            end_local.astimezone(timezone.utc).replace(tzinfo=None))


def _to_local(moment):
    """库里的 naive UTC → 本地时间（按天/按时段分组要用）"""
    return moment.replace(tzinfo=timezone.utc).astimezone()


class ReportService:
    @staticmethod
    def assert_store_in_scope(store_id):
        """数据范围：本店范围的角色只能看自己那家的报表

        老板/财务那种 `all` 范围的账号随便选店——他们本来就该看到全部。
        """
        from flask_login import current_user

        if not current_user.can_access_store(store_id):
            raise BusinessError('无权查看其他门店的报表', status_code=403)

    @staticmethod
    def resolve_range(days=7, start=None, end=None):
        """算出报表的时间区间

        两种给法：给 `days`（最近 N 天，含今天），或者给 `start`/`end` 两个日期。
        都不给就是最近 7 天。
        """
        if start or end:
            end = end or date.today()
            start = start or (end - timedelta(days=6))
        else:
            end = date.today()
            start = end - timedelta(days=max(1, days) - 1)

        if start > end:
            start, end = end, start

        # 夹一下上限，见 MAX_DAYS 的说明
        if (end - start).days + 1 > MAX_DAYS:
            start = end - timedelta(days=MAX_DAYS - 1)
        return start, end

    @staticmethod
    def get_overview(store_ids=None, days=7, start=None, end=None, store_id=None):
        """一份完整的经营概览

        `store_ids` 是**数据范围**（`current_user.accessible_store_ids()`）：
        店长传 `[自己那家]`、老板传 `None`（不限）。`store_id` 是「再看某一家」，
        它只能落在 store_ids 里面——外面那层在 API 层拦（`assert_store_in_scope`）。
        """
        start, end = ReportService.resolve_range(days, start, end)
        utc_start, utc_end = _local_day_range(start, end)

        orders = ReportService._query_orders(store_ids, store_id, utc_start, utc_end)

        return {
            'range': {
                'start': start.isoformat(),
                'end': end.isoformat(),
                'days': (end - start).days + 1,
            },
            'summary': ReportService._summary(orders),
            'trend': ReportService._trend(orders, start, end),
            'by_hour': ReportService._by_hour(orders),
            'by_store': ReportService._by_store(orders),
            'by_method': ReportService._by_method(store_ids, store_id, utc_start, utc_end),
            'top_dishes': ReportService._top_dishes(
                store_ids, store_id, utc_start, utc_end
            ),
        }

    # ---------- 取数 ----------

    @staticmethod
    def _scope(query, store_ids, store_id):
        """数据范围 + 「再看某一家」这两个筛选，所有查询都走这里

        两处都写的话，迟早有一处漏掉——漏掉的那处就是把别家店的数
        算进了店长的报里。所以抽成一个方法，加新查询时必须经过它。
        """
        if store_ids is not None:
            query = query.filter(Order.store_id.in_(store_ids or []))
        if store_id is not None:
            query = query.filter(Order.store_id == store_id)
        return query

    @staticmethod
    def _query_orders(store_ids, store_id, utc_start, utc_end):
        """把区间内的订单拉回来（只取算报表要用的几列）

        拉回来在 Python 里切，理由见模块开头。**已取消的单也拉**——
        单量、时段那些要排除它，但「取消了几单」本身也是店长想看的数。
        """
        query = db.session.query(
            Order.id, Order.store_id, Order.status, Order.created_at,
            Order.paid_amount, Order.refunded_amount,
        ).filter(Order.created_at >= utc_start, Order.created_at < utc_end)
        return ReportService._scope(query, store_ids, store_id).all()

    # ---------- 各维度 ----------

    @staticmethod
    def _valid(orders):
        """算营业额和单量的那些单：**排除已取消**

        取消的单钱没进来过，算进营业额就是虚的；但也别丢掉，
        `by_hour` 里能看出「这个点顾客老是取消」。
        """
        return [o for o in orders if o.status != Order.STATUS_CANCELLED]

    @staticmethod
    def _summary(orders):
        valid = ReportService._valid(orders)
        revenue = sum((Decimal(o.paid_amount) - Decimal(o.refunded_amount) for o in valid),
                      Decimal('0'))
        refund = sum((Decimal(o.refunded_amount) for o in valid), Decimal('0'))
        count = len(valid)

        return {
            'revenue': _money(revenue),
            'order_count': count,
            # 客单价：单量为 0 时给 0，别给 NaN——前端显示「NaN 元」很难看
            'avg_order_amount': _money(revenue / count) if count else 0,
            'refund_amount': _money(refund),
            'cancelled_count': len(orders) - count,
        }

    @staticmethod
    def _trend(orders, start, end):
        """按天铺开——**没有单的日子也要有一行**，不然柱子会跳着排"""
        buckets = {}
        day = start
        while day <= end:
            buckets[day.isoformat()] = {'revenue': Decimal('0'), 'order_count': 0}
            day += timedelta(days=1)

        for order in ReportService._valid(orders):
            key = _to_local(order.created_at).date().isoformat()
            if key not in buckets:      # 时区换算后可能落到区间外的相邻日
                continue
            buckets[key]['revenue'] += Decimal(order.paid_amount) - Decimal(order.refunded_amount)
            buckets[key]['order_count'] += 1

        return [
            {'date': key, 'revenue': _money(value['revenue']),
             'order_count': value['order_count']}
            for key, value in buckets.items()
        ]

    @staticmethod
    def _by_hour(orders):
        """按时段——**只返回有单的小时**，24 个空格子没人看

        这一块是给排班用的：「11 点到 13 点占了一天四成的单」，
        比「今天 56 单」有用得多。
        """
        buckets = {}
        for order in ReportService._valid(orders):
            hour = _to_local(order.created_at).hour
            bucket = buckets.setdefault(hour, {'order_count': 0, 'revenue': Decimal('0')})
            bucket['order_count'] += 1
            bucket['revenue'] += Decimal(order.paid_amount) - Decimal(order.refunded_amount)

        return [
            {'hour': hour, 'order_count': buckets[hour]['order_count'],
             'revenue': _money(buckets[hour]['revenue'])}
            for hour in sorted(buckets)
        ]

    @staticmethod
    def _by_store(orders):
        """按门店——店长只会看到自己一家，老板看到 6 家对比

        门店名要查一次表：订单里只有 store_id。6 家店，一次查完就够了
        """
        buckets = {}
        for order in ReportService._valid(orders):
            bucket = buckets.setdefault(order.store_id, {'order_count': 0, 'revenue': Decimal('0')})
            bucket['order_count'] += 1
            bucket['revenue'] += Decimal(order.paid_amount) - Decimal(order.refunded_amount)

        names = {
            store.id: store.name
            for store in Store.query.filter(Store.id.in_(list(buckets) or [0])).all()
        }

        rows = [
            {'store_id': store_id, 'store_name': names.get(store_id, f'门店 {store_id}'),
             'order_count': value['order_count'], 'revenue': _money(value['revenue'])}
            for store_id, value in buckets.items()
        ]
        # 营业额高的排前面——「哪家店做得好」是这张表要回答的问题
        rows.sort(key=lambda row: row['revenue'], reverse=True)
        return rows

    @staticmethod
    def _by_method(store_ids, store_id, utc_start, utc_end):
        """支付方式构成

        **只看成功的支付流水**（失败的、还没支付的不算钱）。
        和营业额的差额就是退款——那部分单独在 summary 里给了。
        """
        query = (db.session.query(
                     Payment.method,
                     func.count(Payment.id),
                     func.sum(Payment.amount),
                 )
                 .join(Order, Payment.order_id == Order.id)
                 .filter(Payment.status == Payment.STATUS_SUCCESS,
                         Order.created_at >= utc_start, Order.created_at < utc_end,
                         Order.status != Order.STATUS_CANCELLED))
        query = ReportService._scope(query, store_ids, store_id)

        return [
            {'method': method, 'method_label': Payment.METHOD_LABELS.get(method, method),
             'count': count, 'amount': _money(total)}
            for method, count, total in query.group_by(Payment.method).all()
        ]

    @staticmethod
    def _top_dishes(store_ids, store_id, utc_start, utc_end):
        """菜品排行：卖了多少份、收了多少钱

        **用订单明细里的快照**（`dish_name`），不 join 菜品表：
        菜改过名的话，报表显示的该是「当时卖的那个名字」——
        和订单快照一条道理。数量按份数（`quantity`）排，不是按销售额。
        """
        query = (db.session.query(
                     OrderItem.dish_id,
                     OrderItem.dish_name,
                     func.sum(OrderItem.quantity),
                     func.sum(OrderItem.subtotal),
                 )
                 .join(Order, OrderItem.order_id == Order.id)
                 .filter(Order.created_at >= utc_start, Order.created_at < utc_end,
                         Order.status != Order.STATUS_CANCELLED))
        query = ReportService._scope(query, store_ids, store_id)

        rows = (query
                .group_by(OrderItem.dish_id, OrderItem.dish_name)
                .order_by(func.sum(OrderItem.quantity).desc())
                .limit(TOP_DISH_LIMIT)
                .all())

        return [
            {'dish_id': dish_id, 'dish_name': dish_name,
             'quantity': int(quantity), 'amount': _money(amount)}
            for dish_id, dish_name, quantity, amount in rows
        ]
