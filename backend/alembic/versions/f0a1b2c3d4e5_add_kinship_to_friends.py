"""add kinship fields to friends

Revision ID: f0a1b2c3d4e5
Revises: c1d2e3f4a5b6
Create Date: 2026-10-05 19:30:00.000000

给 friends 表加 kinship_type 和 generation_level，
让家人合并数据推算 / 代际遗传分析有字段可用。
"""
from alembic import op
import sqlalchemy as sa

revision = 'f0a1b2c3d4e5'
down_revision = 'c1d2e3f4a5b6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('friends', sa.Column('kinship_type', sa.String(length=20), nullable=True))
    op.add_column('friends', sa.Column('generation_level', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('friends', 'generation_level')
    op.drop_column('friends', 'kinship_type')
