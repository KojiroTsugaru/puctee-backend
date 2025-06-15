"""add_user_trust_stats

Revision ID: 92f3a2c1f4aa
Revises: e0afb7bac429
Create Date: 2025-06-01 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '92f3a2c1f4aa'
down_revision: Union[str, None] = 'e0afb7bac429'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # UserTrustStatsテーブルの作成
    op.create_table(
        'user_trust_stats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('total_plans', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('late_plans', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('on_time_streak', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('best_on_time_streak', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_arrival_status', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_trust_stats_id'), 'user_trust_stats', ['id'], unique=False)
    op.create_index(op.f('ix_user_trust_stats_user_id'), 'user_trust_stats', ['user_id'], unique=True)


def downgrade() -> None:
    # UserTrustStatsテーブルの削除
    op.drop_index(op.f('ix_user_trust_stats_user_id'), table_name='user_trust_stats')
    op.drop_index(op.f('ix_user_trust_stats_id'), table_name='user_trust_stats')
    op.drop_table('user_trust_stats')
