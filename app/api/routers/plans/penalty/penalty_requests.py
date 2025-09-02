# Penalty approval request endpoints
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, update
from app.core.auth import get_current_username
from app.db.session import get_db
from app.models import User, Plan, plan_participants, PenaltyApprovalRequest, Penalty
from app.schemas import (
    PenaltyApprovalRequestCreate,
    PenaltyApprovalRequestResponse,
    PenaltyApprovalStatus
)
from app.services.push_notification import send_penalty_approval_request_notification
from app.core.s3 import upload_proof_image_to_s3
from datetime import datetime, timezone
import base64

router = APIRouter()

@router.post("/{plan_id}/penalty-approval-request", response_model=PenaltyApprovalRequestResponse)
async def send_penalty_approval_request(
    plan_id: int,
    request_data: PenaltyApprovalRequestCreate,
    current_user: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db),
):
    """Send penalty approval request with optional comment and proof image"""
    # Get current user (requesting approval)
    result = await db.execute(
        select(User).where(User.username == current_user)
    )
    requesting_user = result.scalar_one_or_none()
    if not requesting_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Verify the plan exists and user is a participant
    result = await db.execute(
        select(Plan)
        .options(selectinload(Plan.participants))
        .where(Plan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )
    
    # Check if requesting user is a participant
    if requesting_user not in plan.participants:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only plan participants can request penalty approval"
        )
    
    # Check if requesting user has penalty_status 'required'
    result = await db.execute(
        select(plan_participants).where(
            plan_participants.c.plan_id == plan_id,
            plan_participants.c.user_id == requesting_user.id
        )
    )
    requesting_participant = result.first()
    if not requesting_participant or requesting_participant.penalty_status != 'required':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only request approval for penalties with 'required' status"
        )
    
    # Check if there's already a pending approval request
    result = await db.execute(
        select(PenaltyApprovalRequest).where(
            PenaltyApprovalRequest.plan_id == plan_id,
            PenaltyApprovalRequest.penalty_user_id == requesting_user.id,
            PenaltyApprovalRequest.status == 'pending'
        )
    )
    existing_request = result.scalar_one_or_none()
    if existing_request:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="There is already a pending approval request for this user"
        )
    
    # Update penalty status to pendingApproval
    stmt = (
        update(plan_participants)
        .where(
            plan_participants.c.plan_id == plan_id,
            plan_participants.c.user_id == requesting_user.id
        )
        .values(penalty_status='pendingApproval')
    )
    await db.execute(stmt)
    
    # Create penalty approval request
    approval_request = PenaltyApprovalRequest(
        plan_id=plan_id,
        penalty_user_id=requesting_user.id,
        comment=request_data.comment,
        proof_image_url=None  # Will be set after S3 upload if image data provided
    )
    db.add(approval_request)
    await db.commit()
    await db.refresh(approval_request)
    
    # Handle proof image data upload to S3 if provided
    if request_data.proof_image_data:
        try:
            # Decode base64 image data if it's base64 encoded
            if isinstance(request_data.proof_image_data, str):
                image_data = base64.b64decode(request_data.proof_image_data)
            else:
                image_data = request_data.proof_image_data
            
            # Upload to S3
            proof_image_url = await upload_proof_image_to_s3(
                image_data=image_data,
                user_id=requesting_user.id,
                request_id=approval_request.id
            )
            
            # Update approval request with S3 URL
            approval_request.proof_image_url = proof_image_url
            await db.commit()
            await db.refresh(approval_request)
            
        except Exception as e:
            print(f"Failed to upload proof image: {str(e)}")
            # Continue without failing the entire request
    
    # Get all participants except the requesting user
    other_participants = [p for p in plan.participants if p.id != requesting_user.id]
    
    # Send push notifications to all other participants
    notification_count = 0
    
    for participant in other_participants:
        if participant.push_token:
            try:
                success = await send_penalty_approval_request_notification(
                    device_token=participant.push_token,
                    requesting_user_name=requesting_user.display_name,
                    request_id=approval_request.id,
                    plan_title=plan.title
                )
                if success:
                    notification_count += 1
                    print(f"Penalty approval notification sent to {participant.username}")
                else:
                    print(f"Failed to send notification to {participant.username}")
            except Exception as e:
                print(f"Failed to send notification to {participant.username}: {str(e)}")
    
    # Log the approval request
    print(f"Penalty approval requested by {requesting_user.username} for plan {plan.id}")
    return approval_request

