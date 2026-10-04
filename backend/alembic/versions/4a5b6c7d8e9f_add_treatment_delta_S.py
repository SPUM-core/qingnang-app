"""add expected_delta_S / outcome_delta_S to treatment_plans

Revision ID: 4a5b6c7d8e9f
Revises: 9a8b7c6d5e4f
Create Date: 2026-10-02 12:00:00.000000

背景：T3 撤方回弹验证（青囊agent §0.4e 护栏四）需要存储干预前预期 ΔS 位移和
停药后实际观测位移，以区分"根因解决的正确方案"和"对症压制的错误方案"。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4a5b6c7d8e9f'
down_revision: Union[str, None] = '9a8b7c6d5e4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('treatment_plans', sa.Column('expected_delta_S', sa.JSON(), nullable=True))
    op.add_column('treatment_plans', sa.Column('outcome_delta_S', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('treatment_plans', 'outcome_delta_S')
    op.drop_column('treatment_plans', 'expected_delta_S')
