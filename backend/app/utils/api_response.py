from datetime import datetime
from typing import Any, Dict


def api_response(
        success: bool = True,
        message: str = '',
        data: Any = None,
        status_code: int = 200
)-> Dict:
    """
        统一API响应格式
        参数:
            success: 请求是否成功
            message: 提示信息
            data: 返回的数据
            status_code: HTTP状态码（仅用于文档标注，实际由视图函数控制）
        返回:
            统一格式的响应字典
        """
    response = {
        'success': success,
        'message': message,
        'data': data,
        'timestamp': datetime.now().isoformat()  # 可选：添加时间戳
    }

    return response
