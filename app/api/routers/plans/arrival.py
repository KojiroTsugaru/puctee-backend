from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.auth import get_current_username
from app.db.session import get_db
from app.models import Plan, User, UserTrustStats
from app.schemas import LocationCheck, LocationCheckResponse
from app.services.push_notification import send_arrival_check_notification
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
        
        # Compare current time with start time
        current_time = datetime.now(timezone.utc)
        time_diff = (current_time - plan.start_time).total_seconds()
        
        # Update plan status based on arrival result
        if is_arrived:
            plan.status = "completed"
        else:
            plan.status = "on_going"
        
        # Update statistics
        await update_trust_stats(plan_id, user, plan, is_arrived, time_diff, db)
        
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
    plan_id: int,
    user: User,
    plan: Plan,
    is_arrived: bool,
    time_diff: float,
    db: AsyncSession
) -> None:
    """
    Update user's trust statistics
    
    Args:
        user: User object
        plan: Plan object
        is_arrived: Whether arrived or not
        time_diff: Time difference from start time (seconds)
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
        if time_diff <= 0:  # Before start time
            plan.arrival_status = "on_time"
            trust_stats.on_time_streak += 1
            trust_stats.best_on_time_streak = max(
                trust_stats.best_on_time_streak,
                trust_stats.on_time_streak
            )
        else:  # After start time
            plan.arrival_status = "late"
            trust_stats.late_plans += 1
            trust_stats.on_time_streak = 0
    else:
        plan.arrival_status = "not_arrived"
        trust_stats.on_time_streak = 0

    # Common statistics update
    trust_stats.total_plans += 1
    trust_stats.last_arrival_status = plan.arrival_status

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