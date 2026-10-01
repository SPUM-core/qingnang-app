"""add patient_height_m to observations

Revision ID: c1d2e3f4a5b6
Revises: a1b2c3d4e5f6
Create Date: 2026-09-27 18:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # P0-2 联动：身高必录（单位：米），旧记录为 NULL → 算法链路按"未测量"处理
    op.add_column('observations', sa.Column('patient_height_m', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('observations', 'patient_height_m')
