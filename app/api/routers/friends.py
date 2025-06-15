from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List

from app.core.auth import get_current_username
from app.db.session import get_db
from app.models import User, FriendInvite
from app.schemas import User as UserSchema, FriendInvite as FriendInviteSchema, FriendInviteCreate, UserResponse

router = APIRouter()

@router.get("/", response_model=list[UserResponse])
async def read_friends(
    current_user: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db)
):
    # Get current user with friends relationship loaded
    result = await db.execute(
        select(User)
        .options(selectinload(User.friends))
        .where(User.username == current_user)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user.friends

@router.post("/friend-invites", response_model=FriendInviteSchema)
async def create_friend_invite(
    invite: FriendInviteCreate,
    current_user: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db)
):
    # Get current user
    result = await db.execute(
        select(User).where(User.username == current_user)
    )
    sender = result.scalar_one_or_none()
    if not sender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Get receiver
    result = await db.execute(
        select(User).where(User.id == invite.receiver_id)
    )
    receiver = result.scalar_one_or_none()
    if not receiver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receiver not found"
        )

    # Check if invite already exists
    result = await db.execute(
        select(FriendInvite).where(
            (FriendInvite.sender_id == sender.id) & (FriendInvite.receiver_id == receiver.id) |
            (FriendInvite.sender_id == receiver.id) & (FriendInvite.receiver_id == sender.id)
        )
    )
    existing_invite = result.scalar_one_or_none()
    if existing_invite:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Friend invite already exists"
        )

    # Create invite
    db_invite = FriendInvite(
        sender_id=sender.id,
        receiver_id=receiver.id
    )
    db.add(db_invite)
    await db.commit()
    await db.refresh(db_invite)
    return db_invite

@router.get("/friend-invites", response_model=List[FriendInviteSchema])
async def read_friend_invites(
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

    # Get invites
    result = await db.execute(
        select(FriendInvite).where(FriendInvite.receiver_id == user.id)
    )
    invites = result.scalars().all()
    return invites

@router.post("/friend-invites/{invite_id}/accept")
async def accept_friend_invite(
    invite_id: int,
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

    # Get invite
    result = await db.execute(
        select(FriendInvite).where(
            FriendInvite.id == invite_id,
            FriendInvite.receiver_id == user.id,
            FriendInvite.status == "pending"
        )
    )
    invite = result.scalar_one_or_none()
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Friend invite not found"
        )

    # Get sender
    result = await db.execute(
        select(User).where(User.id == invite.sender_id)
    )
    sender = result.scalar_one_or_none()
    if not sender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sender not found"
        )

    # Update invite status
    invite.status = "accepted"
    await db.commit()

    # Add friendship
    user.friends.append(sender)
    sender.friends.append(user)
    await db.commit()

    return {"message": "Friend invite accepted"}

@router.post("/friend-invites/{invite_id}/decline")
async def decline_friend_invite(
    invite_id: int,
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

    # Get invite
    result = await db.execute(
        select(FriendInvite).where(
            FriendInvite.id == invite_id,
            FriendInvite.receiver_id == user.id,
            FriendInvite.status == "pending"
        )
    )
    invite = result.scalar_one_or_none()
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Friend invite not found"
        )

    # Update invite status
    invite.status = "declined"
    await db.commit()

    return {"message": "Friend invite declined"} 