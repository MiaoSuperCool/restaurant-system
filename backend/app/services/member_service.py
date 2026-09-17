"""会员档案的查询和建档

余额相关的事在 `BalanceService` 里——**会员是"人"，储值是"他的钱"**，
分开两个 service，别让一个文件管两件事。

但「把人和他的钱拼成一份数据下发」这件事得有人干，就放这儿（`with_assets`）：
员工端查会员和顾客端看自己，要的是同一份东西，拼法不该有两份。
"""
from flask_login import current_user

from backend.app.errors import BusinessError, NotFoundError
from backend.app.extensions import db
from backend.app.models import Balance, Member, Points
from backend.app.services.audit_service import AuditService

RESOURCE = 'member'


class MemberService:
    @staticmethod
    def get_or_404(member_id):
        member = db.session.get(Member, member_id)
        if not member:
            raise NotFoundError('会员不存在')
        return member

    @staticmethod
    def with_assets(member_id):
        """会员档案 + 储值余额 + 积分

        **两个资产一起给**：不管收银台还是顾客自己，想知道的就是
        「他账上有多少钱、多少分」，分三个请求没意义。

        没有账户时给的是「0 的表示」而不是 None——**这里和员工端那个列表
        不一样**：那边要区分「看不到」和「没有」（没权限时给 null），
        而这是本人的数据，不存在看不到。
        """
        from backend.app.services.balance_service import BalanceService
        from backend.app.services.points_service import PointsService

        member = MemberService.get_or_404(member_id)

        balance = Balance.query.filter_by(member_id=member_id).first()
        points = Points.query.filter_by(member_id=member_id).first()

        data = member.to_dict()
        data['balance'] = (balance.to_dict() if balance
                           else BalanceService.empty_dict(member_id))
        points_data = points.to_dict() if points else PointsService.empty_dict(member_id)
        # 顺手把「这些分能抵多少钱」算出来——**用 service 的换算，不另写一套**。
        # 前端拿它直接显示，顾客不用心算「320 分是几块钱」
        points_data['amount'] = float(PointsService.amount_for_points(points_data['balance']))
        data['points'] = points_data
        return data

    @staticmethod
    def get_by_mobile(mobile):
        """按手机号查——收银台「顾客报手机号」就是这个入口"""
        return Member.query.filter_by(mobile=mobile).first()

    @staticmethod
    def get_paginated(page=1, per_page=10, search=None):
        query = Member.query
        if search:
            # 手机号和昵称都能搜：收银台按手机号，后台找人按名字
            query = query.filter(db.or_(
                Member.mobile.ilike(f'%{search}%'),
                Member.nickname.ilike(f'%{search}%'),
            ))
        return (query.order_by(Member.id.desc())
                .paginate(page=page, per_page=per_page, error_out=False))

    @staticmethod
    def _assert_identity(mobile, openid, exclude_id=None):
        """手机号和 openid 都得是唯一的，而且**至少得有一个**

        两个都空的话这张卡谁也认不出来——下次顾客来了没法证明这是他。
        """
        if not mobile and not openid:
            raise BusinessError('手机号和微信 openid 至少要填一个')

        if mobile:
            existing = Member.query.filter_by(mobile=mobile).first()
            if existing and existing.id != exclude_id:
                raise BusinessError(f'手机号 {mobile} 已经被注册过了')

        if openid:
            existing = Member.query.filter_by(openid=openid).first()
            if existing and existing.id != exclude_id:
                raise BusinessError('这个微信号已经注册过会员了')

    @staticmethod
    def create(data):
        """建会员（员工代客办卡，或者顾客端微信登录时自动建）"""
        try:
            mobile = data.get('mobile') or None
            openid = data.get('openid') or None
            MemberService._assert_identity(mobile, openid)

            member = Member(
                mobile=mobile,
                openid=openid,
                nickname=data.get('nickname', ''),
                avatar=data.get('avatar', ''),
            )
            db.session.add(member)
            db.session.commit()

            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='CREATE_MEMBER',
                resource=RESOURCE,
                status='success',
                new_value=member.to_dict(),
            )
            return member
        except Exception:
            db.session.rollback()
            AuditService.log(
                operator_id=current_user.id,
                operator_name=current_user.username,
                action='CREATE_MEMBER',
                resource=RESOURCE,
                status='failed',
            )
            raise
