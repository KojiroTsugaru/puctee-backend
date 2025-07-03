from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
from datetime import datetime, UTC
from app.core.auth import get_current_username
from app.db.session import get_db
from app.models import User, Plan
from app.schemas import Plan as PlanSchema, PlanListRequest
from fastapi import status as http_status

router = APIRouter()

@router.post("/list", response_model=List[PlanSchema])
async def read_plans(
    params: PlanListRequest,
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
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Get plans with eager loading and order by start_time
    result = await db.execute(
        select(Plan)
        .options(
            selectinload(Plan.participants),
            selectinload(Plan.locations),
            selectinload(Plan.penalties),
            selectinload(Plan.invites)
        )
        .where(
            Plan.participants.contains(user),
            Plan.status.in_(params.plan_status),
            Plan.start_time > datetime.now(UTC)  # 現在時刻より後の予定のみ
        )
        .order_by(Plan.start_time)  # start_timeで昇順ソート
        .offset(params.skip)
        .limit(params.limit)
    )
    plans = result.scalars().all()
    return plans

@router.get("/{plan_id}", response_model=PlanSchema)
async def read_plan(
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
            status_code=http_status.HTTP_404_NOT_FOUND,
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
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )
    return plan