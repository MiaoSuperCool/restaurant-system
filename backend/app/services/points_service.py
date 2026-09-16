"""积分账户的操作：消费返、抵扣、手工调整、老系统迁移

**所有积分变动都必须经过这里**——直接改 `Points` 而不记流水，账就对不上了。
和 `BalanceService` 是一个路子，区别在于积分不分本金/赠送（见 `models/points.py`）。

换算比例
--------

    消费 1 元  →  返 1 积分
    100 积分   →  抵 1 元

**先写成模块常量。** 真要按门店/活动配置，那是后面的事——但那时候改动会散到
「返多少」「抵多少」「退款怎么回滚」三处，所以现在就把换算收在
`points_for_amount` / `amount_for_points` 两个函数里，别的地方不许自己算。
"""
import logging
from decimal import Decimal

from flask_login import current_user
from sqlalchemy import select

from backend.app.errors import BusinessError, NotFoundError
from backend.app.extensions import db
from backend.app.models import Member, Points, PointsTxn
from backend.app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

RESOURCE = 'points'

# 消费 1 元返多少积分
EARN_RATE = 1
# 多少积分抵 1 元
REDEEM_RATE = 100

CENT = Decimal('0.01')


class PointsService:
    # ---------- 换算 ----------

    @staticmethod
    def points_for_amount(amount):
        """这笔消费能返多少积分

        向下取整：消费 32.5 元返 32 积分（多给的那 0.5 分不如少给，
        免得账面上出现"差 0.5 分"这种说不清的东西）
        """
        return int(Decimal(amount) * EARN_RATE)

    @staticmethod
    def amount_for_points(points):
        """这些积分能抵多少钱"""
        return (Decimal(points) / REDEEM_RATE).quantize(CENT)

    @staticmethod
    def max_points_for_amount(amount):
        """这么多钱的订单，最多能用多少积分抵

        **不能抵成负数**（那等于倒找钱给顾客），所以抵扣上限就是订单金额。
        这个换算和「返多少」用的是**不同的比例**（返是 `EARN_RATE`、抵是
        `REDEEM_RATE`），所以得单独一个函数，别拿 `points_for_amount` 凑。
        """
        return int(Decimal(amount) * REDEEM_RATE)

    # ---------- 查 ----------

    @staticmethod
    def get_member_or_404(member_id):
        member = db.session.get(Member, member_id)
        if not member:
            raise NotFoundError('会员不存在')
        return member

    @staticmethod
    def get_points(member_id):
        """查账户，没有就返回 None（查的时候不该有副作用）"""
        return Points.query.filter_by(member_id=member_id).first()

    @staticmethod
    def get_balances(member_ids):
        """批量取积分：`{member_id: Points}`（列表页用，避免 N+1）"""
        if not member_ids:
            return {}
        rows = Points.query.filter(Points.member_id.in_(member_ids)).all()
        return {row.member_id: row for row in rows}

    @staticmethod
    def empty_dict(member_id):
        """没积过分的账户长什么样（和 BalanceService.empty_dict 一个意思）"""
        return {'member_id': member_id, 'balance': 0}

    @staticmethod
    def get_txns(member_id, page=1, per_page=20):
        return (PointsTxn.query
                .filter_by(member_id=member_id)
                .order_by(PointsTxn.id.desc())
                .paginate(page=page, per_page=per_page, error_out=False))

    # ---------- 改 ----------

    @staticmethod
    def _lock(member_id):
        """锁住这个会员的积分行（没有就建一个）

        理由和 `BalanceService._lock` 一样：不锁的话，两个收银台同时给同一个会员
        扣积分/返积分，会各自读到旧值——**流水里的「变动后余额」也会跟着错**。

        SQLite 不支持 FOR UPDATE（测试环境会静默忽略），所以并发这件事测不出来。
        """
        points = db.session.execute(
            select(Points).where(Points.member_id == member_id).with_for_update()
        ).scalar_one_or_none()

        if points is None:
            points = Points(member_id=member_id, balance=0)
            db.session.add(points)
            db.session.flush()
        return points

    @staticmethod
    def _record(points, txn_type, delta, order=None, legacy_no='', remark=''):
        """改积分 + 记流水（**唯一**的记账入口）"""
        points.balance = points.balance + int(delta)
        db.session.flush()

        if points.balance < 0:
            # 正常路径走不到这儿（redeem 会先查够不够）。真到了说明上面算错了，
            # 宁可整笔回滚也不要留下负积分
            raise BusinessError('积分不足，操作已取消')

        txn = PointsTxn(
            member_id=points.member_id,
            type=txn_type,
            delta=int(delta),
            after=points.balance,
            order_id=order.id if order is not None else None,
            legacy_no=legacy_no,
            remark=remark,
        )
        db.session.add(txn)
        return txn

    @staticmethod
    def earn(member_id, amount, order=None, remark=''):
        """消费返积分：`amount` 是这笔消费多少钱

        **不 commit**——调用方多半在一个更大的事务里（比如收款），由它决定
        什么时候提交。`order` 可传可不传：门店现场补返积分时未必挂得上单。
        """
        delta = PointsService.points_for_amount(amount)
        if delta <= 0:
            # 消费金额太小，返不出整数分。不必记一条 +0 的流水
            return None

        if not remark:
            remark = f'订单 {order.order_no} 消费返积分' if order else '消费返积分'

        points = PointsService._lock(member_id)
        return PointsService._record(
            points, PointsTxn.TYPE_EARN, delta, order=order, remark=remark,
        )

    @staticmethod
    def redeem(member_id, points_to_use, order=None, remark=''):
        """用积分抵扣——扣积分

        返回**抵扣了多少钱**（调用方拿它去减应付）。扣多少积分由调用方定，
        因为「最多能用多少」是订单那边的事（不能抵超过订单金额）。
        """
        points_to_use = int(points_to_use)
        if points_to_use <= 0:
            raise BusinessError('抵扣的积分必须大于 0')

        points = PointsService._lock(member_id)
        if points.balance < points_to_use:
            raise BusinessError(
                f'积分不够：账上 {points.balance} 分，这次要用 {points_to_use} 分'
            )

        PointsService._record(
            points, PointsTxn.TYPE_REDEEM, -points_to_use, order=order, remark=remark,
        )
        return PointsService.amount_for_points(points_to_use)

    @staticmethod
    def adjust(member_id, delta, remark):
        """员工手工调整（补偿、纠错）

        **必须写 remark**——手工加的分，不写清楚为什么，事后没人说得清。
        """
        if not remark:
            raise BusinessError('手工调整必须写明原因')
        if not delta:
            raise BusinessError('调整数量不能是 0')

        points = PointsService._lock(member_id)
        return PointsService._record(points, PointsTxn.TYPE_ADJUST, delta, remark=remark)

    @staticmethod
    def revoke(member_id, amount, order=None, remark=''):
        """退款时把当初返的积分扣回来

        消费 32 元返了 32 分，退 32 元就扣回 32 分；退 10 元就扣 10 分——
        按**退款金额**算，和返的时候用的是同一个换算。

        **扣不满就扣到 0 为止，不让积分变负。** 顾客可能早就把积分花掉了
        （抵扣了另一单）。

        这里有个已知的小口子：花 1000 分抵 10 元、再把那 10 元退掉，只会扣回
        10 分——那 1000 分已经花出去了。金额很小，而且退款要走审批流，先接受。
        真要堵上得让积分能变负（欠着），那是另一套账。

        返回实际扣了多少分（可能比 `delta` 少，也可能不记流水）。
        """
        delta = PointsService.points_for_amount(amount)
        if delta <= 0:
            return None

        points = PointsService._lock(member_id)
        actual = min(delta, points.balance)     # 不够就扣到 0
        if actual <= 0:
            # 一分都没有，不用往流水里塞一条 0 变动的记录
            return None

        if not remark:
            remark = f'订单 {order.order_no} 退款扣回积分' if order else '退款扣回积分'

        txn = PointsService._record(
            points, PointsTxn.TYPE_REVOKE, -actual, order=order, remark=remark,
        )
        # 没扣满的话补一句，免得看流水的人以为程序算错了
        if actual < delta:
            txn.remark = f'{remark}（应扣 {delta} 分，账上只有 {points.balance + actual} 分，扣到 0 为止）'
        return txn

    @staticmethod
    def restore(member_id, points, order=None, remark=''):
        """退款时把当初**抵扣用掉**的积分还回去

        和 `revoke` 是一对，方向相反：

            revoke    退款 → 扣掉「消费时返的」（那笔消费不算了）
            restore   退款 → 还回「抵扣时用的」（那笔优惠也不算了）

        全额退款时正好全部还原：当初抵了多少分，就还多少分。
        参数是**分**不是金额——因为 `Order.points_used` 记的就是分，
        还的时候要精确对上，不能再过一道换算。
        """
        points = int(points)
        if points <= 0:
            return None

        if not remark:
            remark = f'订单 {order.order_no} 退款返还抵扣积分' if order else '退款返还抵扣积分'

        account = PointsService._lock(member_id)
        return PointsService._record(
            account, PointsTxn.TYPE_RESTORE, points, order=order, remark=remark,
        )

    @staticmethod
    def migrate(member_id, balance, legacy_no, remark=''):
        """老系统迁移导入——类型记 `migrate` + 老系统单号，将来对账要能追回源头"""
        points = PointsService._lock(member_id)
        return PointsService._record(
            points, PointsTxn.TYPE_MIGRATE, balance,
            legacy_no=legacy_no, remark=remark,
        )

    # ---------- 带审计的入口（给 API 用） ----------

    @staticmethod
    def adjust_with_audit(member_id, delta, remark):
        """手工调整 + 审计 + 事务

        `adjust` 本身不 commit（它可能被包在别的事务里），但**手工调整是独立动作**，
        得自己管事务和留痕。
        """
        try:
            PointsService.get_member_or_404(member_id)
            txn = PointsService.adjust(member_id, delta, remark)
            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='ADJUST_POINTS',
                resource=RESOURCE,
                status='success',
                new_value={'member_id': member_id, 'delta': delta,
                           'after': txn.after, 'remark': remark},
            )
            return txn
        except Exception:
            db.session.rollback()
            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='ADJUST_POINTS',
                resource=RESOURCE,
                status='failed',
            )
            raise
