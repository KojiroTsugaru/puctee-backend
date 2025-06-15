from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from app.db.session import get_db
from app.core.auth import get_current_username
from app.models import Plan
from app.models import User
from app.models import PlanInvite as PlanInviteModel
from app.schemas import PlanInviteCreate, PlanInvite, PlanInviteResponse
from typing import List

router = APIRouter()

@router.post("/invites/create", response_model=PlanInviteResponse)
async def create_plan_invite(
    invite: PlanInviteCreate,
    current_user: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db)
):
    # Check if plan exists and user is creator
    plan = await db.get(Plan, invite.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to invite to this plan")
    
    # Check if user to invite exists
    user_to_invite = await db.get(User, invite.user_id)
    if not user_to_invite:
        raise HTTPException(status_code=404, detail="User to invite not found")
    
    # Check if invite already exists
    existing_invite = await db.execute(
        select(PlanInviteModel).where(
            PlanInviteModel.plan_id == invite.plan_id,
            PlanInviteModel.user_id == invite.user_id
        )
    )
    if existing_invite.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Invite already exists")
    
    # Create invite
    new_invite = PlanInviteModel(
        plan_id=invite.plan_id,
        user_id=invite.user_id,
        status="pending"
    )
    db.add(new_invite)
    await db.commit()
    await db.refresh(new_invite)
    
    return new_invite

@router.get("/invites/list", response_model=List[PlanInviteResponse])
async def get_plan_invites(
    current_user: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db)
):
    # Get current user
    result = await db.execute(
        select(User).where(User.username == current_user)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get all pending invites for current user with eager loading
    result = await db.execute(
        select(PlanInviteModel)
        .options(
            selectinload(PlanInviteModel.plan).selectinload(Plan.participants),
            selectinload(PlanInviteModel.plan).selectinload(Plan.locations),
            selectinload(PlanInviteModel.plan).selectinload(Plan.penalties),
            selectinload(PlanInviteModel.plan).selectinload(Plan.invites)
        )
        .where(
            PlanInviteModel.user_id == user.id,
            PlanInviteModel.status == "pending"
        )
        .order_by(PlanInviteModel.id.desc())
    )
    invites = result.scalars().all()
    
    return invites

@router.put("/invites/{invite_id}", response_model=PlanInviteResponse)
async def update_plan_invite(
    invite_id: int,
    status: str,
    current_user: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db)
):
    # Get current user
    result = await db.execute(
        select(User).where(User.username == current_user)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get invite with eager loading of plan and its relationships
    result = await db.execute(
        select(PlanInviteModel)
        .options(
            selectinload(PlanInviteModel.plan).selectinload(Plan.participants),
            selectinload(PlanInviteModel.plan).selectinload(Plan.locations),
            selectinload(PlanInviteModel.plan).selectinload(Plan.penalties),
            selectinload(PlanInviteModel.plan).selectinload(Plan.invites)
        )
        .where(PlanInviteModel.id == invite_id)
    )
    invite = result.scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this invite")
    
    # Update status
    invite.status = status
    await db.commit()
    await db.refresh(invite)
    
    # If accepted, add user to plan participants
    if status == "accepted":
        if user not in invite.plan.participants:
            invite.plan.participants.append(user)
            await db.commit()
    
    return invite 