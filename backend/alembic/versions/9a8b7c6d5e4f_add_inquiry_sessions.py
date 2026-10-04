"""add inquiry_sessions

Revision ID: 9a8b7c6d5e4f
Revises: 3c4d5e6f7a8b
Create Date: 2026-10-02 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9a8b7c6d5e4f'
down_revision: Union[str, None] = '3c4d5e6f7a8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'inquiry_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=True),
        sa.Column('stage', sa.String(20), server_default='initial'),
        sa.Column('status', sa.String(20), server_default='active'),
        sa.Column('user_context', sa.JSON(), nullable=True),
        sa.Column('history', sa.JSON(), nullable=True),
        sa.Column('answer_bank', sa.JSON(), nullable=True),
        sa.Column('summary', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_inquiry_sessions_user_id', 'inquiry_sessions', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_inquiry_sessions_user_id', table_name='inquiry_sessions')
    op.drop_table('inquiry_sessions')
