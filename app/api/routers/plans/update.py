from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.auth import get_current_username
from app.db.session import get_db
from app.models import Plan, User, Location, Penalty
from app.schemas import PlanUpdate, Plan as PlanSchema
from app.services.scheduler.eventbridge_scheduler import schedule_silent_for_plan

router = APIRouter()

@router.put("/{plan_id}", response_model=PlanSchema)
async def update_plan(
    plan_id: int,
    plan_update: PlanUpdate,
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

    # Get plan with eager loading
    result = await db.execute(
        select(Plan)
        .options(
            selectinload(Plan.participants),
            selectinload(Plan.locations),
            selectinload(Plan.penalties),
            selectinload(Plan.invites)
        )
        .where(Plan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )

    # Update plan fields
    update_data = plan_update.model_dump(exclude_unset=True)
    
    # Handle relationships separately
    if 'participants' in update_data and update_data['participants'] is not None:
        # Update participants (sent as List[int])
        plan.participants = []
        result = await db.execute(
            select(User).where(User.id.in_(update_data['participants']))
        )
        users = result.scalars().all()
        plan.participants.extend(users)

    if 'location' in update_data:
        # Update location (sent as LocationCreate)
        plan.locations = []
        location_data = update_data['location']
        location = Location(
            plan_id=plan.id,
            user_id=user.id,
            name=location_data['name'],
            latitude=location_data['latitude'],
            longitude=location_data['longitude']
        )
        plan.locations.append(location)

    if 'penalty' in update_data and update_data['penalty'] is not None:
        # Update penalty (sent as Optional[PenaltyCreate])
        plan.penalties = []
        penalty_data = update_data['penalty']
        penalty = Penalty(
            plan_id=plan.id,
            user_id=user.id,
            content=penalty_data['content'],
            status=penalty_data.get('status', 'pending')
        )
        plan.penalties.append(penalty)

    # Update other fields
    for field, value in update_data.items():
        if field not in ['participants', 'location', 'penalty']:
            setattr(plan, field, value)

    # Commit changes
    await db.commit()
    await db.refresh(plan)

    start_utc = plan.start_time.astimezone(timezone.utc)
    await schedule_silent_for_plan(plan.id, start_utc, db)
    
    return plan