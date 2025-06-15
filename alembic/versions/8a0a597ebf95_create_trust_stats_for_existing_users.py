"""create trust stats for existing users

Revision ID: 8a0a597ebf95
Revises: a951c29aeed6
Create Date: 2024-03-21 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
from app.models import User, UserTrustStats

# revision identifiers, used by Alembic.
revision: str = '8a0a597ebf95'
down_revision: Union[str, None] = 'a951c29aeed6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 既存のユーザーに対してUserTrustStatsを作成
    bind = op.get_bind()
    session = Session(bind=bind)
    
    # すべてのユーザーを取得
    users = session.query(User).all()
    
    # 各ユーザーに対してUserTrustStatsを作成
    for user in users:
        # 既にUserTrustStatsが存在するか確認
        existing_stats = session.query(UserTrustStats).filter_by(user_id=user.id).first()
        if not existing_stats:
            # UserTrustStatsが存在しない場合は作成
            trust_stats = UserTrustStats(user_id=user.id)
            session.add(trust_stats)
    
    session.commit()


def downgrade() -> None:
    # UserTrustStatsを削除
    op.execute('DELETE FROM user_trust_stats')
