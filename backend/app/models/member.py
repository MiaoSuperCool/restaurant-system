"""会员档案 + 顾客端登录用的验证码

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
from datetime import datetime, timedelta, timezone

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


class MemberVerifyCode(BaseModel):
    """顾客端登录用的短信验证码

    **为什么存库不存缓存**：项目里装了 Flask-Caching（配置指向 Redis），
    但**没有任何地方用过它**——开发环境 Redis 根本没起。验证码要是存缓存，
    就等于给「顾客登录」这个基础功能加了一个平时不跑的运行时依赖。
    存库还有个好处：谁在什么时候要过几次验证码，查得到，这本身就是防刷的证据。

    **每次发都插一条新行，不覆盖旧的**。查的时候取最新那条有效的，
    这样「一分钟内已经发过」才判得出来（覆盖掉就查不到了）。
    过期的老行在发新码时顺手清掉。
    """
    __tablename__ = 'member_verify_code'

    mobile = db.Column(db.String(20), nullable=False, index=True)
    code = db.Column(db.String(6), nullable=False)

    expires_at = db.Column(db.DateTime, nullable=False)
    # 用过一次就作废——不然同一个码能反复换 token
    used_at = db.Column(db.DateTime, nullable=True)
    # 输错几次。超了直接作废，不然可以拿一个码暴力试 6 位数字
    attempt_count = db.Column(db.Integer, nullable=False, default=0)

    # 有效期和「一分钟内不重复发」的间隔。放这儿而不是配置里：
    # 它们是这个功能自己的一部分，换个环境也不该变
    TTL_SECONDS = 300
    RESEND_INTERVAL_SECONDS = 60
    MAX_ATTEMPTS = 5

    @classmethod
    def issue(cls, mobile, code):
        """生成一条新码（调用方负责 commit）"""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        return cls(mobile=mobile, code=code, expires_at=now + timedelta(seconds=cls.TTL_SECONDS))

    @property
    def is_used(self):
        return self.used_at is not None

    @property
    def is_expired(self):
        return self.expires_at < datetime.now(timezone.utc).replace(tzinfo=None)

    def mark_used(self):
        self.used_at = datetime.now(timezone.utc).replace(tzinfo=None)

    def to_dict(self):
        """**不带 code**——验证码是凭据，不进任何接口的返回体"""
        return {
            'mobile': self.mobile,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'used_at': self.used_at.isoformat() if self.used_at else None,
        }
