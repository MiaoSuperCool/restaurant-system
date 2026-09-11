from backend.app.extensions import db
from backend.app.models.base import BaseModel


class AuditLog(BaseModel):
    __tablename__ = 'audit_log'

    # ondelete='SET NULL'：删除用户后审计记录保留
    # （operator_id 置空，operator_name 冗余存有名字）
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    operator_name = db.Column(db.String(50), nullable=False, index=True)
    action = db.Column(db.String(50), nullable=False)
    resource = db.Column(db.String(50), nullable=True)  # 操作对象（user、audit_log 等）
    status = db.Column(db.String(50), nullable=False, default='success')
    old_value = db.Column(db.JSON, nullable=True)
    new_value = db.Column(db.JSON, nullable=True)


    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.operator_id,
            'user_name': self.operator_name,
            'action': self.action,
            'resource': self.resource,
            # 操作时间即记录创建时间（BaseModel.created_at）
            'datetime': self.created_at.isoformat() if self.created_at else None,
            'status': self.status,
            'old_value': self.old_value,
            'new_value': self.new_value
        }
