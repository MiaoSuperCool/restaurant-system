from flask_login import current_user

from backend.app import BusinessError
from backend.app.extensions import db

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
    def login_with_token(username, password):
        """小程序登录：账号密码 → token

        校验那一段和网页端**完全一样**（走同一个 `login()`），
        这里只是换个发凭据的方式——网页端发 session cookie，小程序发 token。
        """
        from backend.app.utils.token import issue_token

        staff = AuthService.login(username, password)
        return staff, issue_token(staff)

    @staticmethod
    def resolve_token(token):
        """token → 员工；无效、过期、版本对不上、账号停用，一律返回 None

        **每次请求都查一次库**（不是把身份全塞进 token 里）。多一次主键查询，
        换来的是「停用账号、改角色立刻生效」——门店里兼职账号要能秒开秒停，
        靠等 token 过期显然不行。权限也是现查的，同理。
        """
        from backend.app.models.staff import Staff
        from backend.app.utils.token import parse_token

        payload = parse_token(token)
        if not payload:
            return None

        staff = db.session.get(Staff, payload.get('uid'))
        if not staff or not staff.is_active:
            return None

        # 版本对不上 = 这个 token 是在登出/改密码之前签的，作废
        if (payload.get('ver') or 0) != (staff.token_version or 0):
            return None

        return staff

    @staticmethod
    def logout():
        """登出——**两条通道的「登出」不是同一件事**

        session 通道：清掉服务端的 session，浏览器那个 cookie 随之作废
        token 通道：服务端**没存** token，删不掉——把 `token_version` +1，
                    让这个员工手里所有旧 token 一起失效

        后者会把别的设备也一并踢下线。这是**故意的**：门店里的公用平板
        （`is_shared`）登出时，本来就该把之前登录留下的凭据也清掉，
        不然下一个人拿起平板还能接着用上一个账号。
        """
        from backend.app.utils.token import bearer_token

        staff = current_user
        AuditService.log(
            operator_id=staff.id,
            operator_name=staff.username,
            action='Logout',
            status='success'
        )

        if bearer_token() is not None:
            staff.token_version = (staff.token_version or 0) + 1
            db.session.commit()
