# Penalty endpoints
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.auth import get_current_username
from app.db.session import get_db
from app.models import User, Plan, Penalty
from app.schemas import Penalty as PenaltySchema, PenaltyCreate

router = APIRouter()

@router.get("/{plan_id}/penalties", response_model=List[PenaltySchema])
async def read_penalties(
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

    # Get penalties
    result = await db.execute(
        select(Penalty).where(Penalty.plan_id == plan_id)
    )
    penalties = result.scalars().all()
    return penalties

@router.post("/{plan_id}/penalties", response_model=PenaltySchema)
async def create_penalty(
    plan_id: int,
    penalty: PenaltyCreate,
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

    # Create penalty
    db_penalty = Penalty(
        **penalty.model_dump(),
        plan_id=plan_id,
        user_id=user.id
    )
    db.add(db_penalty)
    await db.commit()
    await db.refresh(db_penalty)
    return db_penalty

@router.post("/{plan_id}/penalties/{penalty_id}/proof")
async def upload_penalty_proof(
    plan_id: int,
    penalty_id: int,
    proof_url: str,
    current_user: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db)
):
    # Get current user
    result = await db.execute(select(User).where(User.username == current_user))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Get plan
    result = await db.execute(
        select(Plan).where(
            Plan.id == plan_id,
            Plan.participants.contains(user)
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    # Get penalty
    result = await db.execute(
        select(Penalty).where(
            Penalty.id == penalty_id,
            Penalty.plan_id == plan_id,
            Penalty.user_id == user.id
        )
    )
    penalty = result.scalar_one_or_none()
    if not penalty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Penalty not found")

    # Update penalty
    penalty.proof_url = proof_url
    await db.commit()
    return {"message": "Proof uploaded successfully"}