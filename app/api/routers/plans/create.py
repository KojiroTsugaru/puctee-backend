from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.auth import get_current_username
from app.db.session import get_db
from app.models import User, Plan, Location, Penalty, PlanInvite
from app.schemas import Plan as PlanSchema, PlanCreate

router = APIRouter()

@router.post("/create", response_model=PlanSchema)
async def create_plan(
    plan: PlanCreate,
    current_user: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db),
):
    # 1) 作成者取得
    result = await db.execute(select(User).where(User.username == current_user))
    user: User = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # 2) Plan レコード作成
    db_plan = Plan(title=plan.title, start_time=plan.start_time)
    db_plan.participants.append(user)  # 作成者は自動的に参加者として追加
    
    db.add(db_plan)
    await db.flush()  # db_plan.id を確定

    # 3) 他の参加者を招待
    if plan.participants:
        # 自身のIDを除外し、重複を防ぐ
        other_participant_ids = set(pid for pid in plan.participants if pid != user.id)
        
        for uid in other_participant_ids:
            other = await db.get(User, uid)
            if other:
                invite = PlanInvite(plan_id=db_plan.id, user_id=other.id)
                db.add(invite)

    # 4) Location, Penalty の追加
    loc = plan.location
    db.add(Location(
        plan_id=db_plan.id,
        user_id=user.id,
        name = loc.name,
        latitude=loc.latitude,
        longitude=loc.longitude,
    ))
    if plan.penalty:
        pen = plan.penalty
        db.add(Penalty(
            plan_id=db_plan.id,
            user_id=user.id,
            content=pen.content,
            status=pen.status,
        ))

    # 5) コミット
    await db.commit()

    # 6) リレーションをまとめてロード
    result = await db.execute(
        select(Plan)
        .options(
            selectinload(Plan.participants),
            selectinload(Plan.penalties),
            selectinload(Plan.locations),
            selectinload(Plan.invites)
        )
        .where(Plan.id == db_plan.id)
    )
    full_plan: Plan = result.scalar_one()

    return full_plan