# app/api/routers/plans/location_validation.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.auth import get_current_username
from app.db.session import get_db
from app.models import Plan, User
from app.schemas import LocationShareValidationRequest, LocationShareValidationResponse, UserInfo
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

@router.post("/validate-location-share", response_model=LocationShareValidationResponse)
async def validate_location_share_access(
    request: LocationShareValidationRequest,
    db: AsyncSession = Depends(get_db),
    current_username: str = Depends(get_current_username)
):
    """
    Supabase WebSocket接続前の検証エンドポイント
    プラン参加者かどうかとユーザー情報を返す
    """
    try:
        # プランの存在確認
        result = await db.execute(select(Plan).where(Plan.id == request.plan_id))
        plan = result.scalar_one_or_none()
        if not plan:
            return LocationShareValidationResponse(
                valid=False,
                error="Plan not found"
            )

        # ユーザーの存在確認
        user_result = await db.execute(select(User).where(User.username == current_username))
        user = user_result.scalar_one_or_none()
        if not user:
            return LocationShareValidationResponse(
                valid=False,
                error="User not found"
            )

        # プラン参加者かどうかの確認
        participation_check = select(Plan.id).where(
            Plan.id == request.plan_id,
            Plan.participants.any(User.username == current_username)
        )
        participation_result = await db.execute(participation_check)
        is_participant = participation_result.scalar_one_or_none() is not None

        if not is_participant:
            return LocationShareValidationResponse(
                valid=False,
                error="User is not a participant of this plan"
            )

        # 成功時はユーザー情報も返す
        return LocationShareValidationResponse(
            valid=True,
            user_info=UserInfo(
                user_id=user.id,
                display_name=user.display_name,
                profile_image_url=user.profile_image_url
            )
        )

    except Exception as e:
        return LocationShareValidationResponse(
            valid=False,
            error=f"Validation error: {str(e)}"
        )

@router.get("/plan/{plan_id}/participants")
async def get_plan_participants(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    current_username: str = Depends(get_current_username)
):
    """
    プランの参加者一覧を取得（位置情報共有用）
    """
    try:
        # プランの存在確認と参加者の取得
        result = await db.execute(
            select(Plan)
            .where(Plan.id == plan_id)
            .options(selectinload(Plan.participants))
        )
        plan = result.scalar_one_or_none()
        
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        # 現在のユーザーが参加者かどうか確認
        user_is_participant = any(p.username == current_username for p in plan.participants)
        if not user_is_participant:
            raise HTTPException(status_code=403, detail="Not a participant of this plan")

        # 参加者情報を返す
        participants = [
            {
                "user_id": participant.id,
                "display_name": participant.display_name,
                "profile_image_url": participant.profile_image_url
            }
            for participant in plan.participants
        ]

        return {
            "plan_id": plan_id,
            "participants": participants
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching participants: {str(e)}")
