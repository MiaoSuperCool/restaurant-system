"""对账：账上记的数，和按流水重算的数，对不对得上

**对的是什么**（模型文件 `models/legacy.py` 开头也写了，这里说操作层面的）：

    储值   期望 = 流水累加        实际 = 账户余额
    订单   期望 = 支付流水合计     实际 = 订单的 paid_amount 合计

**期望值是「按原始凭证重算出来的」，实际值是「账上现在记着的」**，
差异 = 实际 − 期望（正数 = 账上多了）。这个方向别搞反，
不然界面上「多了 100」和「少了 100」会反着显示。

两个类别的时间口径不一样，这是**刻意**的
------------------------------------------

订单是**按天**对的：`biz_date` 那天该店收了多少，是有明确答案的问题。

储值**没有历史快照**——`Balance` 表存的是「此刻账上有多少」，不是「某天收盘时
有多少」。所以储值对账算的就是**跑它的那一刻**，`biz_date` 只是这条结论挂在哪天。
跑历史日期的储值对账没有意义，界面上也不给选。

（真要做历史对账得加余额日切快照，那是另一件事，现在不需要。）
"""
import logging
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func

from backend.app.errors import BusinessError, NotFoundError
from backend.app.extensions import db
from backend.app.models import (
    Balance,
    BalanceTxn,
    Member,
    Order,
    Payment,
    Reconciliation,
    Store,
)
from backend.app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

RESOURCE = 'reconciliation'

CENT = Decimal('0.01')

# 差异明细最多留几条。**留明细是为了让人能顺藤摸瓜**，不是把流水复制一份——
# 真差了 500 个会员，该去查流水，不是在页面上翻 500 行
DETAIL_LIMIT = 20


def _money(value):
    return Decimal(value or 0).quantize(CENT)


