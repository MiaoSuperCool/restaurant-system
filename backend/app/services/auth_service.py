from flask_login import current_user

from backend.app import BusinessError
from backend.app.services import AuditService
from backend.app.services.user_service import UserService


class AuthService:
    @staticmethod
    def login(username, password):
        user = UserService.get_user_by_username(username)
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


