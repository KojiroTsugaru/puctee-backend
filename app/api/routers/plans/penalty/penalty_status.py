# Penalty status management endpoints
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.core.auth import get_current_username
from app.db.session import get_db
from app.models import User, Plan, plan_participants
from app.schemas import (
    PenaltyStatusUpdate, 
    PenaltyStatusResponse
)
from datetime import datetime, timezone

router = APIRouter()

@router.get("/{plan_id}/me/penalty-status", response_model=PenaltyStatusResponse)
async def get_my_penalty_status(
    plan_id: int,
    current_user: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's penalty status for a specific plan"""
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
    
    # Verify the plan exists
    result = await db.execute(
        select(Plan).where(Plan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )
    
    # Get user's penalty status from plan_participants table
    result = await db.execute(
        select(plan_participants).where(
            plan_participants.c.plan_id == plan_id,
            plan_participants.c.user_id == user.id
        )
    )
    participant = result.first()
    if not participant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a participant in this plan"
        )
    
    return PenaltyStatusResponse(
        plan_id=plan_id,
        user_id=user.id,
        penalty_status=participant.penalty_status,
        penalty_completed_at=participant.penalty_completed_at,
        updated_at=datetime.now(timezone.utc)
    )

@router.put("/penalty-status", response_model=PenaltyStatusResponse)
async def update_penalty_status_endpoint(
    penalty_update: PenaltyStatusUpdate,
    current_user: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db),
):
    """
    Update penalty status for a specific user in a plan
    
    Args:
        penalty_update: Penalty status update data
        current_user: Current authenticated user
        db: Database session
    
    Returns:
        Updated penalty status information
    """
    # Verify the plan exists
    result = await db.execute(
        select(Plan).where(Plan.id == penalty_update.plan_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )
    
    # Verify the user exists
    result = await db.execute(
        select(User).where(User.id == penalty_update.user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if the user is a participant in the plan
    result = await db.execute(
        select(plan_participants).where(
            plan_participants.c.plan_id == penalty_update.plan_id,
            plan_participants.c.user_id == penalty_update.user_id
        )
    )
    participant = result.first()
    if not participant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a participant in this plan"
        )
    
    # Prepare update values
    update_values = {
        'penalty_status': penalty_update.penalty_status
    }
    
    # If status is being set to 'completed', record the timestamp
    if penalty_update.penalty_status == 'completed':
        update_values['penalty_completed_at'] = datetime.now(timezone.utc)
    elif penalty_update.penalty_status in ['none', 'pending', 'exempted']:
        # Clear penalty_completed_at for other statuses
        update_values['penalty_completed_at'] = None
    
    # Update penalty status in plan_participants table
    stmt = (
        update(plan_participants)
        .where(
            plan_participants.c.plan_id == penalty_update.plan_id,
            plan_participants.c.user_id == penalty_update.user_id
        )
        .values(**update_values)
    )
    
    await db.execute(stmt)
    await db.commit()
    
    # Get updated participant data
    result = await db.execute(
        select(plan_participants).where(
            plan_participants.c.plan_id == penalty_update.plan_id,
            plan_participants.c.user_id == penalty_update.user_id
        )
    )
    updated_participant = result.first()
    
    # Log penalty status update
    print(f"Penalty status updated for user {user.username} in plan {plan.id}: {penalty_update.penalty_status}")
    
    return PenaltyStatusResponse(
        plan_id=penalty_update.plan_id,
        user_id=penalty_update.user_id,
        penalty_status=updated_participant.penalty_status,
        penalty_completed_at=updated_participant.penalty_completed_at,
        updated_at=datetime.now(timezone.utc)
    )
