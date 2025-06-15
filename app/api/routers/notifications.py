from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.core.auth import get_current_username
from app.db.session import get_db
from app.models import User, Notification
from app.schemas import NotificationResponse
from app.schemas import NotificationBase as NotificationSchema
from app.schemas import NotificationCreate

router = APIRouter()

@router.get("/notifications", response_model=List[NotificationSchema])
async def read_notifications(
    skip: int = 0,
    limit: int = 100,
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

    # Get notifications
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    notifications = result.scalars().all()
    return notifications

@router.post("/notifications", response_model=NotificationSchema)
async def create_notification(
    notification: NotificationCreate,
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

    # Create notification
    db_notification = Notification(
        **notification.model_dump(),
        user_id=user.id
    )
    db.add(db_notification)
    await db.commit()
    await db.refresh(db_notification)
    return db_notification

@router.put("/notifications/{notification_id}/read")
async def mark_notification_as_read(
    notification_id: int,
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

    # Get notification
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user.id
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    # Mark as read
    notification.is_read = True
    await db.commit()
    return {"message": "Notification marked as read"}

@router.put("/notifications/read-all")
async def mark_all_notifications_as_read(
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

    # Get all unread notifications
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == user.id,
            Notification.is_read == False
        )
    )
    notifications = result.scalars().all()

    # Mark all as read
    for notification in notifications:
        notification.is_read = True
    await db.commit()
    return {"message": "All notifications marked as read"}

@router.delete("/notifications/{notification_id}")
async def delete_notification(
    notification_id: int,
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

    # Get notification
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user.id
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    # Delete notification
    await db.delete(notification)
    await db.commit()
    return {"message": "Notification deleted"}

@router.get("/notifications/unread-count")
async def get_unread_notifications_count(
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

    # Count unread notifications
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == user.id,
            Notification.is_read == False
        )
    )
    unread_count = len(result.scalars().all())
    return {"unread_count": unread_count} 