@router.post("/{plan_id}/penalty-approval-request-solo", response_model=PenaltyApprovalRequestResponse)
async def send_penalty_approval_request_solo(
    plan_id: int,
    request_data: PenaltyApprovalRequestCreate,
    current_user: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db),
):
    """Send penalty approval request and auto-approve if plan has only 1 participant"""
    # Get current user (requesting approval)
    result = await db.execute(
        select(User).where(User.username == current_user)
    )
    requesting_user = result.scalar_one_or_none()
    if not requesting_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Verify the plan exists and user is a participant
    result = await db.execute(
        select(Plan)
        .options(selectinload(Plan.participants))
        .where(Plan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )
    
    # Check if requesting user is a participant
    if requesting_user not in plan.participants:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only plan participants can request penalty approval"
        )
    
    # Check if requesting user has penalty_status 'required'
    result = await db.execute(
        select(plan_participants).where(
            plan_participants.c.plan_id == plan_id,
            plan_participants.c.user_id == requesting_user.id
        )
    )
    requesting_participant = result.first()
    if not requesting_participant or requesting_participant.penalty_status != 'required':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only request approval for penalties with 'required' status"
        )
    
    # Check if there's already a pending approval request
    result = await db.execute(
        select(PenaltyApprovalRequest).where(
            PenaltyApprovalRequest.plan_id == plan_id,
            PenaltyApprovalRequest.penalty_user_id == requesting_user.id,
            PenaltyApprovalRequest.status == 'pending'
        )
    )
    existing_request = result.scalar_one_or_none()
    if existing_request:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="There is already a pending approval request for this user"
        )
    
    # Check number of participants
    participant_count = len(plan.participants)
    
    # Create penalty approval request
    approval_request = PenaltyApprovalRequest(
        plan_id=plan_id,
        penalty_user_id=requesting_user.id,
        comment=request_data.comment,
        proof_image_url=None  # Will be set after S3 upload if image data provided
    )
    
    # If only 1 participant, auto-approve immediately
    if participant_count == 1:
        approval_request.status = 'approved'
        approval_request.approver_user_id = requesting_user.id  # Self-approved
        approval_request.approved_at = datetime.now(timezone.utc)
        
        # Update penalty status to 'completed' immediately
        penalty_status = 'completed'
        penalty_completed_at = datetime.now(timezone.utc)
        
        print(f"Auto-approving penalty for single participant {requesting_user.username} in plan {plan.id}")
    else:
        # Multiple participants - keep as pending and update to pendingApproval
        penalty_status = 'pendingApproval'
        penalty_completed_at = None
        
        print(f"Penalty approval requested by {requesting_user.username} for plan {plan.id} with {participant_count} participants")
    
    # Update penalty status
    stmt = (
        update(plan_participants)
        .where(
            plan_participants.c.plan_id == plan_id,
            plan_participants.c.user_id == requesting_user.id
        )
        .values(
            penalty_status=penalty_status,
            penalty_completed_at=penalty_completed_at
        )
    )
    await db.execute(stmt)
    
    db.add(approval_request)
    await db.commit()
    await db.refresh(approval_request)
    
    # Handle proof image data upload to S3 if provided
    if request_data.proof_image_data:
        try:
            # Decode base64 image data if it's base64 encoded
            if isinstance(request_data.proof_image_data, str):
                image_data = base64.b64decode(request_data.proof_image_data)
            else:
                image_data = request_data.proof_image_data
            
            # Upload to S3
            proof_image_url = await upload_proof_image_to_s3(
                image_data=image_data,
                user_id=requesting_user.id,
                request_id=approval_request.id
            )
            
            # Update approval request with S3 URL
            approval_request.proof_image_url = proof_image_url
            await db.commit()
            await db.refresh(approval_request)
            
        except Exception as e:
            print(f"Failed to upload proof image: {str(e)}")
            # Continue without failing the entire request
    
    # Send notifications only if multiple participants and not auto-approved
    if participant_count > 1:
        # Get all participants except the requesting user
        other_participants = [p for p in plan.participants if p.id != requesting_user.id]
        
        # Send push notifications to all other participants
        notification_count = 0
        
        for participant in other_participants:
            if participant.push_token:
                try:
                    success = await send_penalty_approval_request_notification(
                        device_token=participant.push_token,
                        requesting_user_name=requesting_user.display_name,
                        request_id=approval_request.id,
                        plan_title=plan.title
                    )
                    if success:
                        notification_count += 1
                        print(f"Penalty approval notification sent to {participant.username}")
                    else:
                        print(f"Failed to send notification to {participant.username}")
                except Exception as e:
                    print(f"Failed to send notification to {participant.username}: {str(e)}")
    
    return approval_request

