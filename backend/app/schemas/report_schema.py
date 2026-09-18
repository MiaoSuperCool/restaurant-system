"""经营报表的请求 schema"""
import datetime

from marshmallow import Schema, fields, validate


class ReportQuerySchema(Schema):
    """报表的查询参数

    时间有两种给法：给 `days`（最近 N 天，含今天），或者给 `start` / `end`。
    **两个都传的话以 start/end 为准**——选了具体日期又传了 days 是自相矛盾的，
    按更明确的那个来。
    """

    days = fields.Integer(
        load_default=7,
        validate=validate.Range(min=1, max=90, error='最多往回看 90 天'),
        metadata={'description': '最近 N 天（含今天）；传了 start/end 就忽略它'},
    )
    start = fields.Date(
        required=False,
        metadata={'description': '起始业务日 YYYY-MM-DD'},
    )
    end = fields.Date(
        required=False,
        load_default=lambda: datetime.date.today(),
        metadata={'description': '结束业务日（含当天）；默认今天'},
    )
    store_id = fields.Integer(
        required=False,
        metadata={'description': '看某一家店；不传 = 数据范围内全部。'
                                 '**超出数据范围会被 403 拦掉**'},
    )
