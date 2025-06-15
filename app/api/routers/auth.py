from datetime import datetime, timedelta
from typing import Optional, Set
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError, jwt

from app.core.config import settings
from app.db.session import get_db
from app.models import User, UserTrustStats
from app.schemas import Token, UserCreate, User as UserSchema, RefreshToken
from app.core.s3 import upload_to_s3
import re

# TODO: Simple in-memory blacklist. Replace with Redis or DB in prod.
BLACKLISTED_REFRESH_TOKENS: Set[str] = set()

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

BLACKLIST_KEY = "blacklisted_refresh_tokens"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=30)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> str:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return username

@router.post("/signup", response_model=Token)
async def signup(
    user: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    # Check if user already exists
    result = await db.execute(
        select(User).where(
            (User.email == user.email) | (User.username == user.username)
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username already registered"
        )

    # Create new user
    hashed_password = get_password_hash(user.password)
    db_user = User(
        email=user.email,
        display_name=user.display_name,
        username=user.username,
        hashed_password=hashed_password
    )
    
    db.add(db_user)
    await db.flush()  # IDを取得するためにflush

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
        select(User).where(User.username == form_data.username)
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
        select(User).where(User.email == email)
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
    result = await db.execute(select(User).where(User.username == username))
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
    current_user: str = Depends(get_current_user),
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

    # Redis セットに追加
    BLACKLISTED_REFRESH_TOKENS.add(refresh_token)

    return {"message": "Successfully logged out"}

@router.get("/validate-username/{username}")
async def validate_username(
    username: str,
    db: AsyncSession = Depends(get_db)
):
    """
    ユーザー名が利用可能かどうかを検証する
    """
    result = await db.execute(
        select(User).where(User.username == username)
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
    メールアドレスが利用可能かどうかを検証する
    """
    # メールアドレスの形式を検証
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format"
        )
    
    # メールアドレスの重複をチェック（大文字小文字を区別しない）
    result = await db.execute(
        select(User).where(User.email.ilike(email))
    )
    existing_user = result.scalar_one_or_none()
    
    return {
        "available": existing_user is None,
        "message": "Email is available" if existing_user is None else "Email is already registered"
    }