"""add_arrival_status_to_plans

Revision ID: e0afb7bac429
Revises: c1a4bb4bd041
Create Date: 2025-06-01 15:40:56.572568

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e0afb7bac429'
down_revision: Union[str, None] = 'c1a4bb4bd041'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('plans', sa.Column('arrival_status', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('plans', 'arrival_status')
