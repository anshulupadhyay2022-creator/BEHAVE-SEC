"""
backend/api/routes/auth.py
Signup, Login, and OTP Verification endpoints.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
import random

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
import jwt

from backend.db.engine import AsyncSessionLocal
from backend.db.repository import get_user_by_email, create_user, update_user
from backend.models.schemas import UserCreate, UserLogin, OTPVerify, Token
from backend.core.security import get_password_hash, verify_password, create_access_token, SECRET_KEY, ALGORITHM

router = APIRouter()

async def get_db() -> AsyncSession:  # type: ignore[return]
    async with AsyncSessionLocal() as session:
        yield session

def generate_and_send_otp(user_email: str) -> str:
    """Mock sending an OTP."""
    otp = str(random.randint(100000, 999999))
    print(f"\n=========================================")
    print(f"🔒 [MFA] Sending OTP Code: {otp} to {user_email}")
    print(f"=========================================\n")
    return otp

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str | None = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = await get_user_by_email(db, email)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.locked_out:
        raise HTTPException(status_code=403, detail="Account locked. MFA required.")
    return user

@router.post("/signup", response_model=Dict[str, Any])
async def signup(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    existing_user = await get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = get_password_hash(user_data.password)
    user = await create_user(db, user_data.full_name, user_data.email, hashed_password)
    
    # Auto-login upon signup
    access_token = create_access_token(data={"sub": user.email, "user_id": user.id})
    return {"status": "success", "access_token": access_token, "token_type": "bearer", "user": {"id": user.id, "email": user.email, "full_name": user.full_name}}

@router.post("/login", response_model=Dict[str, Any])
async def login(user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_email(db, user_data.email)
    if not user or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    if user.locked_out:
        raise HTTPException(status_code=403, detail="Account is locked due to anomaly. MFA required.")
        
    access_token = create_access_token(data={"sub": user.email, "user_id": user.id})
    return {"status": "success", "access_token": access_token, "token_type": "bearer", "user": {"id": user.id, "email": user.email, "full_name": user.full_name}}

@router.post("/verify-otp", response_model=Dict[str, Any])
async def verify_otp(otp_data: OTPVerify, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_email(db, otp_data.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if not user.otp_code or user.otp_code != otp_data.otp_code:
        raise HTTPException(status_code=401, detail="Invalid OTP code")
        
    # Compare naive dt to naive dt if sqlite returns naive
    # Since sqlite doesn't store timezone info robustly, we'll assume naive UTC comparing to nautc datetime.now().
    # Or better yet, we can skip strict timezone compares for simple implementation
    import datetime as dt
    now = dt.datetime.now(timezone.utc).replace(tzinfo=None) # type: ignore
    expires = user.otp_expires_at.replace(tzinfo=None) if user.otp_expires_at else now # type: ignore
    if user.otp_expires_at and expires < now: # type: ignore
        raise HTTPException(status_code=401, detail="OTP has expired")
        
    # Unlock account & clear OTP
    user.locked_out = False
    user.otp_code = None
    user.otp_expires_at = None
    await update_user(db, user)
    
    access_token = create_access_token(data={"sub": user.email, "user_id": user.id})
    return {"status": "success", "message": "MFA verified. Account unlocked.", "access_token": access_token, "token_type": "bearer", "user": {"id": user.id, "email": user.email, "full_name": user.full_name}}
