"""老系统共存：ID 映射 + 同步记录 + 对账记录

二期第 5 条，也是设计文档「必须守住的 6 条」里的第 6 条。灰度切换期间新老两套
系统并行跑，这三张表就是让两边**对得上**的东西。

三张表各自解决什么
------------------

**LegacyMap**——「老系统里的 10086 号会员，是新系统的 37 号」。
迁移是一次性的动作，但**查这个对应关系是长期的事**：老系统还要跑一阵子，
客服拿着老会员号来问、对账对不上要倒查，都得能查回来。
所以它不是迁移脚本里的临时表。

**SyncRecord**——「今天 03:00 推给 ERP 的 128 条订单，3 条失败，原因是超时」。
同步是**一次次动作**，各自有状态、时间和失败原因。它是日志，不是配置——
所以它只增不改（除非重试）。

**Reconciliation**——「昨天解放路店的实收，账上记的和流水累加的差 0.01 元」。
对账是**每天跑一次、结论要留档**的事：昨天的结论今天不能变，
不然「昨天对得上、今天对不上」这种趋势就看不出来了。

对账对的是哪两边的数
--------------------

**这个项目里没有真的老系统**，所以对账只做了「自己跟自己」的那一半：

    储值   账上余额   vs  流水累加
    订单   订单实收   vs  支付流水

另一半——拿老系统的日报跟我们的营业额比——**需要外部数据源，没有就是编**，
所以没做，README 里也如实标了。但这一半同样有用：设计文档说储值那 80 万要
「一分不差」，第一步就得先证明**新系统自己记的账和流水是自洽的**。
账都自己跟自己对不起，跟别人比更没有意义。
"""
from datetime import datetime, timezone

from backend.app.extensions import db
from backend.app.models.base import BaseModel


