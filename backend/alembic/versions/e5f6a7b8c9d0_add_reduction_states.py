"""add reduction_states — 归约算法库活算子状态持久化

Revision ID: e5f6a7b8c9d0
Revises: 64c3a1b9bdaf_x
Create Date: 2026-10-14 20:00:00.000000

背景：归约引擎 Phase 1 修复2 — ReductionState 每次 API 调用新建零状态，
L4 闭环回填的修正值当场丢弃，"活"算子实际是"每次重生的算子"。
此迁移新增 reduction_states 表，存储：
  - broken_node_gain（断链点增益系数）
  - peak_suppress（尖峰压制系数）
  - ke_conflict_mult（KE 冲突升级系数）
  - season_corrections / hour_corrections（乘数表修正 JSON）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = '64c3a1b9bdaf_x'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'reduction_states',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('label', sa.Text(), default='default'),
        # 活算子权重（R3 增益中庸 + L4 回填修正）
        sa.Column('broken_node_gain', sa.Float(), default=1.0),
        sa.Column('peak_suppress', sa.Float(), default=0.3),
        sa.Column('ke_conflict_mult', sa.Float(), default=1.5),
        # 乘数表覆盖修正（JSON）
        sa.Column('season_corrections', sa.JSON(), nullable=True),
        sa.Column('hour_corrections', sa.JSON(), nullable=True),
        # 元信息
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    # 插入默认行（让引擎启动时能直接加载）
    op.execute(
        "INSERT INTO reduction_states (label, broken_node_gain, peak_suppress, ke_conflict_mult) "
        "VALUES ('default', 1.0, 0.3, 1.5) ON CONFLICT DO NOTHING"
    )


def downgrade() -> None:
    op.drop_table('reduction_states')
