from flask_login import current_user

from backend.app import BusinessError

# 直接导入模块而不是 from backend.app.services import ...：
# 包 __init__ 里 auth_service 排在 staff_service 之前，走包导入会撞上半初始化的模块
from backend.app.services.audit_service import AuditService
from backend.app.services.staff_service import StaffService


class AuthService:
    @staticmethod
    def login(username, password):
        user = StaffService.get_staff_by_username(username)
        if not user:
            raise BusinessError('用户不存在，请检查输入或先创建', status_code=404)

        if not user.check_password(password):
            raise BusinessError('用户名或密码错误', status_code=401)

        if not user.is_active:
            raise BusinessError('账号已被禁用')

        AuditService.log(
            operator_id=user.id,
            operator_name=user.username,
            action='Login',
            status='success'
        )

        return user


    @staticmethod
    def logout():
        AuditService.log(
            operator_id=current_user.id,
            operator_name=current_user.username,
            action='Logout',
            status='success'
        )