@router.post("/{plan_id}/penalty-approval/{request_id}", response_model=PenaltyApprovalRequestResponse)
async def approve_penalty(
    plan_id: int,
    request_id: int,
    current_user: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db),
):
    """
    Approve a penalty approval request
    
    Args:
        plan_id: Plan ID
        request_id: Penalty approval request ID
        current_user: Current authenticated user (approver)
        db: Database session
    
    Returns:
        Penalty approval information
    """
    # Get current user (approver)
    result = await db.execute(
        select(User).where(User.username == current_user)
    )
    approver = result.scalar_one_or_none()
    if not approver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approver user not found"
        )
    
    # Verify the plan exists
    result = await db.execute(
        select(Plan).where(Plan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )
    
    # Get the approval request
    result = await db.execute(
        select(PenaltyApprovalRequest).where(
            PenaltyApprovalRequest.id == request_id,
            PenaltyApprovalRequest.plan_id == plan_id
        )
    )
    approval_request = result.scalar_one_or_none()
    if not approval_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Penalty approval request not found"
        )
    
    # Check if request is still pending
    if approval_request.status != 'pending':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve request with status '{approval_request.status}'"
        )
    
    # Check if approver is a participant in the plan
    result = await db.execute(
        select(plan_participants).where(
            plan_participants.c.plan_id == plan_id,
            plan_participants.c.user_id == approver.id
        )
    )
    approver_participant = result.first()
    if not approver_participant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only plan participants can approve penalties"
        )
    
    # Check if penalty user is a participant and has 'pending' status
    result = await db.execute(
        select(plan_participants).where(
            plan_participants.c.plan_id == plan_id,
            plan_participants.c.user_id == approval_request.penalty_user_id
        )
    )
    penalty_participant = result.first()
    if not penalty_participant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Penalty user is not a participant in this plan"
        )
    
    if penalty_participant.penalty_status != 'required':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only approve penalties with 'required' status"
        )
    
    # Check if approval already exists (status is already approved)
    if approval_request.status == 'approved':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Penalty has already been approved"
        )
    
    # Update approval request to approved
    approval_request.status = 'approved'
    approval_request.approver_user_id = approver.id
    approval_request.approved_at = datetime.now(timezone.utc)
    approval_request.updated_at = datetime.now(timezone.utc)
    
    # Update penalty status to 'completed'
    stmt = (
        update(plan_participants)
        .where(
            plan_participants.c.plan_id == plan_id,
            plan_participants.c.user_id == approval_request.penalty_user_id
        )
        .values(
            penalty_status='completed',
            penalty_completed_at=datetime.now(timezone.utc)
        )
    )
    await db.execute(stmt)
    
    await db.commit()
    await db.refresh(approval_request)
    
    # Get penalty user for logging
    result = await db.execute(
        select(User).where(User.id == approval_request.penalty_user_id)
    )
    penalty_user = result.scalar_one_or_none()
    
    # Log penalty approval
    print(f"Penalty approved for user {penalty_user.username if penalty_user else approval_request.penalty_user_id} in plan {plan.id} by {approver.username}")
    
    return approval_request

