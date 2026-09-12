from marshmallow import Schema, fields, validate

from backend.app.models.staff import Staff
from backend.app.schemas.validators import one_of


class StaffCreateSchema(Schema):
    username = fields.Str(required=True, validate=validate.Length(min=2, max=80))
    real_name = fields.Str(required=True, validate=validate.Length(min=1, max=80))
    email = fields.Email(required=True, validate=validate.Length(max=80))
    mobile = fields.Str(required=True, validate=validate.Length(min=6, max=80))
    password = fields.Str(required=True, validate=validate.Length(min=6, max=128))

    store_id = fields.Integer(
        load_default=None,
        allow_none=True,
        metadata={'description': '归属门店 id；总部账号（运营/财务/老板）留空'},
    )
    employment_type = fields.Str(
        load_default=Staff.TYPE_FULL_TIME,
        validate=one_of(Staff.TYPE_LABELS),
        metadata={'description': '用工类型：全职 / 兼职'},
    )
    role_ids = fields.List(
        fields.Integer(),
        load_default=list,
        metadata={'description': '角色 id 列表；权限和数据范围都由角色决定'},
    )
    is_shared = fields.Boolean(
        load_default=False,
        metadata={'description': '公用账号（服务员共用设备登录）'},
    )
    is_active = fields.Boolean(load_default=True)
    is_admin = fields.Boolean(
        load_default=False,
        metadata={'description': '超级管理员，绕过权限码检查'},
    )


class StaffUpdateSchema(Schema):
    """只传需要改的字段"""

    username = fields.Str(validate=validate.Length(min=2, max=80))
    real_name = fields.Str(validate=validate.Length(min=1, max=80))
    email = fields.Email(validate=validate.Length(max=80))
    mobile = fields.Str(validate=validate.Length(min=6, max=80))
    password = fields.Str(validate=validate.Length(min=6, max=128))
    store_id = fields.Integer(allow_none=True)
    employment_type = fields.Str(validate=one_of(Staff.TYPE_LABELS))
    role_ids = fields.List(fields.Integer())
    is_shared = fields.Boolean()
    is_active = fields.Boolean()
    is_admin = fields.Boolean()
