"""门店的请求参数 schema

枚举校验用 validate.OneOf(Store.XXX_LABELS)：把合法取值锁在模型定义的那份常量上，
避免 schema 和各处硬编码的字符串各写各的。
"""
from marshmallow import Schema, fields, validate

from backend.app.models.store import Store
from backend.app.schemas.validators import one_of


class StoreCreateSchema(Schema):
    code = fields.Str(
        required=True,
        validate=validate.Length(min=2, max=32),
        metadata={'description': '门店编码（对接用，创建后慎改，如 S001）'},
    )
    name = fields.Str(required=True, validate=validate.Length(min=1, max=80))
    store_type = fields.Str(load_default=Store.TYPE_DINE_IN, validate=one_of(Store.TYPE_LABELS))
    address = fields.Str(load_default='', validate=validate.Length(max=255))
    phone = fields.Str(load_default='', validate=validate.Length(max=20))
    description = fields.Str(
        load_default='', validate=validate.Length(max=255),
        metadata={'description': '一句话介绍，给顾客看的；内部备注请用 remark'},
    )
    business_hours = fields.Str(
        load_default='', validate=validate.Length(max=64),
        metadata={'description': '营业时间，如 09:00-22:00'},
    )
    business_status = fields.Str(load_default=Store.STATUS_OPEN, validate=one_of(Store.STATUS_LABELS))
    run_mode = fields.Str(load_default=Store.MODE_NEW, validate=one_of(Store.MODE_LABELS))
    remark = fields.Str(load_default='', validate=validate.Length(max=255))


class StoreUpdateSchema(Schema):
    """只传需要改的字段（未出现的字段一律不动）"""

    code = fields.Str(validate=validate.Length(min=2, max=32))
    name = fields.Str(validate=validate.Length(min=1, max=80))
    store_type = fields.Str(validate=one_of(Store.TYPE_LABELS))
    address = fields.Str(validate=validate.Length(max=255))
    phone = fields.Str(validate=validate.Length(max=20))
    description = fields.Str(validate=validate.Length(max=255))
    business_hours = fields.Str(validate=validate.Length(max=64))
    business_status = fields.Str(validate=one_of(Store.STATUS_LABELS))
    run_mode = fields.Str(validate=one_of(Store.MODE_LABELS))
    remark = fields.Str(validate=validate.Length(max=255))
