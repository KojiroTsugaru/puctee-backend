# Location endpoints
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.auth import get_current_username
from app.db.session import get_db
from app.models import User, Plan, Location
from app.schemas import Location as LocationSchema, LocationCreate
from typing import List
from datetime import datetime

router = APIRouter()

@router.post("/{plan_id}/locations", response_model=LocationSchema)
async def create_location(
    plan_id: int,
    location: LocationCreate,
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

    # Create location
    db_location = Location(
        **location.model_dump(),
        plan_id=plan_id,
        user_id=user.id
    )
    db.add(db_location)
    await db.commit()
    await db.refresh(db_location)
    return db_location

@router.get("/{plan_id}/locations", response_model=List[LocationSchema])
async def read_locations(
    plan_id: int,
    since: datetime = None,
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

    # Get locations
    query = select(Location).where(Location.plan_id == plan_id)
    if since:
        query = query.where(Location.created_at >= since)
    result = await db.execute(query)
    locations = result.scalars().all()
    return locations