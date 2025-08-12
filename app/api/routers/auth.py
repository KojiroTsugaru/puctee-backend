from datetime import datetime, timedelta
from typing import Optional, Set
from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError, jwt

from app.core.config import settings
from app.db.session import get_db
from app.models import User as UserModel, UserTrustStats
from app.schemas import Token, UserCreate, User as UserSchema, RefreshToken
import re
from app.core.auth import create_refresh_token, create_access_token, verify_password, get_password_hash, get_current_username

# TODO: Simple in-memory blacklist. Replace with Redis or DB in prod.
BLACKLISTED_REFRESH_TOKENS: Set[str] = set()

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login/username")

BLACKLIST_KEY = "blacklisted_refresh_tokens"

@router.post("/signup", response_model=Token)
async def signup(
    user: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    # Check if user already exists
    result = await db.execute(
        select(UserModel).where(
            (UserModel.email == user.email) | (UserModel.username == user.username)
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username already registered"
        )

    # Create new user
    hashed_password = get_password_hash(user.password)
    db_user = UserModel(
        email=user.email,
        display_name=user.display_name,
        username=user.username,
        hashed_password=hashed_password
    )
    
    db.add(db_user)
    await db.flush()  # Flush to get ID

    # Create UserTrustStats for the new user
    trust_stats = UserTrustStats(user_id=db_user.id)
    db.add(trust_stats)
    
    await db.commit()
    await db.refresh(db_user)

    # Create tokens
    access_token = create_access_token(data={"sub": user.username})
    refresh_token = create_refresh_token(data={"sub": user.username})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": refresh_token
    }

@router.post("/login/username", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    # Get user
    result = await db.execute(
        select(UserModel).where(UserModel.username == form_data.username)
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create tokens
    access_token = create_access_token(data={"sub": user.username})
    refresh_token = create_refresh_token(data={"sub": user.username})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": refresh_token
    }
    
@router.post("/login/email", response_model=Token)
async def login(
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    # Get user
    result = await db.execute(
        select(UserModel).where(UserModel.email == email)
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create tokens
    access_token = create_access_token(data={"sub": user.username})
    refresh_token = create_refresh_token(data={"sub": user.username})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": refresh_token
    }

@router.post("/refresh", response_model=Token)
async def refresh_token(
    token_data: RefreshToken,
    db: AsyncSession = Depends(get_db)
):
    old_rt = token_data.refresh_token

    # 1) Reject if already revoked    
    if old_rt in BLACKLISTED_REFRESH_TOKENS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked")

    # 2) Decode and validate
    try:
        payload = jwt.decode(
            old_rt,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        username: str = payload.get("sub")
        if username is None:
            raise JWTError()
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    # 3) Make sure user still exists
    result = await db.execute(select(UserModel).where(UserModel.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    # 4) Revoke the old refresh token
    BLACKLISTED_REFRESH_TOKENS.add(old_rt)

    # 5) Issue new tokens
    new_access = create_access_token(data={"sub": username})
    new_refresh = create_refresh_token(data={"sub": username})

    return {
        "access_token": new_access,
        "token_type": "bearer",
        "refresh_token": new_refresh,
    }

@router.post("/logout")
async def logout(
    token_payload: RefreshToken,
    current_user: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db)
):
    """
    Blacklist the provided refresh token so it can no longer be used.
    """
    refresh_token = token_payload.refresh_token

    # verify the token is valid before blacklisting
    try:
        payload = jwt.decode(
            refresh_token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        if payload.get("sub") != current_user:
            raise JWTError()
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid refresh token")

    # Add to Redis set
    BLACKLISTED_REFRESH_TOKENS.add(refresh_token)

    return {"message": "Successfully logged out"}

@router.get("/validate-username/{username}")
async def validate_username(
    username: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Validate if username is available
    """
    result = await db.execute(
        select(UserModel).where(UserModel.username == username)
    )
    existing_user = result.scalar_one_or_none()
    
    return {
        "available": existing_user is None,
        "message": "Username is available" if existing_user is None else "Username is already taken"
    }
    
@router.get("/validate-email/{email}")
async def validate_email(
    email: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Validate if email address is available
    """
    # Validate email address format
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format"
        )
    
    # Check for email address duplication (case-insensitive)
    result = await db.execute(
        select(UserModel).where(UserModel.email.ilike(email))
    )
    existing_user = result.scalar_one_or_none()
    
    return {
        "available": existing_user is None,
        "message": "Email is available" if existing_user is None else "Email is already registered"
    }