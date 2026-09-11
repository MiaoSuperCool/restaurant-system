from flask import jsonify
from flask_login import current_user, login_required
from flask_smorest import Blueprint

from backend.app.services import UserService
from backend.app.utils.api_response import api_response

bp = Blueprint('main', __name__)

@bp.route('/index')
@bp.response(200, description='当前用户 + 示例统计')
@login_required
def index():
    """首页基础信息（需登录）：当前用户 + 示例统计

    注意：本模板 API 均带 /api 前缀，唯独此仪表盘接口沿用 /index（历史约定），
    部署时 Nginx/代理需同时转发 /index（前端 Vite 代理已配置）
    """
    user_count = UserService.get_all_count()  # 示例统计：用户总数
    return jsonify(api_response(
        success=True,
        data={
            'user': current_user.to_dict(),
            'is_admin': current_user.is_admin,
            'user_count': user_count,
        }
    ))


@bp.route('/health')
@bp.response(200, description='健康检查通过')
def health():
    """健康检查（部署探活/负载均衡用，无需登录）"""
    return jsonify(api_response(success=True, data={'status': 'ok'}))
