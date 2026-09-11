"""rename user table to staff

把员工账号表从 user 改名为 staff，并补上归属门店、用工类型、公用账号三个字段。

这版迁移是手写的，不能用 autogenerate：自动比对只会看到「少了一张 user 表、
多了一张 staff 表」，生成出来是 drop_table + create_table，会把已有账号删掉。

Revision ID: 6ecbc630323e
Revises: 06582cacde3c
Create Date: 2026-09-11 20:07:12.149741

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '6ecbc630323e'
down_revision = '06582cacde3c'
branch_labels = None
depends_on = None


def upgrade():
    # 1) 表改名。
    #    MySQL 和 SQLite(3.25+) 都会自动把引用它的外键（audit_log.operator_id）
    #    指向新表名，所以不需要重建那条外键约束。
    op.rename_table('user', 'staff')

    # 2) 新增字段。
    #    NOT NULL 的列必须先给 server_default，否则已有的那行数据填不进去；
    #    填完之后再把默认值摘掉，让库里的结构和模型定义保持一致
    #    （模型里用的是 Python 侧 default，不声明 server_default）。
    op.add_column('staff', sa.Column('store_id', sa.Integer(), nullable=True))
    op.add_column('staff', sa.Column(
        'employment_type', sa.String(length=20), nullable=False, server_default='full_time'
    ))
    op.add_column('staff', sa.Column(
        'is_shared', sa.Boolean(), nullable=False, server_default=sa.false()
    ))
    op.alter_column('staff', 'employment_type', server_default=None)
    op.alter_column('staff', 'is_shared', server_default=None)

    # 3) 归属门店外键。
    #    RESTRICT：门店下面还有员工时不允许删除门店。store_service 里另有一道
    #    更友好的检查（会告诉用户还剩多少条数据），这里是数据库层的兜底。
    op.create_index('ix_staff_store_id', 'staff', ['store_id'])
    op.create_foreign_key(
        'fk_staff_store_id', 'staff', 'store', ['store_id'], ['id'], ondelete='RESTRICT'
    )


def downgrade():
    op.drop_constraint('fk_staff_store_id', 'staff', type_='foreignkey')
    op.drop_index('ix_staff_store_id', table_name='staff')

    op.drop_column('staff', 'is_shared')
    op.drop_column('staff', 'employment_type')
    op.drop_column('staff', 'store_id')

    op.rename_table('staff', 'user')
