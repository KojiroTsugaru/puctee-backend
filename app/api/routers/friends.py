from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import List

from app.core.auth import get_current_username
from app.db.db_users import get_current_user
from app.db.session import get_db
from app.models import User, FriendInvite as FriendInviteModel
from app.schemas import FriendInvite, FriendInviteCreate, UserResponse
from app.services.push_notification import send_friend_invite_notification

router = APIRouter()

@router.get("/list", response_model=list[UserResponse])
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

@router.post("/friend-invites", response_model=FriendInvite)
async def create_friend_invite(
    invite: FriendInviteCreate,
    sender: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
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
    pending_invite_exists = await db.execute(
        select(FriendInviteModel).where(
            FriendInviteModel.status == "pending",
            FriendInviteModel.sender_id.in_([sender.id, receiver.id]),
            FriendInviteModel.receiver_id.in_([sender.id, receiver.id]),
            FriendInviteModel.sender_id != FriendInviteModel.receiver_id
        )
    )
    if pending_invite_exists.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Friend invite already exists"
        )

    # Create invite
    db_invite = FriendInviteModel(
        sender_id=sender.id,
        receiver_id=receiver.id
    )
    db.add(db_invite)
    await db.commit()
    await db.refresh(db_invite)

    # Send push notification if receiver has a device token
    if receiver.push_token:
        await send_friend_invite_notification(
            device_token=receiver.push_token,
            sender_username=sender.username,
            invite_id=db_invite.id
        )

    return db_invite

@router.get("/friend-invites/received", response_model=List[FriendInvite])
async def read_received_invites(
    current_user: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db),
):
    # Get current user with friends relationship loaded
    result = await db.execute(
        select(User)
        .options(selectinload(User.received_invites))
        .where(User.username == current_user)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get only pending received invites
    invite_result = await db.execute(
        select(FriendInviteModel).where(
            FriendInviteModel.receiver_id == user.id,
            FriendInviteModel.status == "pending"  # Filter only pending
        )
    )
    pending_invites = invite_result.scalars().all()
    return pending_invites


@router.get("/friend-invites/sent", response_model=List[FriendInvite])
async def read_sent_invites(
    current_user: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db)
):
    # Get current user with friends relationship loaded
    result = await db.execute(
        select(User)
        .options(selectinload(User.sent_invites))
        .where(User.username == current_user)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get only pending sent invites
    invite_result = await db.execute(
        select(FriendInviteModel).where(
            FriendInviteModel.sender_id == user.id,
            FriendInviteModel.status == "pending"  # Filter only pending
        )
    )
    pending_invites = invite_result.scalars().all()
    return pending_invites

@router.post("/friend-invites/{invite_id}/accept")
async def accept_friend_invite(
    invite_id: int,
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

    # Get the invite
    invite_result = await db.execute(
        select(FriendInviteModel).where(
            FriendInviteModel.id == invite_id,
            FriendInviteModel.receiver_id == user.id,
            FriendInviteModel.status == "pending"
        )
    )
    invite = invite_result.scalar_one_or_none()
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Friend invite not found"
        )

    # Get sender with friends relationship loaded
    sender_result = await db.execute(
        select(User)
        .options(selectinload(User.friends))
        .where(User.id == invite.sender_id)
    )
    sender = sender_result.scalar_one_or_none()
    if not sender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sender not found"
        )

    # Update invite status
    invite.status = "accepted"
    
    # Add friendship (bidirectional)
    if sender not in user.friends:
        user.friends.append(sender)
    if user not in sender.friends:
        sender.friends.append(user)

    await db.commit()
    
    return {"message": "Friend invite accepted successfully"}

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

    # Get the invite
    invite_result = await db.execute(
        select(FriendInviteModel).where(
            FriendInviteModel.id == invite_id,
            FriendInviteModel.receiver_id == user.id,
            FriendInviteModel.status == "pending"
        )
    )
    invite = invite_result.scalar_one_or_none()
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Friend invite not found"
        )

    # Update invite status
    invite.status = "declined"
    await db.commit()

    return {"message": "Friend invite declined successfully"}

@router.delete("/{friend_id}")
async def remove_friend(
    friend_id: int,
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

    # Get friend user with friends relationship loaded
    friend_result = await db.execute(
        select(User)
        .options(selectinload(User.friends))
        .where(User.id == friend_id)
    )
    friend = friend_result.scalar_one_or_none()
    if not friend:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Friend user not found"
        )

    # Check if they are actually friends
    if friend not in user.friends:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Users are not friends"
        )

    # Remove friendship (bidirectional)
    if friend in user.friends:
        user.friends.remove(friend)
    if user in friend.friends:
        friend.friends.remove(user)

    await db.commit()
    
    return {"message": f"Successfully removed friend (ID: {friend_id}) from friends"}