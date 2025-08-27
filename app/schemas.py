from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
# Base schemas
class UserBase(BaseModel):
    email: EmailStr
    display_name: str
    username: str
    profile_image_url: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    display_name: Optional[str] = None
    username: Optional[str] = None
    push_token: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    display_name: str
    username: str
    profile_image_url: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        
class UserSearchResponse(BaseModel):
    profile_image_url: Optional[str] = None

class User(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Auth schemas
class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: str

class TokenData(BaseModel):
    username: Optional[str] = None

class RefreshToken(BaseModel):
    refresh_token: str

# Friend schemas
class FriendInviteBase(BaseModel):
    receiver_id: int

class FriendInviteCreate(FriendInviteBase):
    pass

class FriendInvite(FriendInviteBase):
    id: int
    sender_id: int
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        
# Penalty schemas
class PenaltyBase(BaseModel):
    content: str
    status: str = "pending"

class PenaltyCreate(PenaltyBase):
    content: str
    status: str = "pending"

class PenaltyUpdate(BaseModel):
    status: str
    proof_url: Optional[str] = None

class Penalty(PenaltyBase):
    id: int
    plan_id: int
    user_id: int
    status: str = "pending"
    proof_url: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        
# Location schemas
class LocationBase(BaseModel):
    name: str
    latitude: float
    longitude: float

class LocationCreate(LocationBase):
    pass

class Location(LocationBase):
    id: int
    plan_id: int
    user_id: int

    class Config:
        from_attributes = True
        
class LocationCheck(BaseModel):
    latitude: float
    longitude: float
    
    class Config:
        from_attributes = True
        
class LocationCheckResponse(BaseModel):
    is_arrived: bool
    distance: float
    
    class Config:
        from_attributes = True
    
# Plan schemas
class PlanBase(BaseModel):
    title: str
    start_time: datetime

class PlanCreate(PlanBase):
    penalty: Optional[PenaltyCreate] = None
    location: LocationCreate
    participants: Optional[List[int]] = None # user id of participants

class PlanUpdate(PlanBase):
    status: Optional[str] = None
    penalty: Optional[PenaltyCreate] = None
    location: LocationCreate
    participants: Optional[List[int]] = None # user id of participants

class Plan(PlanBase):
    id: int
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    participants: List[User] = []
    locations: List[Location] = []
    invites: List['PlanInvite'] = []
    penalties: List[Penalty] = []

    class Config: 
        from_attributes = True
        # Output all datetime in seconds-precision ISO8601 (no fractional)
        json_encoders = {
            datetime: lambda v: v.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        
class PlanInvite(BaseModel):
    id: int
    plan_id: int
    user_id: int
    status: str

    class Config:
        from_attributes = True
        
class PlanInviteCreate(BaseModel):
    plan_id: int
    user_id: int

class PlanInviteResponse(BaseModel):
    id: int
    plan_id: int
    user_id: int
    status: str
    plan: Plan

    class Config:
        from_attributes = True
        
class NotificationBase(BaseModel):
    title: str
    content: str
    data: Optional[Dict[str, Any]] = None

class NotificationCreate(NotificationBase):
    user_id: int

class NotificationResponse(NotificationBase):
    id: int
    user_id: int
    is_read: bool

    class Config:
        from_attributes = True

# Penalty Status Schemas
class PenaltyStatusUpdate(BaseModel):
    plan_id: int
    user_id: int
    penalty_status: Literal['none', 'pending', 'completed', 'exempted']

class PenaltyStatusResponse(BaseModel):
    plan_id: int
    user_id: int
    penalty_status: str
    penalty_completed_at: Optional[datetime] = None
    updated_at: datetime

    class Config:
        from_attributes = True

# Penalty Approval Request Schemas
class PenaltyApprovalRequestCreate(BaseModel):
    comment: Optional[str] = None
    proof_image_data: Optional[bytes] = None

class PenaltyApprovalRequestResponse(BaseModel):
    id: int
    plan_id: int
    penalty_user_id: int
    comment: Optional[str] = None
    proof_image_url: Optional[str] = None
    status: str
    approver_user_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class PenaltyApprovalStatus(BaseModel):
    plan_id: int
    penalty_user_id: int
    has_approval: bool
    approver_user_id: Optional[int] = None
    approved_at: Optional[datetime] = None

class PushTokenUpdate(BaseModel):
    push_token: str 
    
    class Config:
        from_attributes = True

class UserTrustStatsResponse(BaseModel):
    id: Optional[int] = None
    userId: Optional[int] = None
    total_plans: int
    late_plans: int
    on_time_streak: int
    best_on_time_streak: int
    last_arrival_status: Optional[str]
    trust_level: float

    class Config:
        from_attributes = True
        
class ProfileImageResponse(BaseModel):
    message: str
    url: str
    
    class Config:
        from_attributes = True
        
class PlanListRequest(BaseModel):
    skip: int = 0
    limit: int = 20
    plan_status: List[str] = ["upcoming", "ongoing", "completed", "cancelled"]

# WebSocket Schemas
class LocationShareMessage(BaseModel):
    user_id: int
    display_name: str
    profile_image_url: Optional[str] = None
    latitude: float
    longitude: float

class WebSocketErrorResponse(BaseModel):
    error: str
    code: Optional[str] = None

class LocationUpdateRequest(BaseModel):
    latitude: float
    longitude: float
    name: Optional[str] = None
