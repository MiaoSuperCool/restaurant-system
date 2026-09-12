"""角色：权限码的集合 + 一个数据范围

一张表管两件事（设计文档「角色 × 权限（修订版）」）：
- 有哪些权限码（经 role_permission 关联）
- 能碰多大范围的数据（data_scope 列，本店 / 全部）

数据范围必须放在角色上而不是权限码上：同一个 dish:price:edit，
店长只能改本店、运营主管能改全公司，区别不在「能不能改」而在「能改哪些」。
"""
from backend.app.extensions import db
from backend.app.models.base import BaseModel

# ---------- 两张纯关联表 ----------
# 用 db.Table 而不是建模成类，因为关联本身没有任何属性（没有授权时间、没有授权人）。
# 复合主键顺带在数据库层挡住重复：(staff_id, role_id) 物理上不可能出现两条。
# ondelete='CASCADE'：删员工/删角色时关联行自动清掉，否则外键会卡住删除。

staff_role = db.Table(
    'staff_role',
    db.Column('staff_id', db.Integer,
              db.ForeignKey('staff.id', ondelete='CASCADE'), primary_key=True),
    db.Column('role_id', db.Integer,
              db.ForeignKey('role.id', ondelete='CASCADE'), primary_key=True),
)

role_permission = db.Table(
    'role_permission',
    db.Column('role_id', db.Integer,
              db.ForeignKey('role.id', ondelete='CASCADE'), primary_key=True),
    db.Column('permission_id', db.Integer,
              db.ForeignKey('permission.id', ondelete='CASCADE'), primary_key=True),
)


class Role(BaseModel):
    __tablename__ = 'role'

    # 数据范围
    SCOPE_STORE = 'store'   # 本店：只能碰自己归属门店的数据
    SCOPE_ALL = 'all'       # 全部：6 家店都能碰
    SCOPE_LABELS = {
        SCOPE_STORE: '本店',
        SCOPE_ALL: '全部',
    }

    code = db.Column(db.String(32), unique=True, nullable=False)
    name = db.Column(db.String(32), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=False, default='')
    data_scope = db.Column(db.String(16), nullable=False, default=SCOPE_STORE)
    # 预置角色：由 seed-rbac 维护，不允许在界面上改权限或删除，
    # 免得把种子数据改乱之后没法重建
    is_builtin = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    permissions = db.relationship(
        'Permission',
        secondary=role_permission,
        backref=db.backref('roles', lazy='dynamic'),
        order_by='Permission.sort_order',
    )

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'description': self.description,
            'data_scope': self.data_scope,
            'data_scope_label': self.SCOPE_LABELS.get(self.data_scope, self.data_scope),
            'is_builtin': self.is_builtin,
            'sort_order': self.sort_order,
            'permission_codes': [p.code for p in self.permissions],
        }
