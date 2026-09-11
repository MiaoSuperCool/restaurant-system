from flask import jsonify
from flask_login import current_user, login_required
from flask_smorest import Blueprint

from backend.app.services import StaffService, StoreService
from backend.app.utils.api_response import api_response

bp = Blueprint('main', __name__)

@bp.route('/index')
@bp.response(200, description='当前登录员工 + 示例统计')
@login_required
def index():
    """首页基础信息（需登录）：当前登录员工 + 示例统计

    注意：本项目 API 均带 /api 前缀，唯独此仪表盘接口沿用 /index（历史约定），
    部署时 Nginx/代理需同时转发 /index（前端 Vite 代理已配置）
    """
    return jsonify(api_response(
        success=True,
        data={
            'staff': current_user.to_dict(),
            'is_admin': current_user.is_admin,
            'staff_count': StaffService.get_all_count(),
            'store_count': StoreService.get_all_count(),
        }
    ))


@bp.route('/health')
@bp.response(200, description='健康检查通过')
def health():
    """健康检查（部署探活/负载均衡用，无需登录）"""
    return jsonify(api_response(success=True, data={'status': 'ok'}))
