"""经营报表接口

**一个接口，两个角色**：店长看到的范围和老板不一样，但看的是同一套数——
靠的是数据范围（`current_user.accessible_store_ids()`），不是两个接口。

    店长  report:store   只有自己那家 → `by_store` 里一行，看不到门店对比
    老板  report:all     全公司 → `by_store` 里六行，能对比

调权那条线也在这儿：**能不能看报表**是权限码的事（两个码任一），
**能看哪几家**是数据范围的事。这两件事在后端是分开的，前端也一样。
"""
from flask import jsonify
from flask_login import current_user
from flask_smorest import Blueprint

from backend.app.schemas.report_schema import ReportQuerySchema
from backend.app.services import ReportService
from backend.app.utils.api_response import api_response
from backend.app.utils.decorators import permission_required

bp = Blueprint('reports', __name__, url_prefix='/api/reports')


@bp.get('/overview')
@bp.response(200, description='经营概览：汇总 + 趋势 + 时段 + 支付构成 + 菜品排行 + 门店对比')
@permission_required('report:store', 'report:all')
@bp.arguments(ReportQuerySchema, location='query')
def overview(params):
    """一份完整的经营概览

    **口径写在 `ReportService` 的模块开头**（营业日按哪天算、营业额怎么算），
    这里不重复——一张报表不写口径，两个人能数出相差一倍的数。

    看别家店 → 403；没权限码 → 403（菜单里也进不来）。
    """
    store_id = params.get('store_id')
    if store_id is not None:
        # **先拦一道**：数据范围是「本店」的账号，不能靠改 URL 里的 store_id
        # 去看别家的数。放行的话，这一条就是整个报表模块唯一的漏洞
        ReportService.assert_store_in_scope(store_id)

    data = ReportService.get_overview(
        store_ids=current_user.accessible_store_ids(),
        days=params.get('days', 7),
        start=params.get('start'),
        end=params.get('end'),
        store_id=store_id,
    )
    return jsonify(api_response(success=True, data=data))
