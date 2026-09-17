"""老系统迁移：把老 SaaS 导出来的会员和储值搬进新系统

**为什么单独一个模块，不塞进 `demo.py`**：演示数据是「造一个像样的系统出来」，
迁移是「把真实的存量数据搬过来」——性质不一样，一个命令把两件事都办了，
演示的时候就讲不清究竟发生了什么。

`seed-demo --reset` **会连迁移结果一起清掉**（迁移过来的会员就是会员，会员被清了，
ID 映射就成了指向空气的孤儿记录）。所以清完要把这条命令和 `reconcile` 补跑一遍，
`--reset` 的提示里也写了这一点。

迁移最难的不是搬数据，是**搬完之后敢说「一分不差」**
----------------------------------------------------

所以这个过程里做了三件事，分别对应三张表：

    记 ID 映射    搬完之后还要能查回来（客服拿着老会员号来问）
    记同步记录    每一条都要有交代，包括没迁成的那几条
    储值带老单号  流水上留 `legacy_no`，对账对不上时能倒查

**幂等**：按老系统的号认领，跑第二遍一条都不会重复迁。
"""
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

# 假装这是从老 SaaS 导出来的会员表
#
# 真做迁移时这里是一份 CSV —— 换掉这个常量就行，下面的逻辑不用动。
# 几个数是**特意留的**，对应迁移时真正会撞上的三种情况：
#
#   M0001003  手机号在新系统里已经有了（新老系统同一个顾客）→ 认领，不新建
#   M0001005  老系统里同一个手机号挂在两个号下面，而且第一个已经迁过了
#             → **不能猜**，记一条失败让人来处理
#   M0001001  有储值余额，迁移时要连账户带流水一起建，流水上留老单号
LEGACY_MEMBERS = [
    # (老系统的会员号, 手机号, 昵称, 储值余额)
    ('M0001001', '13900139001', '周建国', '1280.50'),
    ('M0001002', '13900139002', '吴美玲', '360.00'),
    ('M0001003', '13800138002', '李先生', '0'),
    ('M0001005', '13900139001', '重复号（老系统里录重了）', '0'),
]

# 从哪个系统搬、往哪个方向。写死在这里，将来真接 ERP 时从配置来
SOURCE = 'legacy_saas'


def _migrate_member(legacy_id, mobile, nickname, amount):
    """迁一个会员，返回 (member, action, 迁过来的储值)

    action 是 created / claimed / skipped 三种之一，用来在最后报数。
    迁不动的时候抛 BusinessError——调用方负责记一条失败的同步记录。
    """
    from backend.app.errors import BusinessError
    from backend.app.extensions import db
    from backend.app.models import LegacyMap, Member
    from backend.app.services import BalanceService, LegacyService

    # 幂等：这个老号迁过了就不再动
    if LegacyService.resolve_member(legacy_id):
        return None, 'skipped', Decimal('0')

    member = Member.query.filter_by(mobile=mobile).first()
    if member:
        # **认领有个前提**：这个新会员身上还没有别的老号。
        # 否则就是老系统里两个人共用一个手机号，而我们前面已经把人迁进来了——
        # 这时候「认领」会把两个老会员悄悄并成一个人，储值也跟着并到一起。
        # 这种账错了看不出来，只能在这儿拦住，让人工去核
        already = LegacyMap.query.filter_by(
            target_type=LegacyMap.TARGET_MEMBER, target_id=member.id,
        ).first()
        if already:
            raise BusinessError(
                f'手机号 {mobile} 在老系统里挂在两个会员号下面'
                f'（{already.legacy_id} 和 {legacy_id}），得先人工核实哪个是对的'
            )
        action = 'claimed'
    else:
        member = Member(mobile=mobile, nickname=nickname)
        db.session.add(member)
        db.session.flush()          # 下面建映射和账户都要用 id
        action = 'created'

    LegacyService.bind(
        LegacyMap.TARGET_MEMBER, member.id, legacy_id,
        remark='从老 SaaS 迁入' if action == 'created' else '老系统会员，认领新系统已有档案',
        operator_name='系统迁移',
    )

    # 储值：**走 service，不自己拼模型对象**
    #
    # 「迁进来的钱一律进本金、类型记 migrate、必须带老系统单号」这些规矩写在
    # `BalanceService.migrate` 里（老系统分不清本金和赠送，我们也别替它猜）。
    # 在这里再写一遍，迟早两处对不上——对账对的正是这个
    migrated = Decimal(amount)
    if migrated > 0:
        if member.balance:
            # 认领来的会员新系统里已经有储值了。两边都算上会把钱凭空放大，
            # 所以一分不动，让差异自己在对账里显出来
            logger.warning('会员 %s 新系统里已有储值，跳过金额迁移', member.id)
        else:
            BalanceService.migrate(
                member.id, migrated, legacy_no=f'LEGACY-{legacy_id}',
                remark='从老系统迁入的储值余额',
            )
            return member, action, migrated

    return member, action, Decimal('0')


def import_legacy():
    """跑一次迁移，返回一份统计给 CLI 打印用

    **一条一提交**：中途挂掉时，已经过去的那几条要留下来，
    下次接着跑（这也让迁移天然可重入——迁过的会被跳过）。
    """
    from backend.app.errors import BusinessError
    from backend.app.extensions import db
    from backend.app.models import SyncRecord
    from backend.app.services import LegacyService

    stats = {'created': 0, 'claimed': 0, 'skipped': 0, 'failed': 0,
             'migrated_amount': Decimal('0')}

    for legacy_id, mobile, nickname, amount in LEGACY_MEMBERS:
        try:
            member, action, migrated = _migrate_member(legacy_id, mobile, nickname, amount)

            if action == 'skipped':
                # 跳过也要记一条：**只记失败的话，「这次跑没跑」没人说得清**
                LegacyService.record_sync(
                    direction='pull', category='member', ref=legacy_id,
                    status=SyncRecord.STATUS_SUCCESS, target=SOURCE,
                    message='老号已经迁过，跳过',
                )
            else:
                LegacyService.record_sync(
                    direction='pull', category='member', ref=legacy_id,
                    status=SyncRecord.STATUS_SUCCESS, target=SOURCE,
                    message=f'{"新建档案" if action == "created" else "认领已有档案"}，'
                            f'储值迁入 ¥{migrated:.2f}',
                )
            db.session.commit()

            stats[action] += 1
            stats['migrated_amount'] += migrated
        except BusinessError as exc:
            # 迁移里的「失败」多半是数据本身有问题（对不上、冲突、缺字段），
            # **不是程序 bug**——所以记下来接着走下一条，不要整批回滚。
            # 整批回滚的话，一条脏数据就会卡住整个迁移
            db.session.rollback()
            LegacyService.record_sync(
                direction='pull', category='member', ref=legacy_id,
                status=SyncRecord.STATUS_FAILED, target=SOURCE, message=str(exc),
            )
            db.session.commit()
            stats['failed'] += 1
            logger.warning('老会员 %s 迁移失败：%s', legacy_id, exc)

    logger.info('老系统迁移完成：%s', stats)
    return stats
