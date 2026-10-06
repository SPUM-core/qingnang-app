"""add_city_to_users
Revision ID: 5a6b7c8d9e0f
Revises: f18fc84bf775
Create Date: 2026-10-05

"""
from alembic import op
import sqlalchemy as sa

revision = '5a6b7c8d9e0f'
down_revision = 'f18fc84bf775'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('city', sa.String(20), nullable=True))


def downgrade():
    op.drop_column('users', 'city')
