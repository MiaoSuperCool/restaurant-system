"""排班接口：班次 + 一周班表 + 我自己的班

权限分两档：

    schedule:view     看（店长看全店这一周的格子，谁都能看自己哪天上班）
    schedule:manage   排（加删班次、改格子）

**「看」和「排」分开**的理由和收支两条线一样：能看班表的人不止店长——
服务员得知道自己哪天来。但「能看」不等于「能改」，改排班是店长的活。

数据范围在这一层不做判断，全部下沉到 `ScheduleService`：
每个方法开头都有 `assert_in_scope`，漏一个就是一个越权入口。
"""
from flask import jsonify
from flask_login import current_user, login_required
from flask_smorest import Blueprint

from backend.app.schemas.schedule_schema import (
    MyScheduleQuerySchema,
    SetDaySchema,
    ShiftCreateSchema,
    ShiftUpdateSchema,
    WeekQuerySchema,
)
from backend.app.services import ScheduleService
from backend.app.utils.api_response import api_response
from backend.app.utils.decorators import permission_required

bp = Blueprint('schedule', __name__, url_prefix='/api/schedule')


# ---------- 门店下拉 ----------

@bp.get('/stores')
@bp.response(200, description='我能排班的门店（数据范围内）')
@login_required
@permission_required('schedule:view')
def list_stores():
    """排班页的门店下拉

    **故意不复用 `/api/stores/options`**：那个要 `store:view`，服务员没有
    （他不是管理门店的人，只是想知道自己哪天上班）。复用的话他会看到
    「没有权限」的报错，而页面本身他是该能进的。
    """
    stores = ScheduleService.get_my_stores()
    return jsonify(api_response(success=True, data={
        'stores': [{'id': s.id, 'code': s.code, 'name': s.name} for s in stores],
    }))


# ---------- 班次 ----------

@bp.get('/stores/<int:store_id>/shifts')
@bp.response(200, description='这家店的班次（含停用的）')
@login_required
@permission_required('schedule:manage')
def list_shifts(store_id):
    """班次配置列表

    **含停用的**——配置页要能把停用的班次再启用回来，列表里过滤掉就找不着了。
    排班的下拉里只用启用中的（那边走 `get_week` 返回的 `shifts`）。
    """
    shifts = ScheduleService.get_shifts(store_id)
    return jsonify(api_response(success=True, data={
        'shifts': [s.to_dict() for s in shifts],
    }))


@bp.post('/stores/<int:store_id>/shifts')
@bp.response(201, description='建好了，返回新班次')
@login_required
@permission_required('schedule:manage')
@bp.arguments(ShiftCreateSchema, location='json')
def create_shift(data, store_id):
    shift = ScheduleService.create_shift(store_id, data)
    return jsonify(api_response(success=True, data=shift.to_dict())), 201


@bp.put('/shifts/<int:shift_id>')
@bp.response(200, description='改好了，返回班次')
@login_required
@permission_required('schedule:manage')
@bp.arguments(ShiftUpdateSchema, location='json')
def edit_shift(data, shift_id):
    shift = ScheduleService.update_shift(shift_id, data)
    return jsonify(api_response(success=True, data=shift.to_dict()))


@bp.delete('/shifts/<int:shift_id>')
@bp.response(200, description='已删除')
@login_required
@permission_required('schedule:manage')
def delete_shift(shift_id):
    """删班次——**排过班的删不掉**，不想再排请改成「停用」"""
    ScheduleService.delete_shift(shift_id)
    return jsonify(api_response(success=True, message='已删除'))


# ---------- 一周班表 ----------

@bp.get('/stores/<int:store_id>/week')
@bp.response(200, description='这一周的班表：员工分行、7 天分列')
@login_required
@permission_required('schedule:view')
@bp.arguments(WeekQuerySchema, location='query')
def week(params, store_id):
    """这一周的格子

    `day` 传这一周里的任意一天都行（周一会自动折到周一）——前端翻页时
    直接拿「上一周某一天」来问，不用自己算周一。
    """
    data = ScheduleService.get_week(store_id, params.get('day'))
    return jsonify(api_response(success=True, data=data))


@bp.put('/stores/<int:store_id>/assignments')
@bp.response(200, description='排好了，返回这个人这天最新的班')
@login_required
@permission_required('schedule:manage')
@bp.arguments(SetDaySchema, location='json')
def set_assignment(data, store_id):
    """排一个人一天的班

    传的 `shift_ids` 是**这一天的完整答案**：点一下加一个班、再点一下取消，
    前端把点完之后的整个数组发上来。返回最新状态，前端拿它覆盖那个格子——
    不自己猜「我刚才那一下到底成没成」。
    """
    assignments = ScheduleService.set_staff_day(
        store_id, data['staff_id'], data['work_date'], data['shift_ids'],
    )
    return jsonify(api_response(success=True, data={'assignments': assignments}))


# ---------- 我自己的班表 ----------

@bp.get('/me')
@bp.response(200, description='我接下来哪天上班')
@login_required
@permission_required('schedule:view')
@bp.arguments(MyScheduleQuerySchema, location='query')
def my_schedule(params):
    """我的班表

    `store_id` 不用传也不用校验数据范围——查的是 `current_user.id` 自己的，
    本来就不该有「看别人的」这个入口。
    """
    data = ScheduleService.get_my_schedule(current_user.id, days=params['days'])
    return jsonify(api_response(success=True, data=data))
