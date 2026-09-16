"""会员档案

一期顾客端「全程不需要登录」，订单的 `member_id` 一直空着；二期接上。

**两个身份标识，都可能为空，都唯一：**

    openid   微信登录拿到的（没有真 AppID 时会是空的）
    mobile   手机号

微信不一定给手机号（用户可以不授权），用户也可能直接拿手机号注册——所以两个都不能
设成 NOT NULL。唯一约束保证「一个手机号只能注册一次」；MySQL 允许多行 NULL 并存，
所以两个都空着也不会互相打架。

**余额和积分不在这张表里。** 设计文档「必须守住的 6 条」第 1 条：余额必须有流水账，
不能只存一个数字。它们各自是独立的账户表 + 流水表，见 balance.py / points.py。

**会员是全公司通用的**，不挂门店——储值那 80 万是公司收的，一个会员在任何一家店
都该能刷。门店级的会员卡是另一回事（那是「这家店的熟客」，本项目不做）。
"""
from backend.app.extensions import db
from backend.app.models.base import BaseModel


class Member(BaseModel):
    __tablename__ = 'member'

    # 微信身份。接不上真微信时一直是空，所以可空
    openid = db.Column(db.String(64), unique=True, nullable=True, index=True)
    # 微信开放平台的 unionid：将来同时有公众号/多个小程序时，靠它认出是同一个人
    unionid = db.Column(db.String(64), nullable=True, index=True)

    mobile = db.Column(db.String(20), unique=True, nullable=True, index=True)

    nickname = db.Column(db.String(32), nullable=False, default='')
    avatar = db.Column(db.String(255), nullable=False, default='')

    # 停用（不发券、不能动储值），但不删——历史订单还得认得这个人。
    # 和 Staff.is_active 一个思路：账号要能秒开秒停
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self):
        # 不返回 openid/unionid：那是身份凭据，顾客知道自己是谁，不需要看这个
        return {
            'id': self.id,
            'mobile': self.mobile,
            'nickname': self.nickname,
            'avatar': self.avatar,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
