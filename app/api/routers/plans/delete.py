from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.auth import get_current_username
from app.db.session import get_db
from app.models import User, Plan
from app.services.scheduler.eventbridge_scheduler import cancel_silent_for_plan

router = APIRouter()

@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(
    plan_id: int,
    current_user: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db)
):
    # Get current user
    result = await db.execute(
        select(User).where(User.username == current_user)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Get plan
    result = await db.execute(
        select(Plan).where(
            Plan.id == plan_id,
            Plan.participants.contains(user)
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )

    # Delete plan
    await db.delete(plan)
    await db.commit()
    
    await cancel_silent_for_plan(plan_id)
    return None