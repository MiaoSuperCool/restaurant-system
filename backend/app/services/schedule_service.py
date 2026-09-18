"""排班：班次的管理 + 一周的班表

**这不是考勤**，理由写在 `models/schedule.py` 开头。这里补一句操作层面的：

    班次   门店级配置（早班 09:00-14:00），排过班就不能删、只能停用
    排班   哪天谁上哪个班；一天可以排两个（餐饮的「两头班」）

数据范围这一层特别要紧：排班是**店长**的活（`schedule:manage`），
他只能排自己那家店和那家店的人。所以这里每个方法开头都要过一遍
`assert_in_scope`。
"""
import logging
from datetime import date, datetime, timedelta

from flask_login import current_user

from backend.app.errors import BusinessError, NotFoundError
from backend.app.extensions import db
from backend.app.models import ShiftAssignment, ShiftTemplate, Staff, Store
from backend.app.services.audit_service import AuditService
from backend.app.utils.references import describe_references, find_referencing_rows

logger = logging.getLogger(__name__)

RESOURCE = 'schedule'

WEEKDAYS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']


def _week_start(day):
    """那一天所在的自然周的周一

    **一周从周一开始**，不是从「今天开始往后数 7 天」——店长想的是
    「下周的班」，而「下周」在所有人脑子里都是周一到周日。
    """
    return day - timedelta(days=day.weekday())


