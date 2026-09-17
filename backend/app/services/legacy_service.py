"""老系统共存：ID 映射 + 同步记录

对账（「账对不对」）在 `reconciliation_service.py`；这里管的是另外两件事：
**「这条数据在对面叫什么」** 和 **「今天推过去的那批成没成」**。

四个动作，对应四个真实场景：

    bind        迁移时一条条记对应关系
    unbind      录错了要能改——但删之前一定留痕
    resolve     客服拿着老会员号来问「这是谁」（迁移完最常用的那个）
    record_sync 同步程序跑完一批，把结果记下来

**成功也要记同步记录**：只记失败的话，「今天到底推没推」没人答得上来——
没记录既可能是「跑了，全成功」，也可能是「压根没跑」。
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import func

from backend.app.errors import BusinessError, NotFoundError
from backend.app.extensions import db
from backend.app.models import Balance, LegacyMap, Member, SyncRecord
from backend.app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

RESOURCE = 'legacy'


def _operator(default_name='系统'):
    """这个模块里记审计时的操作人——迁移命令里没有登录用户，走「系统」"""
    return AuditService.current_operator(default_name)


class LegacyService:
    # 多态引用的代价：**数据库拦不住「映射指向一个不存在的对象」，
    # 只能在应用层拦**——所以这张表本身也得有个 类型 → 模型 的映射表，
    # bind 的时候挨个查一遍。加一种可映射的对象，这里跟着加一行
    TARGET_MODELS = {
        LegacyMap.TARGET_MEMBER: Member,
        LegacyMap.TARGET_BALANCE: Balance,
    }

    # ---------- 查映射 ----------

    @staticmethod
    def get_maps(page=1, per_page=10, target_type=None, search=None):
        """映射列表

        搜索只按**老系统的号**搜。想按会员姓名找的话得先按老号 join 到会员表，
        而 `target_id` 指向哪张表是运行时才知道的（多态），SQL 里 join 不了——
        真要支持得先查一边再回来查另一边，两次查询。现在不做。
        """
        query = LegacyMap.query
        if target_type:
            query = query.filter(LegacyMap.target_type == target_type)
        if search:
            # 老号存的是字符串，搜索也按字符串比——按数字比的话 'M001' 这种查不了
            query = query.filter(LegacyMap.legacy_id.ilike(f'%{search}%'))
        return (query.order_by(LegacyMap.id.desc())
                .paginate(page=page, per_page=per_page, error_out=False))

    @staticmethod
    def resolve(target_type, legacy_id):
        """拿老号查新对象；查不到返回 None（不是 404——「没迁过」是个正常答案）"""
        mapping = LegacyMap.query.filter_by(
            target_type=target_type, legacy_id=str(legacy_id),
        ).first()
        if mapping is None:
            return None
        model = LegacyService.TARGET_MODELS.get(target_type)
        return db.session.get(model, mapping.target_id) if model else None

    @staticmethod
    def resolve_member(legacy_id):
        """拿老会员号查新会员——客服那个场景"""
        return LegacyService.resolve(LegacyMap.TARGET_MEMBER, legacy_id)

    # ---------- 记映射 ----------

    @staticmethod
    def _assert_bindable(target_type, target_id, legacy_id):
        model = LegacyService.TARGET_MODELS.get(target_type)
        if model is None:
            raise BusinessError(f'不认识的对象类型：{target_type}')

        if not db.session.get(model, target_id):
            # 数据库没有外键拦得住这一条（target_id 是多态的），只能在这儿拦
            raise NotFoundError(f'要映射的对象不存在（{target_type} id={target_id}）')

        legacy_id = str(legacy_id)
        # 两个方向都查一遍。数据库上的唯一索引是最后一道保险（并发下才用得上），
        # 这里先查是为了把话说清楚——撞唯一索引报出来的错很难懂
        if LegacyMap.query.filter_by(target_type=target_type, legacy_id=legacy_id).first():
            raise BusinessError(f'老系统的号 {legacy_id} 已经映射过了')
        if LegacyMap.query.filter_by(target_type=target_type, target_id=target_id).first():
            raise BusinessError('这个对象已经有一个老系统的号了')

        return legacy_id

    @staticmethod
    def bind(target_type, target_id, legacy_id, remark='', operator_name=None):
        """记一条对应关系；返回落库后的映射"""
        legacy_id = LegacyService._assert_bindable(target_type, target_id, legacy_id)
        operator_id, name = _operator(operator_name or '系统迁移')

        try:
            mapping = LegacyMap(
                target_type=target_type, target_id=target_id,
                legacy_id=legacy_id, remark=remark,
            )
            db.session.add(mapping)
            db.session.flush()

            AuditService.log(
                operator_id=operator_id, operator_name=name,
                action='BIND_LEGACY_ID', resource=RESOURCE, status='success',
                new_value=mapping.to_dict(),
            )
            return mapping
        except Exception:
            db.session.rollback()
            AuditService.log(
                operator_id=operator_id, operator_name=name,
                action='BIND_LEGACY_ID', resource=RESOURCE, status='failed',
            )
            raise

    @staticmethod
    def unbind(map_id):
        """删掉一条映射——**只在录错的时候用**

        删之前一定留痕：映射是「这条老数据迁到哪去了」的唯一线索，
        删掉之后没有第二个地方能查回来。
        正常迁移过的映射不该删，真迁错了该删的是迁过来的那条数据。
        """
        mapping = db.session.get(LegacyMap, map_id)
        if not mapping:
            raise NotFoundError('映射不存在')

        operator_id, name = _operator()
        old_value = mapping.to_dict()
        try:
            db.session.delete(mapping)
            AuditService.log(
                operator_id=operator_id, operator_name=name,
                action='UNBIND_LEGACY_ID', resource=RESOURCE, status='success',
                old_value=old_value,
            )
            db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            AuditService.log(
                operator_id=operator_id, operator_name=name,
                action='UNBIND_LEGACY_ID', resource=RESOURCE, status='failed',
            )
            raise

    # ---------- 同步记录 ----------

    @staticmethod
    def get_sync_records(page=1, per_page=10, direction=None, target=None,
                         category=None, status=None):
        query = SyncRecord.query
        if direction:
            query = query.filter(SyncRecord.direction == direction)
        if target:
            query = query.filter(SyncRecord.target == target)
        if category:
            query = query.filter(SyncRecord.category == category)
        if status:
            query = query.filter(SyncRecord.status == status)
        return (query.order_by(SyncRecord.synced_at.desc(), SyncRecord.id.desc())
                .paginate(page=page, per_page=per_page, error_out=False))

    @staticmethod
    def record_sync(direction, category, ref, status=SyncRecord.STATUS_SUCCESS,
                    target='legacy_saas', message='', synced_at=None):
        """记一次同步动作

        **不 commit**——调用方多半在一批数据里连着记好几条，
        由它决定什么时候提交。迁移命令是**一条一提交**的：
        中途挂掉时已经过去的那几条要留着，下次接着跑（这也让迁移天然可重入）。
        """
        record = SyncRecord(
            direction=direction, target=target, category=category, status=status,
            ref=ref, message=message,
            synced_at=synced_at or datetime.now(timezone.utc),
        )
        db.session.add(record)
        return record

    @staticmethod
    def sync_summary(since=None):
        """同步汇总——「一共多少条、几条失败」

        页面上第一眼要看的就是这几个数，而不是一屏一屏往下翻。
        `since` 传一个时间点就只统计那以后的（传 None 是全部）。
        """
        query = db.session.query(SyncRecord.status, func.count(SyncRecord.id))
        if since is not None:
            query = query.filter(SyncRecord.synced_at >= since)
        counts = dict(query.group_by(SyncRecord.status).all())
        return {
            'success': counts.get(SyncRecord.STATUS_SUCCESS, 0),
            'failed': counts.get(SyncRecord.STATUS_FAILED, 0),
            'pending': counts.get(SyncRecord.STATUS_PENDING, 0),
            'total': sum(counts.values()),
        }