@router.post("/{plan_id}/penalty-decline/{request_id}")
async def decline_penalty(
    plan_id: int,
    request_id: int,
    current_user: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db),
):
    """
    Decline a penalty approval request
    
    Args:
        plan_id: Plan ID
        request_id: Penalty approval request ID
        current_user: Current authenticated user (decliner)
        db: Database session
    
    Returns:
        Success message
    """
    # Get current user (decliner)
    result = await db.execute(
        select(User).where(User.username == current_user)
    )
    decliner = result.scalar_one_or_none()
    if not decliner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Verify the plan exists
    result = await db.execute(
        select(Plan).where(Plan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )
    
    # Get the approval request
    result = await db.execute(
        select(PenaltyApprovalRequest).where(
            PenaltyApprovalRequest.id == request_id,
            PenaltyApprovalRequest.plan_id == plan_id
        )
    )
    approval_request = result.scalar_one_or_none()
    if not approval_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Penalty approval request not found"
        )
    
    # Check if request is still pending
    if approval_request.status != 'pending':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot decline request with status '{approval_request.status}'"
        )
    
    # Check if decliner is a participant in the plan
    result = await db.execute(
        select(plan_participants).where(
            plan_participants.c.plan_id == plan_id,
            plan_participants.c.user_id == decliner.id
        )
    )
    decliner_participant = result.first()
    if not decliner_participant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only plan participants can decline penalties"
        )
    
    # Update approval request status to 'declined'
    approval_request.status = 'declined'
    approval_request.updated_at = datetime.now(timezone.utc)
    
    # Update penalty status back to 'required'
    stmt = (
        update(plan_participants)
        .where(
            plan_participants.c.plan_id == plan_id,
            plan_participants.c.user_id == approval_request.penalty_user_id
        )
        .values(
            penalty_status='required',
            penalty_completed_at=None  # Clear completion timestamp
        )
    )
    await db.execute(stmt)
    
    await db.commit()
    
    # Get penalty user for logging
    result = await db.execute(
        select(User).where(User.id == approval_request.penalty_user_id)
    )
    penalty_user = result.scalar_one_or_none()
    
    # Log penalty decline
    print(f"Penalty declined for user {penalty_user.username if penalty_user else approval_request.penalty_user_id} in plan {plan.id} by {decliner.username}")
    
    return {
        "message": "Penalty approval request declined successfully",
        "request_id": request_id,
        "plan_id": plan_id
    }

@router.get("/{plan_id}/penalty-approval-requests", response_model=List[PenaltyApprovalRequestResponse])
async def get_penalty_approval_requests(
    plan_id: int,
    current_user: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all penalty approval requests for a specific plan
    
    Args:
        plan_id: Plan ID
        current_user: Current authenticated user
        db: Database session
    
    Returns:
        List of penalty approval requests
    """
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
    
    # Verify the plan exists and user is a participant
    result = await db.execute(
        select(Plan)
        .options(selectinload(Plan.participants))
        .where(Plan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )
    
    # Check if user is a participant
    if user not in plan.participants:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only plan participants can view penalty approval requests"
        )
    
    # Get all penalty approval requests for this plan
    result = await db.execute(
        select(PenaltyApprovalRequest)
        .where(PenaltyApprovalRequest.plan_id == plan_id)
        .order_by(PenaltyApprovalRequest.created_at.desc())
    )
    approval_requests = result.scalars().all()
    
    return approval_requests

@router.get("/{plan_id}/penalty-approval-requests/{request_id}", response_model=PenaltyApprovalRequestResponse)
async def get_penalty_approval_request(
    plan_id: int,
    request_id: int,
    current_user: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific penalty approval request
    
    Args:
        plan_id: Plan ID
        request_id: Approval request ID
        current_user: Current authenticated user
        db: Database session
    
    Returns:
        Penalty approval request details
    """
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
    
    # Verify the plan exists and user is a participant
    result = await db.execute(
        select(Plan)
        .options(selectinload(Plan.participants))
        .where(Plan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )
    
    # Check if user is a participant
    if user not in plan.participants:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only plan participants can view penalty approval requests"
        )
    
    # Get the specific approval request
    result = await db.execute(
        select(PenaltyApprovalRequest).where(
            PenaltyApprovalRequest.id == request_id,
            PenaltyApprovalRequest.plan_id == plan_id
        )
    )
    approval_request = result.scalar_one_or_none()
    if not approval_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Penalty approval request not found"
        )
    
    return approval_request

