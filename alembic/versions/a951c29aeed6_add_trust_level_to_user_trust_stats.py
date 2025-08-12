"""add trust level to user trust stats

Revision ID: a951c29aeed6
Revises: 957a989171e3
Create Date: 2024-03-21 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a951c29aeed6'
down_revision: Union[str, None] = '957a989171e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add trust_level column (default value 50.0)
    op.add_column('user_trust_stats', sa.Column('trust_level', sa.Float(), nullable=False, server_default='50.0'))


def downgrade() -> None:
    # Delete trust_level column
    op.drop_column('user_trust_stats', 'trust_level')
