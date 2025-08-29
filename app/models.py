from sqlalchemy import Boolean, Column, Integer, String, DateTime, ForeignKey, Float, Table, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

# Association tables
user_friends = Table(
    'user_friends',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('friend_id', Integer, ForeignKey('users.id'), primary_key=True)
)

plan_participants = Table(
    'plan_participants',
    Base.metadata,
    Column('plan_id', Integer, ForeignKey('plans.id'), primary_key=True),
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('arrival_status', String, nullable=True),  # on_time, late, not_arrived
    Column('checked_at', DateTime(timezone=True), nullable=True),  # Time when arrival was confirmed
    Column('penalty_status', String, default='none'),  # none, required, pendingApproval, completed, exempted
    Column('penalty_completed_at', DateTime(timezone=True), nullable=True)  # When penalty was completed
)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    display_name = Column(String, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    push_token = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    profile_image_url = Column(String, nullable=True)

    # Relationships
    friends = relationship(
        "User",
        secondary=user_friends,
        primaryjoin=id == user_friends.c.user_id,
        secondaryjoin=id == user_friends.c.friend_id,
        backref="friend_of"
    )
    sent_invites = relationship("FriendInvite", back_populates="sender", foreign_keys="FriendInvite.sender_id")
    received_invites = relationship("FriendInvite", back_populates="receiver", foreign_keys="FriendInvite.receiver_id")
    plans = relationship("Plan", secondary=plan_participants, back_populates="participants")
    notifications = relationship("Notification", back_populates="user")
    locations = relationship("Location", back_populates="user")
    penalties = relationship("Penalty", back_populates="user")
    plan_invites = relationship("PlanInvite", back_populates="user")
    trust_stats = relationship("UserTrustStats", back_populates="user")

class UserTrustStats(Base):
    __tablename__ = "user_trust_stats"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    total_plans = Column(Integer, default=0)  # Total number of plans participated in
    late_plans = Column(Integer, default=0)   # Number of plans where user was late
    on_time_streak = Column(Integer, default=0)  # Current consecutive on-time arrivals
    best_on_time_streak = Column(Integer, default=0)  # Best consecutive on-time arrivals record
    last_arrival_status = Column(String, nullable=True)  # Last arrival status
    trust_level = Column(Float, default=60.0)  # Trust level (0-100%)

    # Fix relationship definition
    user = relationship("User", back_populates="trust_stats", uselist=False)

class FriendInvite(Base):
    __tablename__ = "friend_invites"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"))
    receiver_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String, default="pending")  # pending, accepted, declined
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    sender = relationship("User", back_populates="sent_invites", foreign_keys=[sender_id])
    receiver = relationship("User", back_populates="received_invites", foreign_keys=[receiver_id])

class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    start_time = Column(DateTime(timezone=True))
    status = Column(String, default="upcoming")  # upcoming, ongoing, completed, cancelled
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    participants = relationship("User", secondary=plan_participants, back_populates="plans")
    invites = relationship("PlanInvite", back_populates="plan")
    locations = relationship("Location", back_populates="plan")
    penalties = relationship("Penalty", back_populates="plan")

class PlanInvite(Base):
    __tablename__ = "plan_invites"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, default="pending")  # pending, accepted, rejected

    plan = relationship("Plan", back_populates="invites")
    user = relationship("User", back_populates="plan_invites")
    
class Penalty(Base):
    __tablename__ = "penalties"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("plans.id"))
    user_id = Column(Integer, ForeignKey("users.id"))   
    content=Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    plan = relationship("Plan", back_populates="penalties")
    user = relationship("User", back_populates="penalties")
    approval_requests = relationship("PenaltyApprovalRequest", back_populates="penalty")

class PenaltyApprovalRequest(Base):
    __tablename__ = "penalty_approval_requests"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey('plans.id'), nullable=False)
    penalty_id = Column(Integer, ForeignKey('penalties.id'), nullable=True)  # Optional link to specific penalty
    penalty_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)  # User requesting approval
    comment = Column(Text, nullable=True)  # Optional comment from user
    proof_image_url = Column(String, nullable=True)  # Optional proof image URL
    status = Column(String, default='pending')  # pending, approved, declined
    approver_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # User who approved/declined
    approved_at = Column(DateTime(timezone=True), nullable=True)  # When approved/declined
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    plan = relationship("Plan")
    penalty = relationship("Penalty", back_populates="approval_requests")
    penalty_user = relationship("User", foreign_keys=[penalty_user_id])
    approver_user = relationship("User", foreign_keys=[approver_user_id])

class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("plans.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String, nullable=True)
    latitude = Column(Float)
    longitude = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    plan = relationship("Plan", back_populates="locations")
    user = relationship("User", back_populates="locations")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String)
    content = Column(String)
    type = Column(String)  # friend_invite, plan_invite, penalty, etc.
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="notifications")
