"""merge heads

Revision ID: d1e2f3g4h5i6
Revises: a951c29aeed6, c2d3e4f5g6h7
Create Date: 2025-08-25 12:16:12.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3g4h5i6'
down_revision: Union[str, None] = ('a951c29aeed6', 'c2d3e4f5g6h7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This is a merge migration - no changes needed
    pass


def downgrade() -> None:
    # This is a merge migration - no changes needed
    pass
