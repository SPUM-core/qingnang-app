"""rename observations.pathologies -> topology_states

Revision ID: 64c3a1b9bdaf_x
Revises: 64c3a1b9bdaf
Create Date: 2026-10-11

本体论裁定（2026-10-11）：青囊「无病实体论」，「病理」命名诱发病症措辞
与红色警告卡暗示，违反本体论。字段语义为「当前拓扑状态标签」，重命名对齐。
"""
from alembic import op
import sqlalchemy as sa

revision = "64c3a1b9bdaf_x"
down_revision = "64c3a1b9bdaf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("observations", "pathologies",
                    new_column_name="topology_states",
                    existing_type=sa.JSON(),
                    nullable=True)


def downgrade() -> None:
    op.alter_column("observations", "topology_states",
                    new_column_name="pathologies",
                    existing_type=sa.JSON(),
                    nullable=True)