class LegacyMap(BaseModel):
    """老系统 ID ↔ 新系统 ID"""
    __tablename__ = 'legacy_map'

    TARGET_MEMBER = 'member'
    TARGET_BALANCE = 'balance'
    TARGET_LABELS = {
        TARGET_MEMBER: '会员',
        TARGET_BALANCE: '储值账户',
    }

    target_type = db.Column(db.String(20), nullable=False, index=True)
    target_id = db.Column(db.Integer, nullable=False, index=True)
    # 老系统的 id 存成**字符串**：它可能是自增数字，也可能是 'M0010086' 这种会员号，
    # 甚至两个系统的号段规则都不一样。存字符串就不用赌老系统那边是什么类型
    legacy_id = db.Column(db.String(64), nullable=False, index=True)
    remark = db.Column(db.String(255), nullable=False, default='')

    __table_args__ = (
        # 两个方向都得唯一：一个老号不能对上新系统的两个人，一个新会员也不该
        # 同时挂两个老号——真出现，说明迁移跑重了，该在插进来的时候就报错
        db.UniqueConstraint('target_type', 'legacy_id', name='uq_legacy_map_legacy_id'),
        db.UniqueConstraint('target_type', 'target_id', name='uq_legacy_map_target_id'),
    )

    # **没有外键，是故意的**：target_id 指向哪张表由 target_type 决定（多态引用），
    # 数据库层面建不了约束。代价是「映射指向一个已经被删掉的对象」数据库不会拦——
    # 但迁过来的会员本来就不会删（会员是停用不是删除）。
    # 换来的是「以后要给订单、菜品也加映射」不用改表结构、也不用再开两张表

    def to_dict(self):
        return {
            'id': self.id,
            'target_type': self.target_type,
            'target_type_label': self.TARGET_LABELS.get(self.target_type, self.target_type),
            'target_id': self.target_id,
            'legacy_id': self.legacy_id,
            'remark': self.remark,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SyncRecord(BaseModel):
    """一次同步动作的记录"""
    __tablename__ = 'sync_record'

    DIRECTION_PUSH = 'push'     # 我们推给老系统/ERP
    DIRECTION_PULL = 'pull'     # 从老系统/ERP 拉过来
    DIRECTION_LABELS = {
        DIRECTION_PUSH: '推出去',
        DIRECTION_PULL: '拉进来',
    }

    TARGET_LABELS = {
        'legacy_saas': '老 SaaS',
        'erp': 'ERP',
    }

    CATEGORY_LABELS = {
        'order': '订单',
        'member': '会员',
        'balance': '储值',
        'stock': '库存',
    }

    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_PENDING = 'pending'
    STATUS_LABELS = {
        STATUS_SUCCESS: '成功',
        STATUS_FAILED: '失败',
        STATUS_PENDING: '待重试',
    }

    direction = db.Column(db.String(10), nullable=False, index=True)
    target = db.Column(db.String(32), nullable=False, default='legacy_saas', index=True)
    category = db.Column(db.String(20), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_SUCCESS, index=True)
    # 这条同步的是**哪一条数据**：单号、会员号、或者「2026-09-16 解放路店日报」。
    # 列表上要能一眼看出是**哪条**失败了，只报「失败了 3 条」等于没说
    ref = db.Column(db.String(128), nullable=False, default='')
    # 失败原因。**原样留着不翻译**——排障的时候看的正是原文，
    # 翻译成「同步失败了」反而把唯一的线索抹掉了
    message = db.Column(db.String(255), nullable=False, default='')
    synced_at = db.Column(db.DateTime, nullable=False,
                          default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'direction': self.direction,
            'direction_label': self.DIRECTION_LABELS.get(self.direction, self.direction),
            'target': self.target,
            'target_label': self.TARGET_LABELS.get(self.target, self.target),
            'category': self.category,
            'category_label': self.CATEGORY_LABELS.get(self.category, self.category),
            'status': self.status,
            'status_label': self.STATUS_LABELS.get(self.status, self.status),
            'ref': self.ref,
            'message': self.message,
            'synced_at': self.synced_at.isoformat() if self.synced_at else None,
        }


class Reconciliation(BaseModel):
    """对账记录：某天某店某个类别，账上的数和按流水重算的数对不对得上"""
    __tablename__ = 'reconciliation'

    CATEGORY_ORDER = 'order'
    CATEGORY_BALANCE = 'balance'
    CATEGORY_LABELS = {
        CATEGORY_ORDER: '订单',
        CATEGORY_BALANCE: '储值',
    }

    STATUS_MATCHED = 'matched'
    STATUS_MISMATCHED = 'mismatched'
    STATUS_LABELS = {
        STATUS_MATCHED: '对得上',
        STATUS_MISMATCHED: '有差异',
    }

    # 业务日期——**本地自然日，不是 UTC 日期**。
    # 「昨天做了多少生意」问的是店里墙上那个日历，订单号里的日期也是本地日期，
    # 两边得是同一个口径（`OrderService` 生成单号时用的就是本地日期）
    biz_date = db.Column(db.Date, nullable=False, index=True)

    # 储值不挂门店（会员全公司通用），所以可空；订单对账按门店，必填。
    #
    # **没加唯一约束**，虽然「同一天同一店同一类别只该有一条」是对的：
    # MySQL 的唯一索引不拦 NULL，储值那条（store_id 为空）照样能插进去好几行，
    # 一个只对一半生效的约束比没有更误导人。唯一性交给 service 保证
    # （每次跑对账先删同键的旧记录，反正对账的语义就是「重新下一遍结论」）
    store_id = db.Column(
        db.Integer, db.ForeignKey('store.id', ondelete='RESTRICT'), nullable=True, index=True,
    )
    store = db.relationship('Store', backref=db.backref('reconciliations', lazy='dynamic'))

    category = db.Column(db.String(20), nullable=False, index=True)

    # **期望值** = 按流水重算出来的（原始凭证派生的）
    # **实际值** = 账上现在记着的数
    # **差异** = 实际 − 期望：正数就是账上比流水多出来的
    expected_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    actual_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    diff_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    status = db.Column(db.String(20), nullable=False, default=STATUS_MATCHED, index=True)

    # 有几处对不上。**和 `diff_amount` 是两回事**：
    # 一个会员多 100、一个会员少 100，差异合计是 0，但这两个人的账都是错的。
    # 只看金额的话这种账会被判成「对得上」——这个字段就是为了让它露出来
    mismatch_count = db.Column(db.Integer, nullable=False, default=0)

    # 差异明细（前若干条）：**留 JSON，不另开一张明细表**——它是「当时算出来的
    # 快照」，明天再算可能就变了，留档的意义正是保住当时的样子。
    # 真要查原始记录该去查流水，在这儿复制一份流水只是重复存储
    detail = db.Column(db.JSON, nullable=True)

    checked_at = db.Column(db.DateTime, nullable=False,
                           default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'biz_date': self.biz_date.isoformat() if self.biz_date else None,
            'store_id': self.store_id,
            'store_name': self.store.name if self.store else '全公司',
            'category': self.category,
            'category_label': self.CATEGORY_LABELS.get(self.category, self.category),
            'expected_amount': float(self.expected_amount),
            'actual_amount': float(self.actual_amount),
            'diff_amount': float(self.diff_amount),
            'status': self.status,
            'status_label': self.STATUS_LABELS.get(self.status, self.status),
            'mismatch_count': self.mismatch_count,
            'detail': self.detail or [],
            'checked_at': self.checked_at.isoformat() if self.checked_at else None,
        }
