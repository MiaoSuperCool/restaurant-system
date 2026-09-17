"""老系统共存的请求 schema：ID 映射、同步记录、对账"""
import datetime

from marshmallow import Schema, fields, validate

from backend.app.models.legacy import LegacyMap, Reconciliation, SyncRecord
from backend.app.schemas.query_schema import PageQuerySchema
from backend.app.schemas.validators import one_of


class LegacyMapQuerySchema(PageQuerySchema):
    """映射列表的查询参数"""

    target_type = fields.Str(
        required=False,
        validate=one_of(LegacyMap.TARGET_LABELS),
        metadata={'description': 'member / balance；不传 = 全部'},
    )


class LegacyMapCreateSchema(Schema):
    """手工补一条映射

    迁移程序会自动记，这个接口是给**人工补录**用的：
    老系统里后来才补录的会员、或者迁移时漏掉的个别人。
    """

    target_type = fields.Str(required=True, validate=one_of(LegacyMap.TARGET_LABELS))
    target_id = fields.Integer(required=True)
    legacy_id = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=64),
        metadata={'description': '老系统那边的号，原样存成字符串'},
    )
    remark = fields.Str(load_default='', validate=validate.Length(max=255))


class LegacyResolveQuerySchema(Schema):
    """按老号查新对象"""

    legacy_id = fields.Str(required=True)
    target_type = fields.Str(
        load_default=LegacyMap.TARGET_MEMBER,
        validate=one_of(LegacyMap.TARGET_LABELS),
    )


class SyncRecordQuerySchema(PageQuerySchema):
    """同步记录列表的查询参数"""

    direction = fields.Str(required=False, validate=one_of(SyncRecord.DIRECTION_LABELS))
    target = fields.Str(required=False, validate=one_of(SyncRecord.TARGET_LABELS))
    category = fields.Str(required=False, validate=one_of(SyncRecord.CATEGORY_LABELS))
    status = fields.Str(required=False, validate=one_of(SyncRecord.STATUS_LABELS))


class ReconciliationQuerySchema(PageQuerySchema):
    """对账记录的查询参数"""

    category = fields.Str(required=False, validate=one_of(Reconciliation.CATEGORY_LABELS))
    status = fields.Str(required=False, validate=one_of(Reconciliation.STATUS_LABELS))
    store_id = fields.Integer(required=False)
    biz_date = fields.Date(required=False)


class ReconciliationRunSchema(Schema):
    """跑一次对账

    `biz_date` 不传就是今天。**储值那条只认「此刻」**（`Balance` 没有历史快照），
    传历史日期对它没有意义，传了也只是给结论贴个标签——这一点在
    `ReconciliationService` 的注释里写清楚了。
    """

    category = fields.Str(required=True, validate=one_of(Reconciliation.CATEGORY_LABELS))
    biz_date = fields.Date(
        load_default=lambda: datetime.date.today(),
        metadata={'description': '业务日期（本地自然日）；不传 = 今天'},
    )
    store_id = fields.Integer(
        required=False,
        allow_none=True,
        load_default=None,
        metadata={'description': '订单对账必传；储值对账传了也会被忽略（储值不挂门店）'},
    )
