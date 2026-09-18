"""优惠券：建模板、发券、查券、用券

模型的三个设计点（为什么两张表、为什么过期不写库、为什么没有券码）在
`models/coupon.py` 的模块开头写清楚了，这里不重复。

**这张文件里最要紧的是 `check()`**——「这张券现在能不能用」有四个条件
（用过没、过期没、这家店能不能用、够不够门槛），散在各处迟早漏一个。
而且它**返回原因而不是抛异常**，因为「查这单能用哪些券」只是查，不是操作。
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal

from flask_login import current_user
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from backend.app.errors import BusinessError, NotFoundError
from backend.app.extensions import db
from backend.app.models import CouponTemplate, Member, Store, UserCoupon
from backend.app.services.audit_service import AuditService
from backend.app.utils.references import describe_references, find_referencing_rows

logger = logging.getLogger(__name__)

RESOURCE = 'coupon'

CENT = Decimal('0.01')


def _money(value):
    return Decimal(value).quantize(CENT)


class CouponService:
    # ---------- 模板：查 ----------

    @staticmethod
    def get_template_or_404(template_id):
        template = db.session.get(CouponTemplate, template_id)
        if not template:
            raise NotFoundError('券模板不存在')
        return template

    @staticmethod
    def get_templates(page=1, per_page=10, search=None, status=None):
        query = CouponTemplate.query
        if search:
            query = query.filter(CouponTemplate.name.ilike(f'%{search}%'))
        if status:
            query = query.filter(CouponTemplate.status == status)
        return (query.order_by(CouponTemplate.id.desc())
                .paginate(page=page, per_page=per_page, error_out=False))

    @staticmethod
    def _resolve_stores(store_ids):
        """适用门店：空列表 = 全公司通用（和分类那边一个语义）

        「哪家店都不能用」不是这样表达的——那应该把券停用，直白得多。
        """
        if not store_ids:
            return []
        stores = Store.query.filter(Store.id.in_(store_ids)).all()
        missing = set(store_ids) - {store.id for store in stores}
        if missing:
            raise NotFoundError(f'门店不存在（store_id={sorted(missing)}）')
        return stores

    @staticmethod
    def _assert_discount_value(template_type, value):
        """折扣率得在 (0, 1) 之间——1 是原价（等于没打折），0 是白送

        满减不用管：减 0 元是「没优惠」，语义上说得通（虽然没什么用）
        """
        if template_type != CouponTemplate.TYPE_DISCOUNT:
            return
        if not (Decimal('0') < value < Decimal('1')):
            raise BusinessError('折扣率要在 0 和 1 之间（0.85 表示八五折）')

    # ---------- 模板：改 ----------

    @staticmethod
    def create_template(data):
        try:
            CouponService._assert_discount_value(data['type'], Decimal(data['value']))

            template = CouponTemplate(
                name=data['name'],
                type=data['type'],
                value=data['value'],
                min_amount=data.get('min_amount') or Decimal('0'),
                is_claimable=data.get('is_claimable', False),
                per_member_limit=data.get('per_member_limit'),
                valid_from=data.get('valid_from'),
                valid_to=data.get('valid_to'),
                total_quantity=data.get('total_quantity'),
                status=data.get('status', CouponTemplate.STATUS_ACTIVE),
            )
            template.stores = CouponService._resolve_stores(data.get('store_ids'))

            db.session.add(template)
            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='CREATE_COUPON_TEMPLATE',
                resource=RESOURCE,
                status='success',
                new_value=template.to_dict(),
            )
            return template
        except Exception:
            db.session.rollback()
            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='CREATE_COUPON_TEMPLATE',
                resource=RESOURCE,
                status='failed',
            )
            raise

    @staticmethod
    def update_template(template_id, data):
        try:
            template = CouponService.get_template_or_404(template_id)
            old_value = template.to_dict()

            # 类型和面额一起校验：单改 value 时类型还是旧的
            new_type = data.get('type', template.type)
            new_value = Decimal(data.get('value', template.value))
            CouponService._assert_discount_value(new_type, new_value)

            for field in ('name', 'type', 'value', 'min_amount',
                          'valid_from', 'valid_to', 'total_quantity',
                          'is_claimable', 'per_member_limit', 'status'):
                if field in data:
                    setattr(template, field, data[field])

            if 'store_ids' in data:
                template.stores = CouponService._resolve_stores(data['store_ids'])

            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='UPDATE_COUPON_TEMPLATE',
                resource=RESOURCE,
                status='success',
                old_value=old_value,
                new_value=template.to_dict(),
            )
            return template
        except Exception:
            db.session.rollback()
            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='UPDATE_COUPON_TEMPLATE',
                resource=RESOURCE,
                status='failed',
            )
            raise

    @staticmethod
    def delete_template(template_id):
        """删模板——**发出去过的就不能删了**

        券的引用是 RESTRICT：顾客手里还有券，模板没了那张券就成了没头没尾的东西
        （面额、有效期、适用门店全在模板上）。不想再发的话，把状态改成「停用」——
        停用只停发，已经发出去的还能用。
        """
        try:
            template = CouponService.get_template_or_404(template_id)

            references = find_referencing_rows(CouponTemplate, template_id)
            if references:
                raise BusinessError(
                    f'券模板「{template.name}」还有{describe_references(references)}，'
                    f'不能删除；不想再发的话请把状态改成「停用」'
                )

            old_value = template.to_dict()
            db.session.delete(template)
            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='DELETE_COUPON_TEMPLATE',
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
                action='DELETE_COUPON_TEMPLATE',
                resource=RESOURCE,
                status='failed',
            )
            raise

    # ---------- 发券 ----------

    @staticmethod
    def issue(template_id, member_ids, count=1, remark=''):
        """给一批会员发券，返回实际发出去多少张

        三道检查：模板得是启用的（停用只管「不再发」，所以这里拦）、
        会员得存在且没停用、**总量得够**。
        """
        if not member_ids:
            raise BusinessError('至少要选一个会员')
        if count < 1:
            raise BusinessError('每个会员至少要发 1 张')

        template = CouponService.get_template_or_404(template_id)

        # 锁住模板行再算总量——不锁的话两个人在两个页面同时发，
        # 各自都看到「还剩 5 张」，结果发出去 10 张
        db.session.execute(
            select(CouponTemplate).where(CouponTemplate.id == template_id).with_for_update()
        )

        if template.status != CouponTemplate.STATUS_ACTIVE:
            raise BusinessError(f'券模板「{template.name}」已停用，不能再发')

        members = Member.query.filter(Member.id.in_(member_ids)).all()
        missing = set(member_ids) - {member.id for member in members}
        if missing:
            raise NotFoundError(f'会员不存在（member_id={sorted(missing)}）')

        disabled = [m.nickname or m.mobile for m in members if not m.is_active]
        if disabled:
            raise BusinessError(f'这些会员已停用，不能发券：{"、".join(disabled)}')

        if template.total_quantity is not None:
            issued = template.issued.count()
            wanted = len(members) * count
            if issued + wanted > template.total_quantity:
                raise BusinessError(
                    f'券模板「{template.name}」一共 {template.total_quantity} 张，'
                    f'已经发了 {issued} 张，这次要发 {wanted} 张——不够'
                )

        try:
            now = datetime.now(timezone.utc)
            for member in members:
                for _ in range(count):
                    db.session.add(UserCoupon(
                        template_id=template.id,
                        member_id=member.id,
                        received_at=now,
                        issued_by_id=current_user.id,
                        issued_by_name=current_user.real_name or current_user.username,
                    ))

            db.session.commit()

            total = len(members) * count
            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='ISSUE_COUPON',
                resource=RESOURCE,
                status='success',
                new_value={'template_id': template.id, 'template_name': template.name,
                           'member_ids': member_ids, 'count_each': count, 'total': total,
                           'remark': remark},
            )
            return total
        except Exception:
            db.session.rollback()
            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='ISSUE_COUPON',
                resource=RESOURCE,
                status='failed',
            )
            raise

    # ---------- 顾客自领（券中心） ----------

    @staticmethod
    def _claim_blocked_reason(template, claimed_count):
        """这张券这个人**现在**能不能领；能领返回 None，不能返回原因

        和 `check()` 一个套路（返回原因而不是抛异常）：券中心要把不能领的券
        也列出来、并说清楚为什么，而不是干脆不显示——「有张券但我领不了」
        比「什么都没有」更让人觉得系统坏了。
        """
        if not template.is_claimable:
            return '这张券不是自领的'
        if template.status != CouponTemplate.STATUS_ACTIVE:
            return '这张券已经停发了'
        if template.is_expired:
            return '这张券已经过期了'

        # **还没生效的能领**：券中心里预告一张「国庆开始用」的券是正常做法，
        # 领到手在券包里显示「未生效」就行。只有过期的才拦
        if template.total_quantity is not None and template.issued.count() >= template.total_quantity:
            return '已经被领完了'
        if (template.per_member_limit is not None
                and claimed_count >= template.per_member_limit):
            return f'每人限领 {template.per_member_limit} 张'
        return None

    @staticmethod
    def _claimed_counts(member_id, template_ids):
        """这个人在这些模板上各领过几张

        `member_id` 为空 = 没登录，一律按 0 算（见 `get_claimable_templates`）

        **一次查完**，不要在循环里逐个 count——券中心一屏十几张券，
        那就是十几次查询。这和别处「人数撑死几十个，逐条过 check() 更好读」
        的判断不一样：这里是**按模板**查，模板数固定且会随运营增长，
        而且这个计数是纯 SQL 就能表达的（没有过期那类"算出来"的状态）
        """
        if not member_id or not template_ids:
            return {}
        rows = (db.session.query(UserCoupon.template_id, func.count(UserCoupon.id))
                .filter(UserCoupon.member_id == member_id,
                        UserCoupon.template_id.in_(template_ids))
                .group_by(UserCoupon.template_id)
                .all())
        return dict(rows)

    @staticmethod
    def get_claimable_templates(member_id):
        """券中心：有哪些券，以及这个人各能领几张

        **连不能领的也返回**（带 `blocked_reason`），理由见
        `_claim_blocked_reason`。

        `member_id` 传 None = 游客：券照列，`claimed_count` 一律 0。
        顾客端首页把它当「近期活动」用，不进登录墙（见 `member_optional`）。
        """
        templates = (CouponTemplate.query
                     .filter(CouponTemplate.is_claimable.is_(True))
                     .order_by(CouponTemplate.id.desc())
                     .all())
        claimed = CouponService._claimed_counts(member_id, [t.id for t in templates])

        result = []
        for template in templates:
            count = claimed.get(template.id, 0)
            reason = CouponService._claim_blocked_reason(template, count)
            result.append({
                **template.to_dict(),
                'claimed_count': count,
                'can_claim': reason is None,
                'blocked_reason': reason,
            })
        return result

    @staticmethod
    def claim(template_id, member):
        """顾客自己领一张券

        和员工发券（`issue`）**不是同一条路**，虽然最后都是建一条 `UserCoupon`：

            发券   可以一次给一批人、每人好几张、不看每人限领
            自领   一次一张、受每人限领约束、领完还要防他连点

        领到的券 `issued_by_name` 留空——那个字段的语义就是「谁发的，
        空 = 顾客自己领的」，所以自领不需要额外标记。
        """
        member_id = member.id

        template = CouponService.get_template_or_404(template_id)
        if not template.is_claimable:
            raise BusinessError('这张券不能自己领')

        # 锁住模板行再算总量和已领数——不锁的话两个人同时领最后一张，
        # 各自都看到「还剩 1 张」，结果发出去 2 张（和 issue 那边一个道理）
        db.session.execute(
            select(CouponTemplate).where(CouponTemplate.id == template_id).with_for_update()
        )

        count = (UserCoupon.query
                 .filter_by(template_id=template_id, member_id=member_id)
                 .count())
        reason = CouponService._claim_blocked_reason(template, count)
        if reason:
            raise BusinessError(reason)

        try:
            coupon = UserCoupon(
                template_id=template.id,
                member_id=member_id,
                received_at=datetime.now(timezone.utc),
            )
            db.session.add(coupon)
            db.session.commit()
            return coupon
        except Exception:
            db.session.rollback()
            raise

    # ---------- 查券 ----------

    @staticmethod
    def get_member_coupons(member_id, status=None, page=1, per_page=20):
        """某个会员的券包

        `status` 传 `unused` / `used` / `expired` / `not_started`——后两个
        **都是算出来的**，库里只存未用/已用（见 `UserCoupon.display_status`）。

        这里是**唯一**把「过期/未生效」翻译成 SQL 的地方，条件和
        `is_expired` / `not_started` 严格对应。别处（比如 `get_usable_coupons`）
        都是在 Python 里逐张过 `check()`——一个人手里撑死几十张券，过一遍比
        翻成 SQL 好读，也不会两边走偏。
        """
        query = (UserCoupon.query
                 .filter_by(member_id=member_id)
                 .options(joinedload(UserCoupon.template)))

        # 库里存的是不带时区的 UTC，SQL 里的比较也要用同样的形式
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        if status == UserCoupon.STATUS_USED:
            query = query.filter(UserCoupon.status == UserCoupon.STATUS_USED)
        elif status == 'expired':
            # 过期 = 没用过 且 valid_to 已经过了
            query = (query.filter(UserCoupon.status == UserCoupon.STATUS_UNUSED)
                     .join(CouponTemplate)
                     .filter(CouponTemplate.valid_to.isnot(None),
                             CouponTemplate.valid_to < now))
        elif status == 'not_started':
            query = (query.filter(UserCoupon.status == UserCoupon.STATUS_UNUSED)
                     .join(CouponTemplate)
                     .filter(CouponTemplate.valid_from.isnot(None),
                             CouponTemplate.valid_from > now))
        elif status == UserCoupon.STATUS_UNUSED:
            # 「未使用」= 没用过 **且 已生效 且 没过期**——顾客眼里的「可用券」
            # 不该混进过期的，也不该混进还没到生效时间的
            query = (query.filter(UserCoupon.status == UserCoupon.STATUS_UNUSED)
                     .join(CouponTemplate)
                     .filter(db.or_(CouponTemplate.valid_to.is_(None),
                                    CouponTemplate.valid_to >= now))
                     .filter(db.or_(CouponTemplate.valid_from.is_(None),
                                    CouponTemplate.valid_from <= now)))

        return (query.order_by(UserCoupon.id.desc())
                .paginate(page=page, per_page=per_page, error_out=False))

    @staticmethod
    def get_usable_coupons(member_id, store_id, amount):
        """这一单能用哪些券

        逐张过 `check()`——券的数量是「一个人手里有几张」，撑死几十张，
        在 Python 里过一遍比把四条规则翻译成 SQL 好读得多，也不会两边走偏。
        """
        amount = _money(amount)
        candidates = (UserCoupon.query
                      .filter_by(member_id=member_id, status=UserCoupon.STATUS_UNUSED)
                      .options(joinedload(UserCoupon.template))
                      .all())

        usable = []
        for coupon in candidates:
            if CouponService.check(coupon, store_id, amount) is None:
                usable.append(coupon)

        # 能抵得多的排前面——收银员多半想先看最划算的那张
        usable.sort(key=lambda c: c.template.discount_for(amount), reverse=True)
        return usable

    # ---------- 用券 ----------

    @staticmethod
    def check(coupon, store_id, amount):
        """这张券现在能不能用：能用返回 `None`，不能用返回**原因**

        **返回原因而不是抛异常**，因为「查这单能用哪些券」只是查、不是操作。
        真要用了再由 `use()` 把它抛出来。

        五个条件在这儿一次判完——散到各个调用点的话，迟早漏掉一个
        （最常见的是忘了判「这家店能不能用」）。
        里面「过期」和「还没生效」都是**现算的**，库里没有这两个状态。

        `amount` 传的是**商品原价**（`order.total_amount`），不是应付金额——
        「满 100」说的是消费了多少，不是抵扣完还剩多少。不然会出现
        「先用积分把金额降到 99，券就用不了了」，顾客只会觉得莫名其妙。
        """
        if coupon.status == UserCoupon.STATUS_USED:
            return '这张券已经用过了'

        if coupon.is_expired:
            return '这张券已经过期了'

        if coupon.not_started:
            return '这张券还没到生效时间'

        if not coupon.template.usable_at(store_id):
            return '这张券不适用于这家门店'

        min_amount = Decimal(coupon.template.min_amount)
        if _money(amount) < min_amount:
            return f'满 ¥{min_amount:.2f} 才能用这张券'

        if coupon.template.status == CouponTemplate.STATUS_DISABLED:
            # 停用只停「发」，已经发出去的不拦——但要说清楚，免得顾客以为券废了
            logger.info('券模板 %s 已停用，但顾客手里的这张照常能用', coupon.template_id)

        return None

    @staticmethod
    def use(coupon, order):
        """把券用在这笔订单上，返回抵了多少钱

        **门槛和折扣都按商品原价算**（`order.total_amount`），不看积分抵扣之后
        剩多少——两边各自独立优惠、都以原价为基数。这样先扣积分还是先用券
        结果一样，也不会出现「积分把金额降到门槛以下、券突然用不了」。

        **不 commit**——调用方多半在一个更大的事务里（下单），由它决定什么时候提交。
        和 `BalanceService.deduct` / `PointsService.redeem` 一个路子。
        """
        reason = CouponService.check(coupon, order.store_id, order.total_amount)
        if reason:
            raise BusinessError(reason)

        coupon.status = UserCoupon.STATUS_USED
        coupon.used_at = datetime.now(timezone.utc)
        coupon.used_order_id = order.id
        coupon.used_store_id = order.store_id
        return coupon.template.discount_for(order.total_amount)
