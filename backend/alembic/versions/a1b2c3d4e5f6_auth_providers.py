"""0002 - auth providers: wechat columns + nullable password

Revision ID: a1b2c3d4e5f6
Revises: 1e57d54d7a5b
Create Date: 2026-09-26 18:30:00

Add WeChat auth columns to users and relax password_hash NOT NULL
so users registered via WeChat login don't need a password.
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'b2c3d4e5f6a7'   # 串在 dev_seed 之后
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. 微信登录标识 ──
    op.add_column('users',
        sa.Column('wechat_openid', sa.String(64), nullable=True))
    op.create_unique_constraint('uq_users_wechat_openid', 'users', ['wechat_openid'])
    op.create_index('ix_users_wechat_openid', 'users', ['wechat_openid'])

    op.add_column('users',
        sa.Column('wechat_unionid', sa.String(64), nullable=True))
    op.create_unique_constraint('uq_users_wechat_unionid', 'users', ['wechat_unionid'])
    op.create_index('ix_users_wechat_unionid', 'users', ['wechat_unionid'])

    # ── 2. 密码哈希允许 NULL（微信用户可无密码） ──
    op.alter_column('users', 'password_hash',
        existing_type=sa.String(255),
        nullable=True)


def downgrade() -> None:
    op.alter_column('users', 'password_hash',
        existing_type=sa.String(255),
        nullable=False)

    op.drop_index('ix_users_wechat_unionid', table_name='users')
    op.drop_constraint('uq_users_wechat_unionid', 'users', type_='unique')
    op.drop_column('users', 'wechat_unionid')

    op.drop_index('ix_users_wechat_openid', table_name='users')
    op.drop_constraint('uq_users_wechat_openid', 'users', type_='unique')
    op.drop_column('users', 'wechat_openid')
