"""储值账户的操作：充值、扣款、退款退回、手工调整、老系统迁移

**所有余额变动都必须经过这里。** 直接改 `Balance` 而不记流水，账就对不上了——
流水的全部价值就在于「一条不漏」。设计文档「必须守住的 6 条」第 1 条。

本金和赠送为什么分开、扣款为什么先扣赠送、并发为什么必须锁行——
都在 `models/balance.py` 的模块开头写清楚了，这里不重复。
"""
import logging
from decimal import Decimal

from flask_login import current_user
from sqlalchemy import select

from backend.app.errors import BusinessError, NotFoundError
from backend.app.extensions import db
from backend.app.models import Balance, BalanceTxn, Member
from backend.app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

RESOURCE = 'balance'

# 金额统一两位小数，不要信任调用方传进来的浮点
CENT = Decimal('0.01')


def _money(value):
    return Decimal(value).quantize(CENT)


class BalanceService:
    # ---------- 查 ----------

    @staticmethod
    def get_member_or_404(member_id):
        member = db.session.get(Member, member_id)
        if not member:
            raise NotFoundError('会员不存在')
        return member

    @staticmethod
    def get_balance(member_id):
        """查账户，没有就返回 None（不是建一个空账户——查的时候不该有副作用）"""
        return Balance.query.filter_by(member_id=member_id).first()

    @staticmethod
    def get_txns(member_id, page=1, per_page=20):
        return (BalanceTxn.query
                .filter_by(member_id=member_id)
                .order_by(BalanceTxn.id.desc())
                .paginate(page=page, per_page=per_page, error_out=False))

    @staticmethod
    def _lock(member_id):
        """锁住这个会员的账户行，返回账户（没有就建一个）

        `with_for_update()` 生成 `SELECT ... FOR UPDATE`：这一行被锁住，别的
        扣款请求得排队。**不锁的话，账面上的「变动后余额」也会错**——你以为
        自己是在余额 100 的基础上扣的，其实中间已经被别人扣过一笔了。

        注意：**SQLite 不支持 FOR UPDATE，会被静默忽略**。测试跑在 SQLite 上，
        所以并发这件事测不出来，只能靠代码审阅。生产（MySQL）是真的生效的。
        """
        balance = db.session.execute(
            select(Balance).where(Balance.member_id == member_id).with_for_update()
        ).scalar_one_or_none()

        if balance is None:
            # 新建的账户不用锁——别人还没见过它
            balance = Balance(member_id=member_id, principal=Decimal('0'), bonus=Decimal('0'))
            db.session.add(balance)
            db.session.flush()
        return balance

    @staticmethod
    def _record(balance, txn_type, principal_delta, bonus_delta,
                order=None, legacy_no='', remark='', operator=None):
        """改余额 + 记流水（**唯一**的记账入口）

        两步绑在一起，不给「改了余额但忘了记流水」留口子。
        调用方负责先用 `_lock` 拿到账户（也就是先锁住行）。
        """
        principal_delta = _money(principal_delta)
        bonus_delta = _money(bonus_delta)

        balance.principal = _money(balance.principal + principal_delta)
        balance.bonus = _money(balance.bonus + bonus_delta)
        db.session.flush()

        if balance.principal < 0 or balance.bonus < 0:
            # 正常路径下走不到这儿（deduct 会先查够不够）。真到了这儿说明
            # 上面某处算错了，宁可整笔回滚也不要留下负余额
            raise BusinessError('余额不足，操作已取消')

        txn = BalanceTxn(
            member_id=balance.member_id,
            type=txn_type,
            principal_delta=principal_delta,
            bonus_delta=bonus_delta,
            # 变动后的余额快照——对账的锚点，一眼看出哪一笔不对
            principal_after=balance.principal,
            bonus_after=balance.bonus,
            order_id=order.id if order is not None else None,
            legacy_no=legacy_no,
            remark=remark,
        )
        db.session.add(txn)
        return txn

    # ---------- 改 ----------

    @staticmethod
    def recharge(member_id, principal, bonus=Decimal('0'), remark=''):
        """充值：`principal` 进本金，`bonus` 进赠送

        「充 100 送 20」= `recharge(id, 100, 20)`。

        **两笔记两条流水，不合成一条。** 因为这两个数在报表上是两回事：
        本金是**真收进来的钱**（收入），赠送是**营销成本**。合成一条的话，
        「这个月充值收了多少」就得从里面挑出来算，很容易算错。
        """
        principal, bonus = _money(principal), _money(bonus)
        if principal < 0 or bonus < 0:
            raise BusinessError('充值金额不能为负')

        member = BalanceService.get_member_or_404(member_id)
        if not member.is_active:
            raise BusinessError('该会员已停用，不能充值')

        try:
            balance = BalanceService._lock(member_id)

            if principal > 0:
                BalanceService._record(balance, BalanceTxn.TYPE_RECHARGE,
                                       principal, Decimal('0'), remark=remark)
            if bonus > 0:
                BalanceService._record(balance, BalanceTxn.TYPE_BONUS,
                                       Decimal('0'), bonus, remark=remark)

            db.session.commit()
            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='RECHARGE_BALANCE',
                resource=RESOURCE,
                status='success',
                new_value={'member_id': member_id,
                           'principal': float(principal), 'bonus': float(bonus),
                           'balance_after': float(balance.total)},
            )
            return balance
        except Exception:
            db.session.rollback()
            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='RECHARGE_BALANCE',
                resource=RESOURCE,
                status='failed',
            )
            raise

    @staticmethod
    def deduct(member_id, amount, order=None, remark=''):
        """扣余额（余额支付）：**先扣赠送、再扣本金**

        顺序的理由见 `models/balance.py`——先花掉不能退的那部分，本金留着
        随时能退，而且结束时状态干净。

        **不 commit**：调用方多半是在一个更大的事务里（比如下单），
        由它决定什么时候提交。这里只保证「锁了行、改了余额、记了流水」。
        """
        amount = _money(amount)
        if amount <= 0:
            raise BusinessError('扣款金额必须大于 0')

        balance = BalanceService._lock(member_id)
        if balance.total < amount:
            raise BusinessError(
                f'余额不足：账上 ¥{balance.total:.2f}，这单要扣 ¥{amount:.2f}'
            )

        from_bonus = min(amount, balance.bonus)
        from_principal = amount - from_bonus
        txn = BalanceService._record(
            balance, BalanceTxn.TYPE_CONSUME,
            -from_principal, -from_bonus,
            order=order, remark=remark,
        )
        return txn

    @staticmethod
    def refund_to_balance(consume_txn, amount, order=None, remark=''):
        """订单退款，钱退回余额

        **必须退回余额，不能退现金**——余额支付的那部分钱，公司在一期充值的
        时候就已经收过了。退现金等于公司再掏一次钱，而顾客的储值还没回来，
        **两边都对不上**。

        退回的金额**按原消费的比例拆**成本金和赠送：那笔消费扣了 80 本金 +
        20 赠送的话，退一半就是退 40 本金 + 10 赠送。全额退时正好原样还原。
        除不尽的部分归本金（对顾客有利）。
        """
        amount = _money(amount)
        if amount <= 0:
            raise BusinessError('退款金额必须大于 0')

        spent = abs(_money(consume_txn.amount))
        if amount > spent:
            raise BusinessError(f'退不回这么多：这笔消费只扣了 ¥{spent:.2f}')

        if spent == 0:
            raise BusinessError('这笔流水没有金额，退不了')

        # 本金占原消费的比例；全额退时 ratio 正好让本金原样还原
        ratio = abs(_money(consume_txn.principal_delta)) / spent
        back_principal = _money(amount * ratio)
        back_bonus = amount - back_principal

        balance = BalanceService._lock(consume_txn.member_id)
        return BalanceService._record(
            balance, BalanceTxn.TYPE_REFUND,
            back_principal, back_bonus,
            order=order or consume_txn.order, remark=remark,
        )

    @staticmethod
    def adjust(member_id, principal_delta, bonus_delta, remark):
        """财务手工调整（补偿、纠错）

        **必须写 remark**——手工动的钱，不写清楚为什么动，事后没人说得清。
        """
        if not remark:
            raise BusinessError('手工调整必须写明原因')

        balance = BalanceService._lock(member_id)
        return BalanceService._record(
            balance, BalanceTxn.TYPE_ADJUST,
            principal_delta, bonus_delta, remark=remark,
        )

    @staticmethod
    def migrate(member_id, amount, legacy_no, remark=''):
        """老系统迁移导入

        过渡期以老系统为权威，所以导进来的余额**一律进本金**——老系统那边
        分不清本金和赠送，我们也不该替它猜。类型记 `migrate` + 老系统单号，
        将来对账要能追回源头。
        """
        amount = _money(amount)
        balance = BalanceService._lock(member_id)
        return BalanceService._record(
            balance, BalanceTxn.TYPE_MIGRATE,
            amount, Decimal('0'),
            legacy_no=legacy_no, remark=remark,
        )
