from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.auth import get_current_username
from app.db.session import get_db
from app.models import Plan, User, Location, UserTrustStats
from app.schemas import LocationCheck, LocationCheckResponse
from datetime import datetime, timezone

router = APIRouter()

@router.post("/check-arrival", response_model=LocationCheckResponse)
async def check_arrival(
    location: LocationCheck,
    current_user: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db)
):
    """
    単独到着チェック用エンドポイント
    ユーザーの現在位置とプランの目的地を比較して到着判定を行う
    """
    try:
        # 現在のユーザーを取得
        result = await db.execute(
            select(User).where(User.username == current_user)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # プランを取得（場所情報も含めて）
        result = await db.execute(
            select(Plan)
            .options(selectinload(Plan.locations))
            .where(Plan.id == location.plan_id)
        )
        plan = result.scalar_one_or_none()
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plan not found"
            )

        # ユーザーがプランの参加者かチェック
        if user not in plan.participants:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not a participant of this plan"
            )

        destination = plan.locations[0]  # 最初の場所を目的地として使用

        # 到着判定（例：100メートル以内なら到着と判定）
        distance = calculate_distance(
            location.latitude,
            location.longitude,
            destination.latitude,
            destination.longitude
        )
        is_arrived = distance <= 0.03  # 30メートル以内
        
        # 現在時刻と開始時刻を比較
        current_time = datetime.now(timezone.utc)
        time_diff = (current_time - plan.start_time).total_seconds()
        
        # 統計情報の更新
        await update_trust_stats(user, plan, is_arrived, time_diff, db)
            
        # 変更をデータベースに保存
        await db.commit()
        await db.refresh(plan)

        return LocationCheckResponse(
            is_arrived=is_arrived,
            distance=distance
        )
    except Exception as e:
        # エラーが発生した場合はロールバック
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while updating arrival status: {str(e)}"
        )

async def update_trust_stats(
    user: User,
    plan: Plan,
    is_arrived: bool,
    time_diff: float,
    db: AsyncSession
) -> None:
    """
    ユーザーの信頼度統計情報を更新する
    
    Args:
        user: ユーザーオブジェクト
        plan: プランオブジェクト
        is_arrived: 到着したかどうか
        time_diff: 開始時刻との時間差（秒）
        db: データベースセッション
    """
    # ユーザーの信頼度統計を取得
    result = await db.execute(
        select(UserTrustStats).where(UserTrustStats.user_id == user.id)
    )
    trust_stats = result.scalar_one_or_none()
    if not trust_stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User trust stats not found"
        )

    # 到着状態に応じて統計情報を更新
    if is_arrived:
        if time_diff <= 0:  # 開始時刻前
            plan.arrival_status = "on_time"
            trust_stats.on_time_streak += 1
            trust_stats.best_on_time_streak = max(
                trust_stats.best_on_time_streak,
                trust_stats.on_time_streak
            )
        else:  # 開始時刻後
            plan.arrival_status = "late"
            trust_stats.late_plans += 1
            trust_stats.on_time_streak = 0
    else:
        plan.arrival_status = "not_arrived"
        trust_stats.on_time_streak = 0

    # 共通の統計情報更新
    trust_stats.total_plans += 1
    trust_stats.last_arrival_status = plan.arrival_status

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    2点間の距離を計算 - キロメートル単位
    ハーバーサイン公式を使用
    """
    from math import radians, sin, cos, sqrt, atan2

    R = 6371  # 地球の半径（キロメートル）

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    distance = R * c

    return distance 