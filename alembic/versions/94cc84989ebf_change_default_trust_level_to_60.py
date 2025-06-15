"""change default trust level to 60

Revision ID: 94cc84989ebf
Revises: 8a0a597ebf95
Create Date: 2024-03-21 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '94cc84989ebf'
down_revision: Union[str, None] = '8a0a597ebf95'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 既存のレコードのtrust_levelを60に更新
    op.execute("UPDATE user_trust_stats SET trust_level = 60.0 WHERE trust_level = 50.0")
    
    # デフォルト値を60に変更
    op.alter_column('user_trust_stats', 'trust_level',
                    existing_type=sa.Float(),
                    server_default='60.0',
                    existing_nullable=True)


def downgrade() -> None:
    # 既存のレコードのtrust_levelを50に戻す
    op.execute("UPDATE user_trust_stats SET trust_level = 50.0 WHERE trust_level = 60.0")
    
    # デフォルト値を50に戻す
    op.alter_column('user_trust_stats', 'trust_level',
                    existing_type=sa.Float(),
                    server_default='50.0',
                    existing_nullable=True)
