"""add_observation_analysis_fields

Revision ID: 3c4d5e6f7a8b
Revises: c1d2e3f4a5b6
Create Date: 2026-09-28 12:00:00.000000

Add status, s_graph, pathologies, diagnosis_summary to observations.
"""
from alembic import op
import sqlalchemy as sa


revision = '3c4d5e6f7a8b'
down_revision = 'c1d2e3f4a5b6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('observations',
        sa.Column('status', sa.String(length=20), server_default='uploading', nullable=True))
    op.add_column('observations',
        sa.Column('s_graph', sa.JSON(), nullable=True))
    op.add_column('observations',
        sa.Column('pathologies', sa.JSON(), nullable=True))
    op.add_column('observations',
        sa.Column('diagnosis_summary', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('observations', 'diagnosis_summary')
    op.drop_column('observations', 'pathologies')
    op.drop_column('observations', 's_graph')
    op.drop_column('observations', 'status')
