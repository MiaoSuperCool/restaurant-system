from flask_login import current_user

from backend.app import BusinessError

# 直接导入模块而不是 from backend.app.services import ...：
# 包 __init__ 里 auth_service 排在 staff_service 之前，走包导入会撞上半初始化的模块
from backend.app.services.audit_service import AuditService
from backend.app.services.staff_service import StaffService


class AuthService:
    @staticmethod
    def session_payload(staff):
        """登录态要下发给前端的东西（登录接口和首页接口共用）

        permissions 和 data_scope 一并下发，前端才知道该显示哪些菜单、
        该不该渲染「新增/编辑」按钮。注意这纯粹是体验层——后端每个接口
        都会重新判权，前端就算把 permissions 改了也拿不到数据。
        """
        return {
            'staff': staff.to_dict(),
            'permissions': staff.permission_codes(),
            'data_scope': staff.data_scope,
        }

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
