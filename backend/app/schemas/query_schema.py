"""列表接口的通用查询参数 schema

由 flask-smorest 的 @bp.arguments(schema, location='query') 引用：
一个 schema 同时承担"运行时参数校验"和"OpenAPI 文档生成"两件事，
改参数结构只改这一处，文档不会过期（这正是 smorest 替代手写 docstring 的价值）。
"""
from marshmallow import Schema, fields, validate


class PageQuerySchema(Schema):
    """分页 + 关键字搜索（users / audit 等列表接口共用）"""

    page = fields.Integer(
        load_default=1,
        validate=validate.Range(min=1),
        metadata={'description': '页码，从 1 开始'},
    )
    per_page = fields.Integer(
        required=False,
        metadata={'description': '每页条数；不传则用后端配置的 DEFAULT_PAGE_SIZE'},
    )
    search = fields.String(
        required=False,
        metadata={'description': '关键字（不同接口搜索的字段不同，见各自接口说明）'},
    )
