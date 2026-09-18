"""排班的请求 schema

时间一律走 `'HH:MM'` 字符串（不是 `fields.Time`）：前端 `<el-time-picker>` 和
小程序 `<picker mode="time">` 给的本来就是这种串，转成 `datetime.time`
再转回来只会多两处出错的地方。真正的解析和先后校验在 service 的
`_parse_times` 里。
"""

from marshmallow import Schema, fields, validate


class ShiftCreateSchema(Schema):
    """新建班次"""

    name = fields.String(
        required=True,
        validate=validate.Length(min=1, max=32, error='班次名字 1-32 个字'),
        metadata={'description': '「早班」「晚班」这种，同一家店不能重名'},
    )
    start_time = fields.String(
        required=True,
        validate=validate.Regexp(r'^\d{1,2}:\d{2}$', error='时间写成 HH:MM，比如 09:00'),
    )
    end_time = fields.String(
        required=True,
        validate=validate.Regexp(r'^\d{1,2}:\d{2}$', error='时间写成 HH:MM，比如 14:00'),
    )
    sort_order = fields.Integer(
        load_default=0,
        metadata={'description': '小的排前面；班表里也按这个顺序显示'},
    )


class ShiftUpdateSchema(Schema):
    """改班次——**每一项都可选**，只改传上来的

    `is_active=False` 是「以后不再排这个班」：已经排出去的记录照旧，
    和券模板的停用一个道理。
    """

    name = fields.String(validate=validate.Length(min=1, max=32, error='班次名字 1-32 个字'))
    start_time = fields.String(validate=validate.Regexp(r'^\d{1,2}:\d{2}$'))
    end_time = fields.String(validate=validate.Regexp(r'^\d{1,2}:\d{2}$'))
    is_active = fields.Boolean()
    sort_order = fields.Integer()


class WeekQuerySchema(Schema):
    """看哪一周"""

    day = fields.Date(
        required=False,
        metadata={'description': '这一周里的任意一天；不传 = 本周。'
                                 '**不传具体某天也行**，周几会自动折到周一'},
    )


class SetDaySchema(Schema):
    """排一个人一天的班

    `shift_ids` 是**这一天的完整答案**（不是增量）：传 `[早班id, 晚班id]`
    表示这天两个班都上，传 `[]` 表示这天休息。按 id 对齐，多的删、少的加。
    """

    staff_id = fields.Integer(
        required=True,
        metadata={'description': '只能排本店的在职员工'},
    )
    work_date = fields.Date(required=True)
    shift_ids = fields.List(
        fields.Integer(),
        load_default=list,
        metadata={'description': '这天要上的班次 id；空数组 = 休息'},
    )


class MyScheduleQuerySchema(Schema):
    """「我的班表」看多久"""

    days = fields.Integer(
        load_default=14,
        validate=validate.Range(min=1, max=60, error='最多看 60 天'),
        metadata={'description': '从今天起往后看几天（含今天）'},
    )