class ScheduleService:
    # ---------- 数据范围 ----------

    @staticmethod
    def assert_in_scope(store_id):
        """排班是门店级的活：本店范围的角色只能碰自己那家

        规则本身在 `Staff.can_access_store` 里，这里只负责换成排班该说的话。
        """
        if not current_user.can_access_store(store_id):
            raise BusinessError('无权查看其他门店的排班', status_code=403)

    @staticmethod
    def get_store_or_404(store_id):
        store = db.session.get(Store, store_id)
        if not store:
            raise NotFoundError('门店不存在')
        return store

    @staticmethod
    def get_my_stores():
        """我能在哪些门店看/排班——给前端的门店下拉用

        **不走 `/api/stores/options`**：那个接口要 `store:view`，而一线员工
        只有 `schedule:view`（他得知道自己哪天上班）。为了看班表先给他
        「门店查看」权限是本末倒置——所以这里单开一个，只返回他自己
        数据范围内的那几家（店长一家，老板六家）。
        """
        ids = current_user.accessible_store_ids()
        query = Store.query
        if ids is not None:
            query = query.filter(Store.id.in_(ids))
        return query.order_by(Store.id).all()

    # ---------- 班次 ----------

    @staticmethod
    def get_shifts(store_id, only_active=False):
        """这家店的班次。`only_active=True` 时只给启用中的（排班的下拉用这个）"""
        query = ShiftTemplate.query.filter_by(store_id=store_id)
        if only_active:
            query = query.filter(ShiftTemplate.is_active.is_(True))
        return query.order_by(ShiftTemplate.sort_order, ShiftTemplate.id).all()

    @staticmethod
    def create_shift(store_id, data):
        """加一个班次

        **同名的不许加**（数据库上也有唯一约束）：排班的下拉里出现两个「早班」，
        选哪个全靠猜，而且排出来的班表根本看不出区别。
        """
        ScheduleService.assert_in_scope(store_id)
        ScheduleService.get_store_or_404(store_id)

        existing = ShiftTemplate.query.filter_by(store_id=store_id, name=data['name']).first()
        if existing:
            raise BusinessError(f'这家店已经有一个叫「{data["name"]}」的班次了')

        start, end = ScheduleService._parse_times(data)
        shift = ShiftTemplate(
            store_id=store_id, name=data['name'],
            start_time=start, end_time=end,
            sort_order=data.get('sort_order', 0),
        )
        db.session.add(shift)
        db.session.commit()

        AuditService.log(
            operator_id=current_user.id, operator_name=current_user.username,
            action='CREATE_SHIFT', resource=RESOURCE, status='success',
            new_value=shift.to_dict(),
        )
        return shift

    @staticmethod
    def _parse_times(data):
        """把 'HH:MM' 解析成 time；顺带校验先后

        跨天的班（22:00-02:00）这里不支持——餐饮的营业时间里那种是少数，
        而且真支持了「这条排班算哪天」会变复杂。要记的话拆成两条。
        """
        try:
            start = datetime.strptime(data['start_time'], '%H:%M').time()
            end = datetime.strptime(data['end_time'], '%H:%M').time()
        except (KeyError, ValueError):
            raise BusinessError('班次时间格式要写成 HH:MM，比如 09:00') from None
        if start >= end:
            raise BusinessError('结束时间要在开始时间之后（跨天的班请拆成两条）')
        return start, end

    @staticmethod
    def update_shift(shift_id, data):
        shift = ScheduleService._get_shift_or_404(shift_id)
        ScheduleService.assert_in_scope(shift.store_id)
        old_value = shift.to_dict()

        if 'name' in data and data['name'] != shift.name:
            clash = ShiftTemplate.query.filter_by(
                store_id=shift.store_id, name=data['name'],
            ).first()
            if clash:
                raise BusinessError(f'这家店已经有一个叫「{data["name"]}」的班次了')
            shift.name = data['name']

        if 'start_time' in data or 'end_time' in data:
            shift.start_time, shift.end_time = ScheduleService._parse_times({
                'start_time': data.get('start_time', shift.start_time.strftime('%H:%M')),
                'end_time': data.get('end_time', shift.end_time.strftime('%H:%M')),
            })

        for field in ('is_active', 'sort_order'):
            if field in data:
                setattr(shift, field, data[field])

        db.session.commit()

        AuditService.log(
            operator_id=current_user.id, operator_name=current_user.username,
            action='UPDATE_SHIFT', resource=RESOURCE, status='success',
            old_value=old_value, new_value=shift.to_dict(),
        )
        return shift

    @staticmethod
    def _get_shift_or_404(shift_id):
        shift = db.session.get(ShiftTemplate, shift_id)
        if not shift:
            raise NotFoundError('班次不存在')
        return shift

    @staticmethod
    def delete_shift(shift_id):
        """删班次——**排过班的就删不掉了**，和券模板一个道理

        那个班次名字底下挂着几十条排班记录，删了它们就成了没头没尾的东西
        （连「几点上的班」都不知道了）。不想再排的话把状态改成停用。
        """
        shift = ScheduleService._get_shift_or_404(shift_id)
        ScheduleService.assert_in_scope(shift.store_id)

        references = find_referencing_rows(ShiftTemplate, shift_id)
        if references:
            raise BusinessError(
                f'班次「{shift.name}」还有{describe_references(references)}，'
                f'不能删除；不想再排的话请把状态改成「停用」'
            )

        old_value = shift.to_dict()
        db.session.delete(shift)
        db.session.commit()

        AuditService.log(
            operator_id=current_user.id, operator_name=current_user.username,
            action='DELETE_SHIFT', resource=RESOURCE, status='success',
            old_value=old_value,
        )
        return True

    # ---------- 一周的班表 ----------

    @staticmethod
    def get_week(store_id, day=None):
        """这一周的班表：**按人分行、按天分列**

        返回的结构是「员工列表 + 每人 7 个格子」，格子里的数组和 `days`
        一一对应——前端直接 `row.assignments[dayIndex]` 就能渲染，
        不用自己在两层循环里找「这个人这天排了什么」。
        """
        ScheduleService.assert_in_scope(store_id)
        start = _week_start(day or date.today())
        end = start + timedelta(days=6)

        # **公用账号不进班表**：那台设备背后不是一个具体的人，排它没有意义
        # （它只是「前厅那台收银机」，谁当班不是它当班）
        staff = (Staff.query
                 .filter(Staff.store_id == store_id,
                         Staff.is_active.is_(True),
                         Staff.is_shared.is_(False))
                 .order_by(Staff.id)
                 .all())

        # 一次把这一周的排班全查出来，按 (人, 日) 分组——
        # 不然每个格子里查一次，7 天 × 10 个人就是 70 次查询
        assignments = (ShiftAssignment.query
                       .filter(ShiftAssignment.store_id == store_id,
                               ShiftAssignment.work_date >= start,
                               ShiftAssignment.work_date <= end)
                       .all())
        grouped = {}
        for item in assignments:
            grouped.setdefault((item.staff_id, item.work_date.isoformat()), []).append(item)

        days = [
            {'date': (start + timedelta(days=offset)).isoformat(),
             'weekday': WEEKDAYS[offset],
             'is_today': (start + timedelta(days=offset)) == date.today()}
            for offset in range(7)
        ]

        rows = []
        for member in staff:
            rows.append({
                'staff_id': member.id,
                'staff_name': member.real_name or member.username,
                'employment_type': member.employment_type,
                'employment_type_label': member.TYPE_LABELS.get(
                    member.employment_type, member.employment_type),
                'assignments': [
                    [a.to_dict() for a in grouped.get((member.id, day['date']), [])]
                    for day in days
                ],
            })

        return {
            'store_id': store_id,
            'start': start.isoformat(),
            'end': end.isoformat(),
            'days': days,
            'shifts': [s.to_dict() for s in ScheduleService.get_shifts(store_id, only_active=True)],
            'rows': rows,
        }

    @staticmethod
    def set_staff_day(store_id, staff_id, work_date, shift_ids):
        """把某个人某天的班设成这几个

        **按 id 对齐**（多的删、少的加），不是全删重建——和菜品规格那边
        一个道理：重建会换掉记录 id，而排班记录将来要挂别的东西
        （比如「这天实际出勤了没有」），id 一变那些就全断了。

        传空数组 = 那天不排班。
        """
        ScheduleService.assert_in_scope(store_id)
        ScheduleService.get_store_or_404(store_id)

        member = db.session.get(Staff, staff_id)
        if not member:
            raise NotFoundError('员工不存在')
        # **只排本店的人**：跨店借调是另一个功能（涉及工资算谁的），
        # 这里先不做。员工调岗之后，他之前的排班还留在老店（`store_id` 冗余）
        if member.store_id != store_id:
            raise BusinessError(f'「{member.real_name or member.username}」不属于这家店，排不了班')
        if member.is_shared:
            raise BusinessError(f'「{member.real_name or member.username}」是公用账号（设备），不是人，排不了班')

        wanted = set(shift_ids or [])
        if wanted:
            found = ShiftTemplate.query.filter(
                ShiftTemplate.id.in_(wanted),
                ShiftTemplate.store_id == store_id,
                ShiftTemplate.is_active.is_(True),
            ).all()
            missing = wanted - {s.id for s in found}
            if missing:
                raise BusinessError(f'班次不存在、已停用、或者不是这家店的（shift_id={sorted(missing)}）')

        existing = ShiftAssignment.query.filter_by(
            staff_id=staff_id, work_date=work_date,
        ).all()
        current_ids = {a.shift_id for a in existing}

        added, removed = wanted - current_ids, current_ids - wanted
        if not added and not removed:
            # 没变化也要**返回当前的样子**，不能返回空数组：接口的约定是
            # 「返回这个人这天最新的班」，前端拿它覆盖那个格子。
            # 返回空数组的话，同一个班连点两下，第二下会把格子里的班次擦掉
            return ScheduleService._day_assignments(staff_id, work_date)

        for item in existing:
            if item.shift_id in removed:
                db.session.delete(item)
        for shift_id in added:
            db.session.add(ShiftAssignment(
                store_id=store_id, staff_id=staff_id,
                shift_id=shift_id, work_date=work_date,
            ))
        db.session.commit()

        logger.info('排班变更 staff=%s date=%s 加=%s 删=%s',
                    staff_id, work_date, sorted(added), sorted(removed))
        AuditService.log(
            operator_id=current_user.id, operator_name=current_user.username,
            action='SET_SCHEDULE', resource=RESOURCE, status='success',
            new_value={'store_id': store_id, 'staff_id': staff_id,
                       'work_date': work_date.isoformat(),
                       'added': sorted(added), 'removed': sorted(removed)},
        )
        return ScheduleService._day_assignments(staff_id, work_date)

    @staticmethod
    def _day_assignments(staff_id, work_date):
        return [a.to_dict() for a in ShiftAssignment.query.filter_by(
            staff_id=staff_id, work_date=work_date,
        ).all()]

    # ---------- 我自己的班表 ----------

    @staticmethod
    def get_my_schedule(staff_id, days=14):
        """「我哪天上班」——一线员工看的那份

        和店长那份是**同两张表、两个看法**：店长要的是「这一周的格子」，
        服务员要的是「接下来我哪几天要来、几点来」。所以这里按天折好、
        只给有班的日子（空日子列出来只会刷屏），**没有权限码之外的过滤**：
        看自己的班不需要谁批准。
        """
        start = date.today()
        end = start + timedelta(days=days - 1)

        assignments = (ShiftAssignment.query
                       .join(ShiftTemplate, ShiftAssignment.shift_id == ShiftTemplate.id)
                       .filter(ShiftAssignment.staff_id == staff_id,
                               ShiftAssignment.work_date >= start,
                               ShiftAssignment.work_date <= end)
                       .order_by(ShiftAssignment.work_date, ShiftTemplate.start_time)
                       .all())

        grouped = {}
        for item in assignments:
            grouped.setdefault(item.work_date, []).append(item)

        result = []
        for work_date, items in grouped.items():
            offset = (work_date - start).days
            result.append({
                'date': work_date.isoformat(),
                'weekday': WEEKDAYS[work_date.weekday()],
                # 「今天/明天」在前端算的话要处理时区，两边算还可能不一致；
                # 后端本来就知道今天是哪天，直接给
                'relative': '今天' if offset == 0 else ('明天' if offset == 1 else ''),
                'shifts': [a.to_dict() for a in items],
            })

        return {
            'start': start.isoformat(),
            'end': end.isoformat(),
            'days': result,
            'total': len(assignments),
        }
