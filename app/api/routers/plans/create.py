from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import logging
from datetime import datetime
import json

from app.core.auth import get_current_username
from app.db.session import get_db
from app.models import User, Plan, Location, Penalty, PlanInvite
from app.schemas import Plan as PlanSchema, PlanCreate
from app.services.push_notification import send_plan_invite_notification

# Configure CloudWatch logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

router = APIRouter()

def log_operation(operation: str, data: dict, user_id: int = None, plan_id: int = None):
    """Helper function to log operations to CloudWatch"""
    log_data = {
        'timestamp': datetime.utcnow().isoformat(),
        'operation': operation,
        'user_id': user_id,
        'plan_id': plan_id,
        'data': data
    }
    logger.info(json.dumps(log_data, default=str))

@router.post("/create", response_model=PlanSchema)
async def create_plan(
    plan: PlanCreate,
    current_user: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db),
):
    try:
        # 1) 作成者取得
        result = await db.execute(select(User).where(User.username == current_user))
        user: User = result.scalar_one_or_none()
        if not user:
            error_msg = f"User not found: {current_user}"
            logger.error(error_msg)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)

        # 2) Plan レコード作成
        db_plan = Plan(title=plan.title, start_time=plan.start_time)
        db_plan.participants.append(user)
        db.add(db_plan)
        await db.flush()
        
        log_operation("plan_created", {"title": plan.title, "start_time": plan.start_time}, user.id, db_plan.id)

        # 3) 他の参加者を招待
        if plan.participants:
            other_participant_ids = set(pid for pid in plan.participants if pid != user.id)
            log_operation("processing_participants", {"count": len(other_participant_ids)}, user.id, db_plan.id)
            
            for uid in other_participant_ids:
                try:
                    other = await db.get(User, uid)
                    if other:
                        invite = PlanInvite(plan_id=db_plan.id, user_id=other.id)
                        db.add(invite)
                        log_operation("invite_created", {"invited_user_id": other.id}, user.id, db_plan.id)
                except Exception as e:
                    logger.error(f"Error inviting user {uid}: {str(e)}", exc_info=True)
                    continue

        # 4) Location, Penalty の追加
        try:
            loc = plan.location
            db.add(Location(
                plan_id=db_plan.id,
                user_id=user.id,
                name=loc.name,
                latitude=loc.latitude,
                longitude=loc.longitude,
            ))
            log_operation("location_added", {"name": loc.name}, user.id, db_plan.id)

            if plan.penalty:
                pen = plan.penalty
                db.add(Penalty(
                    plan_id=db_plan.id,
                    user_id=user.id,
                    content=pen.content,
                    status=pen.status,
                ))
                log_operation("penalty_added", {"content": pen.content}, user.id, db_plan.id)

            # 5) コミット
            await db.commit()
            log_operation("db_commit_success", {}, user.id, db_plan.id)

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
            
            # 7) プラン招待通知を送信
            notification_count = 0
            for invite in full_plan.invites:
                try:
                    other = await db.get(User, invite.user_id)
                    if other and other.push_token:
                        await send_plan_invite_notification(
                            device_token=other.push_token,
                            title="New Plan Invitation",
                            body=f"{user.display_name} invited you to a new plan: {full_plan.title}"
                        )
                        notification_count += 1
                        log_operation("notification_sent", {"to_user_id": other.id}, user.id, db_plan.id)
                except Exception as e:
                    logger.error(f"Error sending notification to user {invite.user_id}: {str(e)}", exc_info=True)
                    continue

            log_operation("create_plan_complete", {"notifications_sent": notification_count}, user.id, db_plan.id)
            return full_plan

        except Exception as e:
            await db.rollback()
            logger.error(f"Error in plan creation transaction: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while creating the plan"
            )

    except HTTPException as he:
        logger.error(f"HTTP Error in create_plan: {str(he.detail)}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error in create_plan: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )