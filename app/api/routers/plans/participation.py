# Plan participation endpoints
from app.core.auth import get_current_username
from app.db.session import get_db
from app.models import User, Plan
from app.schemas import Plan as PlanSchema
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

router = APIRouter()

@router.post("/{plan_id}/join")
async def join_plan(
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
        select(Plan).where(Plan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )

    # Add user to plan
    if user not in plan.participants:
        plan.participants.append(user)
        await db.commit()

    return {"message": "Successfully joined plan"}

@router.delete("/{plan_id}/leave")
async def leave_plan(
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
        select(Plan).where(Plan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )

    # Remove user from plan
    if user in plan.participants:
        plan.participants.remove(user)
        await db.commit()

    return {"message": "Successfully left plan"}