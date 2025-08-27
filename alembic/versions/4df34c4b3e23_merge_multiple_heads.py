"""merge multiple heads

Revision ID: 4df34c4b3e23
Revises: 94cc84989ebf, f3g4h5i6j7k8
Create Date: 2025-08-25 13:14:13.549661

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4df34c4b3e23'
down_revision: Union[str, None] = ('94cc84989ebf', 'f3g4h5i6j7k8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make approver_user_id nullable
    op.alter_column('penalty_approval_requests', 'approver_user_id',
                    existing_type=sa.INTEGER(),
                    nullable=True)


def downgrade() -> None:
    # Make approver_user_id not nullable again
    op.alter_column('penalty_approval_requests', 'approver_user_id',
                    existing_type=sa.INTEGER(),
                    nullable=False)
