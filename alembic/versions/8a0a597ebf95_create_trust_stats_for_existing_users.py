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
    # Create UserTrustStats for existing users
    bind = op.get_bind()
    session = Session(bind=bind)
    
    # Get all users
    users = session.query(User).all()
    
    # Create UserTrustStats for each user
    for user in users:
        # Check if UserTrustStats already exists
        existing_stats = session.query(UserTrustStats).filter_by(user_id=user.id).first()
        if not existing_stats:
            # Create UserTrustStats if it doesn't exist
            trust_stats = UserTrustStats(user_id=user.id)
            session.add(trust_stats)
    
    session.commit()


def downgrade() -> None:
    # Delete UserTrustStats
    op.execute('DELETE FROM user_trust_stats')
