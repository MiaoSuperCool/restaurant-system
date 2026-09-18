"""排班：班次 + 谁哪天上了哪个班

**这不是考勤。** 排班回答的是「下周三谁上早班、谁上晚班」，
而不是「昨天张三几点几分打的卡」。打卡要设备、要跟工资挂钩、要处理补卡，
是另一个系统的事——这里只管**把班排出来**。

为什么两张表
------------

    班次 ShiftTemplate    这家店约定俗成的那几个班：早班 09:00-14:00、晚班 16:00-21:00
    排班 ShiftAssignment  哪天、谁、上哪个班

合成一张的话，每次排班都要重填一遍起止时间——而「早班」在今天和下周是同一个
时间。而且改一次班次时间就得改一批排班记录，改漏一条就出现两个「早班」
（一个 9 点开始、一个 9 点半开始），那种错看不出来。

**班次是门店级的**：西溪印象城店 10:30 才开门，它的「早班」和别人不是一个时间。
所以班次挂在门店上，不是全公司一套。

为什么 `ShiftAssignment` 上冗余了 `store_id`
--------------------------------------------

员工有 `store_id`、班次也有 `store_id`，照理说不用再存一遍。但这个字段是**故意的**：

排班记的是「**那天**张三在解放路店上早班」。张三下个月调到武林门店之后，
没有这个字段的话，他过去所有的排班都会被算到武林门店头上——
查「解放路店上个月的排班」会少一个人，而这个人当时明明在那儿。

一句话：**排班是历史，历史不能跟着人走。**
"""
from backend.app.extensions import db
from backend.app.models.base import BaseModel


class ShiftTemplate(BaseModel):
    """班次：门店里约定俗成的那几个"""
    __tablename__ = 'shift_template'

    # ondelete='RESTRICT'：排过班的班次不能删，只能停用——
    # 「早班」这个名字底下挂着几十条排班记录，删了那些记录就没头没尾了
    store_id = db.Column(
        db.Integer, db.ForeignKey('store.id', ondelete='RESTRICT'), nullable=False, index=True,
    )
    store = db.relationship('Store', backref=db.backref('shifts', lazy='dynamic'))

    name = db.Column(db.String(32), nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)

    # 停用只停「以后不再排这个班」，已经排出去的记录照旧——
    # 和券模板那个「停用只停发」是一个道理
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    sort_order = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (
        # 同一家店不能有两个同名的班次——不然排班的下拉里会出现两个「早班」，
        # 选哪个全靠猜
        db.UniqueConstraint('store_id', 'name', name='uq_shift_template_store_name'),
    )

    @property
    def time_range(self):
        """「09:00-14:00」，列表和下拉里都用它"""
        return f'{self.start_time.strftime("%H:%M")}-{self.end_time.strftime("%H:%M")}'

    def to_dict(self):
        return {
            'id': self.id,
            'store_id': self.store_id,
            'name': self.name,
            'start_time': self.start_time.strftime('%H:%M'),
            'end_time': self.end_time.strftime('%H:%M'),
            'time_range': self.time_range,
            'is_active': self.is_active,
            'sort_order': self.sort_order,
        }


class ShiftAssignment(BaseModel):
    """排班：哪天、谁、上哪个班"""
    __tablename__ = 'shift_assignment'

    store_id = db.Column(
        db.Integer, db.ForeignKey('store.id', ondelete='RESTRICT'), nullable=False, index=True,
    )
    # CASCADE：员工删了，他的排班跟着走——排班是「给这个人排的」，
    # 人没了这条记录没有任何意义（和订单明细跟着订单走一个道理）
    staff_id = db.Column(
        db.Integer, db.ForeignKey('staff.id', ondelete='CASCADE'), nullable=False, index=True,
    )
    # `cascade='all, delete-orphan'` 和上面那句 ondelete='CASCADE' **不是重复**：
    # ondelete 是数据库层的事（外键约束直接删子行），cascade 是 ORM 层的事。
    # 只写 ondelete 的话，删员工时 ORM 会先把他的排班查出来、把 staff_id 改成
    # NULL（它以为自己在「解除关联」），结果撞上 NOT NULL 报 IntegrityError——
    # 数据库那条级联根本没机会执行。和订单明细那边一个写法
    staff = db.relationship('Staff', backref=db.backref(
        'shifts', lazy='dynamic', cascade='all, delete-orphan'))

    shift_id = db.Column(
        db.Integer, db.ForeignKey('shift_template.id', ondelete='RESTRICT'),
        nullable=False, index=True,
    )
    shift = db.relationship('ShiftTemplate')

    work_date = db.Column(db.Date, nullable=False, index=True)
    remark = db.Column(db.String(255), nullable=False, default='')

    __table_args__ = (
        # 同一个人、同一天、同一个班只该有一条——防重复点。
        #
        # **不拦「一天两个班」**：餐饮里「两头班」是常态（早上来备菜、
        # 中午歇、晚上再来），那是两条不同 shift_id 的记录，本来就该允许
        db.UniqueConstraint('staff_id', 'work_date', 'shift_id',
                            name='uq_shift_assignment_staff_date_shift'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'store_id': self.store_id,
            'staff_id': self.staff_id,
            'staff_name': (self.staff.real_name or self.staff.username) if self.staff else '',
            'shift_id': self.shift_id,
            'shift_name': self.shift.name if self.shift else '',
            'shift_time_range': self.shift.time_range if self.shift else '',
            'work_date': self.work_date.isoformat() if self.work_date else None,
            'remark': self.remark,
        }
