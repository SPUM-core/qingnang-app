"""add trajectory confirmation fields

Revision ID: d5e6f7a8b9c0
Revises: f18fc84bf775
Create Date: 2026-10-11 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, None] = 'f18fc84bf775'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 人生轨迹信息提取：置信度 + 确认状态机字段
    op.add_column('trajectory_events', sa.Column('confidence', sa.Float(), nullable=True))
    op.add_column('trajectory_events', sa.Column('confirmed', sa.Boolean(), nullable=True))
    op.add_column('trajectory_events', sa.Column('pending', sa.Boolean(), nullable=True))
    op.add_column('trajectory_events', sa.Column('proposed_key', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_trajectory_events_proposed_key'), 'trajectory_events', ['proposed_key'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_trajectory_events_proposed_key'), table_name='trajectory_events')
    op.drop_column('trajectory_events', 'proposed_key')
    op.drop_column('trajectory_events', 'pending')
    op.drop_column('trajectory_events', 'confirmed')
    op.drop_column('trajectory_events', 'confidence')