class ReconciliationService:
    # ---------- 跑对账 ----------

    @staticmethod
    def run(biz_date, category, store_id=None):
        """跑一次对账，把结论存下来

        **同一个（日期、门店、类别）只留一条**：对账的语义是「重新下一遍结论」，
        不是攒一堆历史。旧的直接删掉重插——它本身也是算出来的，
        没有任何需要保留的人工输入（这也是不靠数据库唯一索引的原因，
        见 `Reconciliation.store_id` 那段注释）。
        """
        if category == Reconciliation.CATEGORY_BALANCE:
            result = ReconciliationService._check_balance()
            store_id = None
        elif category == Reconciliation.CATEGORY_ORDER:
            if store_id is None:
                raise BusinessError('订单对账要指定门店')
            result = ReconciliationService._check_order(biz_date, store_id)
        else:
            raise BusinessError(f'不认识的对账类别：{category}')

        expected = _money(result['expected'])
        actual = _money(result['actual'])
        diff = _money(actual - expected)

        # **「对不对得上」看的是有没有对不上的明细，不是总额差多少。**
        # 一个会员多 100、一个会员少 100，总额正好抵消、差值是 0，
        # 但这两个人的账都是错的——只看金额的话这种账会被判成没问题。
        # （这条是写测试时被测试抓出来的，见 test_balance_compares_member_by_member）
        status = (Reconciliation.STATUS_MATCHED if result['mismatched'] == 0
                  else Reconciliation.STATUS_MISMATCHED)

        # 对账多半是定时任务跑的（日结），那时候没有登录用户，记成「系统」。
        # 但也能在页面上手工点一下，那就记成点的那个人
        operator_id, operator_name = AuditService.current_operator('系统（日结对账）')

        try:
            Reconciliation.query.filter_by(
                biz_date=biz_date, store_id=store_id, category=category,
            ).delete()

            record = Reconciliation(
                biz_date=biz_date,
                store_id=store_id,
                category=category,
                expected_amount=expected,
                actual_amount=actual,
                diff_amount=diff,
                status=status,
                mismatch_count=result['mismatched'],
                detail=result['detail'],
                checked_at=datetime.now(timezone.utc),
            )
            db.session.add(record)
            db.session.commit()

            AuditService.log(
                operator_id=operator_id,
                operator_name=operator_name,
                action='RUN_RECONCILIATION',
                resource=RESOURCE,
                status='success',
                new_value={'biz_date': biz_date.isoformat(), 'category': category,
                           'store_id': store_id,
                           'expected': float(expected), 'actual': float(actual),
                           'diff': float(diff)},
            )
            return record
        except Exception:
            db.session.rollback()
            AuditService.log(
                operator_id=operator_id,
                operator_name=operator_name,
                action='RUN_RECONCILIATION',
                resource=RESOURCE,
                status='failed',
            )
            raise

    # ---------- 储值 ----------

    @staticmethod
    def _check_balance():
        """储值：账户余额 vs 流水累加

        **一个会员一个会员地比，不是把两边汇总起来相减。**
        汇总对得上不等于没问题：A 多 100、B 少 100，总数是平的，
        但这两个顾客的账各自都是错的。设计文档说「那 80 万一分不差」，
        指的正是每个人头上那一份都对得上。
        """
        # 流水按会员累加。没有流水的会员不会出现在这个 dict 里
        txn_totals = {
            member_id: Decimal(total)
            for member_id, total in db.session.query(
                BalanceTxn.member_id,
                func.sum(BalanceTxn.principal_delta + BalanceTxn.bonus_delta),
            ).group_by(BalanceTxn.member_id).all()
        }
        balances = {
            balance.member_id: Decimal(balance.principal) + Decimal(balance.bonus)
            for balance in Balance.query.all()
        }

        # 两边的会员取并集：有可能**有账户没流水**（直接建了个空账户），
        # 也可能**有流水没账户**（历史脏数据）——两种都是要对出来的
        member_ids = set(txn_totals) | set(balances)
        names = {}
        if member_ids:
            names = {
                member.id: (member.nickname or member.mobile or f'会员 {member.id}')
                for member in Member.query.filter(Member.id.in_(member_ids)).all()
            }

        expected = actual = Decimal('0')
        detail = []
        mismatched = 0
        for member_id in sorted(member_ids):
            member_expected = txn_totals.get(member_id, Decimal('0'))
            member_actual = balances.get(member_id, Decimal('0'))
            expected += member_expected
            actual += member_actual
            if member_expected != member_actual:
                # 计数不受明细条数上限影响：明细只留前 20 条给人看，
                # 但「有几个人对不上」这个数必须是准的
                mismatched += 1
                if len(detail) < DETAIL_LIMIT:
                    detail.append({
                        'member_id': member_id,
                        'member_name': names.get(member_id, f'会员 {member_id}'),
                        'expected': float(member_expected),
                        'actual': float(member_actual),
                        'diff': float(member_actual - member_expected),
                    })

        return {'expected': expected, 'actual': actual,
                'detail': detail, 'mismatched': mismatched}

    # ---------- 订单 ----------

    @staticmethod
    def _local_day_range(biz_date):
        """本地自然日 → 库里存的 naive UTC 区间 [起, 止)

        **必须转这一道**：库里存的是 UTC，而「昨天做了多少生意」问的是店里墙上
        那个日历。不转的话，晚上 8 点以后的订单会被算到第二天去——
        一天里最忙的那几个小时正好压在边界上。

        用的是服务器的本地时区（`datetime.now().astimezone()`），
        和 `OrderService` 生成单号时用的口径一致。
        """
        local_tz = datetime.now().astimezone().tzinfo
        start = datetime.combine(biz_date, time.min, tzinfo=local_tz)
        end = start + timedelta(days=1)
        return (start.astimezone(timezone.utc).replace(tzinfo=None),
                end.astimezone(timezone.utc).replace(tzinfo=None))

    @staticmethod
    def _check_order(biz_date, store_id):
        """订单：账上记的实收 vs 支付流水

        期望 = 当天该店**支付成功**的流水合计
        实际 = 当天该店订单的 `paid_amount` 合计

        这两个数正常必须一模一样——`paid_amount` 本来就是一笔笔收款加上去的。
        对不上说明有脏数据：手工改过库、或者某段代码只写了其中一边。
        **这类差异越早发现越便宜**，拖到月底就是一笔说不清的账。

        **退款不在这次对账里**：退款走 `RefundTxn`（出账），
        和这里的「进账对不对得上」是两条线，混在一起反而看不清是哪边错了。

        `biz_date` 按下单日算，不按支付时间——营业额报表问的是
        「这个营业日做了多少生意」，订单号里的日期也是下单日。
        """
        start, end = ReconciliationService._local_day_range(biz_date)

        orders = Order.query.filter(
            Order.store_id == store_id,
            Order.created_at >= start,
            Order.created_at < end,
        ).all()
        order_ids = [order.id for order in orders]

        actual = sum((Decimal(order.paid_amount) for order in orders), Decimal('0'))

        payments = (Payment.query
                    .filter(Payment.order_id.in_(order_ids),
                            Payment.status == Payment.STATUS_SUCCESS)
                    .all()) if order_ids else []
        expected = sum((Decimal(payment.amount) for payment in payments), Decimal('0'))

        # 明细按订单汇总，方便直接看出是哪一单对不上
        paid_by_order = {}
        for payment in payments:
            paid_by_order[payment.order_id] = (
                paid_by_order.get(payment.order_id, Decimal('0')) + Decimal(payment.amount)
            )

        detail = []
        mismatched = 0
        for order in orders:
            order_paid = Decimal(order.paid_amount)
            order_txn = paid_by_order.get(order.id, Decimal('0'))
            if order_paid != order_txn:
                mismatched += 1
                if len(detail) < DETAIL_LIMIT:
                    detail.append({
                        'order_id': order.id,
                        'order_no': order.order_no,
                        'expected': float(order_txn),
                        'actual': float(order_paid),
                        'diff': float(order_paid - order_txn),
                    })

        return {'expected': expected, 'actual': actual,
                'detail': detail, 'mismatched': mismatched}

    # ---------- 查 ----------

    @staticmethod
    def get_records(page=1, per_page=10, category=None, store_id=None, status=None,
                    biz_date=None):
        query = Reconciliation.query
        if category:
            query = query.filter(Reconciliation.category == category)
        if store_id is not None:
            query = query.filter(Reconciliation.store_id == store_id)
        if status:
            query = query.filter(Reconciliation.status == status)
        if biz_date:
            query = query.filter(Reconciliation.biz_date == biz_date)

        return (query.order_by(Reconciliation.biz_date.desc(), Reconciliation.id.desc())
                .paginate(page=page, per_page=per_page, error_out=False))

    @staticmethod
    def get_or_404(record_id):
        record = db.session.get(Reconciliation, record_id)
        if not record:
            raise NotFoundError('对账记录不存在')
        return record

    @staticmethod
    def resolve_store(store_id):
        """订单对账要指定门店——先确认它真的存在

        不确认的话，门店 id 写错了会得到一个「0 对 0、对得上」的结论，
        比报错难查得多。
        """
        store = db.session.get(Store, store_id)
        if not store:
            raise NotFoundError('门店不存在')
        return store
