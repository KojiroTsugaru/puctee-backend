from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from datetime import timedelta
from botocore.exceptions import ClientError
import logging
from typing import List
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

from app.core.auth import (
    verify_password,
    create_access_token,
    get_password_hash,
    get_current_username
)
from app.core.config import settings
from app.db.session import get_db
from app.models import User, UserTrustStats
from app.schemas import User as UserSchema, UserCreate, Token, UserUpdate, UserResponse, UserTrustStatsResponse
from app.core.s3 import upload_to_s3
from app.services.push_notification import push_notification_service

router = APIRouter()

@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    # ユーザーをデータベースから取得
    result = await db.execute(
        select(User).where(User.username == form_data.username)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/", response_model=UserResponse)
async def create_user(
    user: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    # ユーザー名とメールアドレスの重複チェック
    result = await db.execute(
        select(User).where(
            (User.username == user.username) | (User.email == user.email)
        )
    )
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered"
        )

    # ユーザーの作成
    db_user = User(
        email=user.email,
        username=user.username,
        display_name=user.display_name,
        hashed_password=user.hashed_password
    )
    db.add(db_user)
    await db.flush()  # IDを取得するためにflush

    # UserTrustStatsの作成
    trust_stats = UserTrustStats(user_id=db_user.id)
    db.add(trust_stats)
    
    await db.commit()
    await db.refresh(db_user)

    return db_user

@router.get("/me", response_model=UserResponse)
async def get_current_user(
    current_user: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db)
):
    """
    現在のユーザー情報を取得
    """
    result = await db.execute(
        select(User)
        .where(User.username == current_user)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

@router.put("/me", response_model=UserSchema)
async def update_user_me(
    user_update: UserUpdate,
    current_username: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.username == current_username)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Update user fields
    for field, value in user_update.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return user

@router.get("/search", response_model=List[UserResponse])
async def search_users(
    query: str = Query(..., description="Search query for display_name or username"),
    current_user: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db)
):
    try:
        # Get current user with friends relationship loaded
        result = await db.execute(
            select(User)
            .options(selectinload(User.friends))
            .where(User.username == current_user)
        )
        current_user_obj = result.scalar_one_or_none()
        if not current_user_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Current user not found"
            )

        # Search query pattern
        search_query = f"%{query}%"

        # Get friend IDs
        friend_ids = [f.id for f in current_user_obj.friends]

        # First, get friends matching the search query
        friends_result = await db.execute(
            select(User)
            .where(
                and_(
                    or_(
                        User.display_name.ilike(search_query),
                        User.username.ilike(search_query)
                    ),
                    User.id != current_user_obj.id,
                    User.id.in_(friend_ids)
                )
            )
            .limit(10)
        )
        friends = friends_result.scalars().all()

        # Then, get other users matching the search query
        other_users_result = await db.execute(
            select(User)
            .where(
                and_(
                    or_(
                        User.display_name.ilike(search_query),
                        User.username.ilike(search_query)
                    ),
                    User.id != current_user_obj.id,
                    ~User.id.in_(friend_ids),
                    ~User.id.in_([friend.id for friend in friends])
                )
            )
            .limit(10)
        )
        other_users = other_users_result.scalars().all()

        # Combine results with friends first and ensure it's a list
        return [*friends, *other_users]  # Use list unpacking to ensure it's a list

    except Exception as e:
        # エラーの詳細をログに記録
        print(f"Error in search_users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while searching users: {str(e)}"
        )

@router.get("/{user_id}", response_model=UserSchema)
async def read_user(
    user_id: int,
    current_user: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

@router.put("/me/push-token")
async def update_push_token(
    push_token: str,
    current_user: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db)
):
    """
    ユーザーのプッシュトークンを更新する
    """
    # Verify the current user is updating their own push token
    result = await db.execute(
        select(User).where(User.username == current_user)
    )
    current_user_obj = result.scalar_one_or_none()
    if not current_user_obj:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user's push token"
        )

    # Update push token
    current_user_obj.push_token = push_token
    await db.commit()
    return {"message": "Push token updated successfully"}

@router.get("/me/trust-stats", response_model=UserTrustStatsResponse)
async def get_my_trust_stats(
    current_username: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db)
):
    """
    現在のユーザーの信頼度統計を取得する
    """
    # ユーザーを取得
    result = await db.execute(
        select(User).where(User.username == current_username)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # 信頼度統計を取得
    result = await db.execute(
        select(UserTrustStats).where(UserTrustStats.user_id == user.id)
    )
    trust_stats = result.scalar_one_or_none()
    if not trust_stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trust stats not found"
        )

    return trust_stats

@router.post("/profile-image")
async def upload_profile_image(
    file: UploadFile = File(...),
    current_username: User = Depends(get_current_username),
    db: AsyncSession = Depends(get_db)
):
    """
    プロフィール画像をアップロードする
    """
    
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    result = await db.execute(
        select(User).where(User.username == current_username)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    try:
        # S3にアップロード
        image_url = await upload_to_s3(file, user.id)
        
        # ユーザーのプロフィール画像URLを更新
        user.profile_image_url = image_url
        await db.commit()
        await db.refresh(user)
        
        return { 
                "message": "profile image uploaded successfully",
                "url": image_url
            }
    except ClientError as e:
        # S3 側のエラー
        await db.rollback()
        logger.error("S3 upload failed", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="S3 へのアップロードに失敗しました"
        )
    except Exception as e:
        await db.rollback()
        logger.error("Unexpected error in profile-image endpoint", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="サーバーエラーが発生しました"
        )

@router.post("/me/test-push")
async def test_push_notification(
    title: str = "Test Notification",
    body: str = "This is a test notification",
    current_user: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db)
):
    """
    現在のユーザーにテスト用のプッシュ通知を送信する
    """
    # 現在のユーザーを取得
    result = await db.execute(
        select(User).where(User.username == current_user)
    )
    current_user_obj = result.scalar_one_or_none()
    if not current_user_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if not current_user_obj.push_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no push token"
        )

    # テスト通知を送信
    success = await push_notification_service.send_notification(
        device_token=current_user_obj.push_token,
        title=title,
        body=body,
        data={"type": "test_notification"}
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send notification"
        )

    return {"message": "Test notification sent successfully"}