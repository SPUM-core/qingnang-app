"""dev_seed 数据注入 — 已废弃

本迁移原为开发环境注入测试账号（13800138000 / 13900139000）。
2026-09-27 决策：移除开发账号数据注入逻辑，保留 dev_seed 列的 schema 变更
（该列已存在于生产库，用于标识系统来源账号）。

账号注入工作由 Alembic data migration 独立负责，禁止在 schema migration 中夹带。

Revision ID: b2c3d4e5f6a7
Revises: 1e57d54d7a5b
Create Date: 2026-09-26 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = '1e57d54d7a5b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # schema：users 增加 dev_seed 标记列（结构变更）
    # 注：原 DEV_ACCOUNTS 数据注入已废弃（2026-09-27）
    #     开发账号不再注入，所有真实业务账号均由注册流程或种子脚本产生
    op.add_column(
        'users',
        sa.Column('dev_seed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )


def downgrade() -> None:
    op.drop_column('users', 'dev_seed')
