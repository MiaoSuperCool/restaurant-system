"""权限：一个权限码 = 一件事能不能干

命名统一为「资源:动作」，如 order:refund、dish:price:edit。
权限码是后端判权的唯一依据，前端的菜单/按钮隐藏只是体验层。
"""
from backend.app.extensions import db
from backend.app.models.base import BaseModel


class Permission(BaseModel):
    __tablename__ = 'permission'

    # 权限码，如 order:refund。全项目的合法取值集中在 rbac.py 的 PERMISSIONS 里
    code = db.Column(db.String(64), unique=True, nullable=False, index=True)
    name = db.Column(db.String(64), nullable=False)
    # 按域分组，只影响展示（权限分配界面按组折叠），不参与判权
    group = db.Column(db.String(32), nullable=False, index=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'group': self.group,
            'sort_order': self.sort_order,
        }
