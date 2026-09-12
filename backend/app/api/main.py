from flask import jsonify
from flask_login import current_user, login_required
from flask_smorest import Blueprint

from backend.app.services import AuthService, OrderService, StaffService, StoreService
from backend.app.utils.api_response import api_response

bp = Blueprint('main', __name__)

@bp.route('/index')
@bp.response(200, description='当前登录员工 + 权限 + 今日经营看板')
@login_required
def index():
    """首页（需登录）：当前登录员工 + 权限 + 今天的经营情况

    'today' 这部分也受数据范围限制——店长看到的是本店的今日数据，
    老板看到的是全公司的。

    前端在页面刷新后会再调一次这个接口，用来同步最新的权限
    （改了角色不用重新登录就能生效）——登录接口返回的是同一份结构。

    注意：本项目 API 均带 /api 前缀，唯独此仪表盘接口沿用 /index（历史约定），
    部署时 Nginx/代理需同时转发 /index（前端 Vite 代理已配置）
    """
    return jsonify(api_response(
        success=True,
        data={
            **AuthService.session_payload(current_user),
            'today': OrderService.get_today_stats(current_user.accessible_store_ids()),
            'staff_count': StaffService.get_all_count(),
            'store_count': StoreService.get_all_count(),
        }
    ))


@bp.route('/health')
@bp.response(200, description='健康检查通过')
def health():
    """健康检查（部署探活/负载均衡用，无需登录）"""
    return jsonify(api_response(success=True, data={'status': 'ok'}))
