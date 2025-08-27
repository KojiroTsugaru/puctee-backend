from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from app.core.auth import get_current_username
from app.db.session import get_db
from app.models import Plan, User, UserTrustStats, plan_participants
from app.schemas import LocationCheck, LocationCheckResponse
from app.services.push_notification import send_arrival_check_notification
from app.services.trust_level import update_trust_level
from datetime import datetime, timezone

router = APIRouter()

@router.post("/{plan_id}/arrival", response_model=LocationCheckResponse)
async def check_arrival(
    plan_id: int,
    location: LocationCheck,
    current_user: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint for individual arrival check
    Compare user's current location with plan destination to determine arrival
    """
    try:
        # Get current user
        result = await db.execute(
            select(User).where(User.username == current_user)
        )
        user = result.scalar_one_or_none()
        if not user:
            print(f"User not found: {current_user}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Get plan (including location information and participants)
        result = await db.execute(
            select(Plan)
            .options(
                selectinload(Plan.locations),
                selectinload(Plan.participants)
            )
            .where(Plan.id == plan_id)
        )
        plan = result.scalar_one_or_none()
        if not plan:
            print(f"Plan not found: {plan_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plan not found"
            )

        # Check if user is a participant in the plan
        if user not in plan.participants:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not a participant of this plan"
            )

        destination = plan.locations[0]  # Use first location as destination

        # Arrival determination (e.g., consider arrived if within 100 meters)
        distance = calculate_distance(
            location.latitude,
            location.longitude,
            destination.latitude,
            destination.longitude
        )
        is_arrived = distance <= 0.1  # Within 100 meters
        
        # Update plan status based on arrival result
        if is_arrived:
            plan.status = "completed"
        else:
            plan.status = "ongoing"
        
        # Update penalty status in plan_participants
        await update_penalty_status(user, plan, is_arrived, db)
        
        # Update statistics
        await update_trust_stats(user, plan, is_arrived, db)
        
        # Send push notification to the user who checked arrival
        if user.push_token:
            try:
                await send_arrival_check_notification(
                    plan=plan,
                    device_token=user.push_token,
                    is_arrived=is_arrived
                )
            except Exception as e:
                # Log error but don't fail the entire request
                print(f"Failed to send notification to {user.username}: {str(e)}")
            
        # Save changes to database
        await db.commit()
        await db.refresh(plan)

        return LocationCheckResponse(
            is_arrived=is_arrived,
            distance=distance
        )
    except Exception as e:
        # Rollback if error occurs
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while updating arrival status: {str(e)}"
        )

async def update_trust_stats(
    user: User,
    plan: Plan,
    is_arrived: bool,
    db: AsyncSession
) -> None:
    """
    Update user's trust statistics
    
    Args:
        user: User object
        plan: Plan object
        is_arrived: Whether arrived or not
        db: Database session
    """
    # Get user's trust statistics
    result = await db.execute(
        select(UserTrustStats).where(UserTrustStats.user_id == user.id)
    )
    trust_stats = result.scalar_one_or_none()
    if not trust_stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User trust stats not found"
        )

    # Update statistics based on arrival status
    if is_arrived:
        plan.arrival_status = "on_time"
        trust_stats.on_time_streak += 1
        trust_stats.best_on_time_streak = max(
            trust_stats.best_on_time_streak,
            trust_stats.on_time_streak
            )
    else:
        plan.arrival_status = "late"
        trust_stats.late_plans += 1
        trust_stats.on_time_streak = 0
        
    # Common statistics update
    trust_stats.total_plans += 1
    
    # Use trust level service to calculate and update trust level
    trust_level_explanation = update_trust_level(trust_stats, plan.arrival_status)
    
    # Log the trust level change for debugging
    print(f"Trust level updated for user {user.username}: {trust_level_explanation}")
    
    # Ensure trust_stats changes are tracked by the session
    db.add(trust_stats)

async def update_penalty_status(
    user: User,
    plan: Plan,
    is_arrived: bool,
    db: AsyncSession
) -> None:
    """
    Update penalty status in plan_participants table
    
    Args:
        user: User object
        plan: Plan object
        is_arrived: Whether user arrived or not
        db: Database session
    """
    # Determine penalty status based on arrival
    if is_arrived:
        penalty_status = 'none'  # No penalty needed - user arrived successfully
    else:
        penalty_status = 'pending'  # Penalty pending - user failed to arrive
    
    # Update penalty status in plan_participants table
    stmt = (
        update(plan_participants)
        .where(
            plan_participants.c.plan_id == plan.id,
            plan_participants.c.user_id == user.id
        )
        .values(
            penalty_status=penalty_status,
            checked_at=datetime.now(timezone.utc)
        )
    )
    
    await db.execute(stmt)
    
    # Log penalty status update
    print(f"Penalty status updated for user {user.username} in plan {plan.id}: {penalty_status}")

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points - in kilometers
    Using Haversine formula
    """
    from math import radians, sin, cos, sqrt, atan2

    R = 6371  # Earth's radius (kilometers)

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    distance = R * c

    return distance 