from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from .session import get_db
from app.core.auth import get_current_username
from app.models import User

async def get_current_user(
    current_username: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Fetch the current User by username. Raises 404 if not found.
    """
    result = await db.execute(
        select(User)
        .where(User.username == current_username)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user