@router.get("/penalty-approval-requests/{request_id}", response_model=PenaltyApprovalRequestResponse)
async def get_penalty_approval_request_by_id(
    request_id: int,
    current_user: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific penalty approval request by ID only
    
    Args:
        request_id: Approval request ID
        current_user: Current authenticated user
        db: Database session
    
    Returns:
        Penalty approval request details
    """
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
    
    # Get the specific approval request with penalty information
    result = await db.execute(
        select(PenaltyApprovalRequest)
        .options(selectinload(PenaltyApprovalRequest.penalty))
        .where(PenaltyApprovalRequest.id == request_id)
    )
    approval_request = result.scalar_one_or_none()
    if not approval_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Penalty approval request not found"
        )
    
    # Verify the plan exists and user is a participant
    result = await db.execute(
        select(Plan)
        .options(selectinload(Plan.participants))
        .where(Plan.id == approval_request.plan_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )
    
    # Check if user is a participant
    if user not in plan.participants:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only plan participants can view penalty approval requests"
        )
    
    # Create response with penalty_name
    response_data = {
        "id": approval_request.id,
        "plan_id": approval_request.plan_id,
        "penalty_user_id": approval_request.penalty_user_id,
        "penalty_name": approval_request.penalty.content if approval_request.penalty else None,
        "comment": approval_request.comment,
        "proof_image_url": approval_request.proof_image_url,
        "status": approval_request.status,
        "approver_user_id": approval_request.approver_user_id,
        "approved_at": approval_request.approved_at,
        "created_at": approval_request.created_at,
        "updated_at": approval_request.updated_at,
    }
    
    return PenaltyApprovalRequestResponse(**response_data)

@router.get("/{plan_id}/penalty-approval-status/{penalty_user_id}", response_model=PenaltyApprovalStatus)
async def get_penalty_approval_status(
    plan_id: int,
    penalty_user_id: int,
    current_user: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db),
):
    """
    Get penalty approval status for a specific user in a plan
    
    Args:
        plan_id: Plan ID
        penalty_user_id: User ID who has the penalty
        current_user: Current authenticated user
        db: Database session
    
    Returns:
        Penalty approval status information
    """
    # Verify the plan exists
    result = await db.execute(
        select(Plan).where(Plan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )
    
    # Check if approval exists
    result = await db.execute(
        select(PenaltyApprovalRequest).where(
            PenaltyApprovalRequest.plan_id == plan_id,
            PenaltyApprovalRequest.penalty_user_id == penalty_user_id,
            PenaltyApprovalRequest.status == 'approved'
        )
    )
    approval = result.scalar_one_or_none()
    
    if approval:
        return PenaltyApprovalStatus(
            plan_id=plan_id,
            penalty_user_id=penalty_user_id,
            has_approval=True,
            approver_user_id=approval.approver_user_id,
            approved_at=approval.approved_at
        )
    else:
        return PenaltyApprovalStatus(
            plan_id=plan_id,
            penalty_user_id=penalty_user_id,
            has_approval=False
        )
