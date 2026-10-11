"""merge trajectory/city/kinship heads

Revision ID: 64c3a1b9bdaf
Revises: d5e6f7a8b9c0, b3c4d5e6f7a8, f0a1b2c3d4e5
Create Date: 2026-10-11 22:10:59.151772

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '64c3a1b9bdaf'
down_revision: Union[str, None] = ('d5e6f7a8b9c0', 'b3c4d5e6f7a8', 'f0a1b2c3d4e5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
