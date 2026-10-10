"""add_birth_location_to_users

Revision ID: b3c4d5e6f7a8
Revises: 5a6b7c8d9e0f
Create Date: 2026-10-08

真太阳时校正必需字段：出生地 + 经纬度
出生时柱 = 北京时间时辰 + (birth_longitude - 120) × 4 分钟

"""
from alembic import op
import sqlalchemy as sa

revision = 'b3c4d5e6f7a8'
down_revision = '5a6b7c8d9e0f'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('birth_city', sa.String(30), nullable=True))
    op.add_column('users', sa.Column('birth_longitude', sa.Float(), nullable=True))
    op.add_column('users', sa.Column('birth_latitude', sa.Float(), nullable=True))


def downgrade():
    op.drop_column('users', 'birth_latitude')
    op.drop_column('users', 'birth_longitude')
    op.drop_column('users', 'birth_city')
