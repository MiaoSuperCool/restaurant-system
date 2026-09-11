from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from backend.app.extensions import db
from backend.app.models.base import BaseModel


class User(UserMixin, BaseModel):
    __tablename__ = 'user'

    username = db.Column(db.String(80), unique=True, nullable=False)
    real_name = db.Column(db.String(80), nullable=False, index=True)
    email = db.Column(db.String(80), unique=True, nullable=False)
    mobile = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    # 安全字段
    is_active = db.Column(db.Boolean, default=True, nullable=False)
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
            'is_active': self.is_active,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
