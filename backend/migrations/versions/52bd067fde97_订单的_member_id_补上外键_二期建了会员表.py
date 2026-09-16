"""订单的 member_id 补上外键（二期建了会员表）

Revision ID: 52bd067fde97
Revises: 0481b7dea684
Create Date: 2026-09-16 17:28:48.951559

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '52bd067fde97'
down_revision = '0481b7dea684'
branch_labels = None
depends_on = None


def upgrade():
    # 外键取名字，别让数据库自动起。Alembic 生成的是 `create_foreign_key(None, ...)`，
    # 那等于交给 MySQL 起名（它起的是 `order_ibfk_3`）——名字带序号，换个环境
    # 就对不上，`downgrade` 里的 drop 更是直接找不到约束。
    # 项目里的惯例是 `fk_<表>_<列>`（见 6ecbc630323e 的 fk_staff_store_id）。
    #
    # RESTRICT：被订单引用过的会员不能删——历史订单得认得他。
    # 不过正常情况下会员是停用（is_active=False），不删。
    op.create_foreign_key(
        'fk_order_member_id', 'order', 'member', ['member_id'], ['id'], ondelete='RESTRICT'
    )


def downgrade():
    op.drop_constraint('fk_order_member_id', 'order', type_='foreignkey')
