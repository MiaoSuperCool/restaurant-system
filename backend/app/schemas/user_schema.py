from marshmallow import Schema, fields, validate


class UserCreateSchema(Schema):
    username = fields.Str(required=True, validate=validate.Length(min=2, max=80))
    real_name = fields.Str(required=True, validate=validate.Length(min=1, max=80))
    email = fields.Email(required=True, validate=validate.Length(max=80))
    mobile = fields.Str(required=True, validate=validate.Length(min=6, max=80))
    password = fields.Str(required=True, validate=validate.Length(min=6, max=128))
    is_active = fields.Boolean(load_default=True)
    is_admin = fields.Boolean(load_default=False)


class UserUpdateSchema(Schema):
    username = fields.Str(validate=validate.Length(min=2, max=80))
    real_name = fields.Str(validate=validate.Length(min=1, max=80))
    email = fields.Email(validate=validate.Length(max=80))
    mobile = fields.Str(validate=validate.Length(min=6, max=80))
    password = fields.Str(validate=validate.Length(min=6, max=128))
    is_active = fields.Boolean()
    is_admin = fields.Boolean()
