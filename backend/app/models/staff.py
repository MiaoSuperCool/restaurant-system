"""员工账号（内部人员）

和顾客（会员）是两套账号体系，不要合并成一张表：
- 员工：账号/密码登录，有门店归属、角色、用工类型、账号状态
- 顾客：微信登录，只有 openid/手机号/昵称，量级几万，不进权限码体系

顾客表（Member）二期单独建，见设计文档「用户要拆成两个实体」。
"""
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from backend.app.extensions import db
from backend.app.models.base import BaseModel


class Staff(UserMixin, BaseModel):
    __tablename__ = 'staff'

    # 用工类型：兼职/小时工不是独立角色，是一种账号类型——套收银员/服务员的权限，
    # 但账号要能秒开秒停（改 is_active 即可）
    TYPE_FULL_TIME = 'full_time'
    TYPE_PART_TIME = 'part_time'
    TYPE_LABELS = {
        TYPE_FULL_TIME: '全职',
        TYPE_PART_TIME: '兼职',
    }

    # 唯一字段的中文名，用于「XX 已存在」这类报错文案
    FIELD_LABELS = {
        'username': '用户名',
        'email': '邮箱',
        'mobile': '手机号',
    }

    username = db.Column(db.String(80), unique=True, nullable=False)
    real_name = db.Column(db.String(80), nullable=False, index=True)
    email = db.Column(db.String(80), unique=True, nullable=False)
    mobile = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    # 归属门店：总部账号（运营主管/财务/老板）不归属具体门店，所以可空。
    # 数据范围「本店」的判定就靠这个字段。
    # ondelete='RESTRICT'：门店还有员工时不能删（store_service 里也有一道更友好的检查）
    store_id = db.Column(
        db.Integer, db.ForeignKey('store.id', ondelete='RESTRICT'), nullable=True, index=True
    )
    store = db.relationship('Store', backref=db.backref('staff_members', lazy='dynamic'))

    employment_type = db.Column(db.String(20), nullable=False, default=TYPE_FULL_TIME)

    # 公用账号：服务员共用一台设备登录时用。开了这个字段，每次下单必须另外记录
    # 实际操作人（选人/扫工牌），否则出了事追责无门。
    is_shared = db.Column(db.Boolean, nullable=False, default=False)

    # 安全字段
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    # 超级管理员：绕过权限码检查的旁路。日常授权走角色（Role），这个只留给
    # 初始管理员账号/老板，不要拿它当日常权限分配手段。
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'real_name': self.real_name,
            'email': self.email,
            'mobile': self.mobile,
            'store_id': self.store_id,
            'store_name': self.store.name if self.store else None,
            'employment_type': self.employment_type,
            'employment_type_label': self.TYPE_LABELS.get(
                self.employment_type, self.employment_type
            ),
            'is_shared': self.is_shared,
            'is_active': self.is_active,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
