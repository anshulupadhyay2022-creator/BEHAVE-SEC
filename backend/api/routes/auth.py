"""
backend/api/routes/auth.py
Signup, Login, OTP Verification, and Behavioral Challenge endpoints.

Login flow (email users):
  1. POST /auth/login        — validates password, sends OTP, returns otp_required
  2. POST /auth/verify-login-otp — validates OTP, returns challenge_required or success
  3. POST /auth/verify-challenge — behavioral CAPTCHA scoring, returns JWT
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
from backend.models.schemas import UserCreate, UserLogin, OTPVerify, Token, ChallengeVerify, LoginChallengeResponse
from backend.core.security import get_password_hash, verify_password, create_access_token, SECRET_KEY, ALGORITHM
from backend.ml.model import model_manager
from backend.utils.email import send_otp, generate_otp

router = APIRouter()

async def get_db() -> AsyncSession:  # type: ignore[return]
    async with AsyncSessionLocal() as session:
        yield session

def generate_and_send_otp(user_email: str, purpose: str = "MFA") -> str:
    """
    Generate a 6-digit OTP, send it via SMTP (or console in dev mode).
    Raises RuntimeError if SMTP delivery fails — callers must map this to
    a generic 'Email is invalid' response to prevent account enumeration.
    """
    otp = generate_otp()
    send_otp(user_email, otp, purpose=purpose)   # raises RuntimeError on failure
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
    new_user = await create_user(db, user_data.full_name, user_data.email, hashed_password)
    
    access_token = create_access_token(data={"sub": new_user.email, "user_id": new_user.id})
    return {
        "status": "success", 
        "access_token": access_token, 
        "token_type": "bearer", 
        "user": {
            "id": new_user.id, 
            "email": new_user.email, 
            "full_name": new_user.full_name
        }
    }

@router.post("/login", response_model=Dict[str, Any])
async def login(user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    """
    Step 1 of the login flow.
    Validates email + password, then sends an OTP to the registered email.
    ALWAYS returns 'Email is invalid' on any failure (wrong email, wrong
    password, SMTP error) to prevent account-enumeration attacks.
    """
    # Generic error used for ALL failure cases — no information leakage
    INVALID = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Email is invalid or OTP could not be delivered. Please check your email address.",
    )

    # 1. Look up user
    user = await get_user_by_email(db, user_data.email)
    if not user or not verify_password(user_data.password, user.password_hash):
        raise INVALID

    # 2. Account locked?
    if user.locked_out:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is locked due to anomaly. MFA required."
        )

    # 3. Generate OTP and send via SMTP
    try:
        otp_code = generate_and_send_otp(user.email, purpose="Login")
    except RuntimeError:
        # SMTP failed — hide reason, treat as invalid email
        raise INVALID

    # 4. Persist OTP on user record (10-minute window)
    user.otp_code = otp_code
    user.otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    await update_user(db, user)

    return {
        "status": "otp_required",
        "message": "OTP sent to your registered email. Please verify to continue.",
        "email": user.email,
    }


class LoginOtpVerify(UserLogin):
    """Login OTP verification payload (email + password + otp)."""
    otp_code: str


@router.post("/verify-login-otp", response_model=Dict[str, Any])
async def verify_login_otp(data: LoginOtpVerify, db: AsyncSession = Depends(get_db)):
    """
    Step 2 of the login flow.
    Validates the OTP the user received by email.
    On success returns challenge_required (if model trained) or a JWT.
    """
    INVALID = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Email is invalid or OTP could not be delivered. Please check your email address.",
    )

    user = await get_user_by_email(db, data.email)
    if not user or not verify_password(data.password, user.password_hash):
        raise INVALID

    # Check OTP
    if not user.otp_code or user.otp_code != data.otp_code:
        raise HTTPException(status_code=401, detail="Invalid or expired OTP code.")

    # Check expiry (naive UTC comparison for SQLite compatibility)
    import datetime as _dt
    now     = _dt.datetime.now(timezone.utc).replace(tzinfo=None)
    expires = user.otp_expires_at.replace(tzinfo=None) if user.otp_expires_at else now
    if expires < now:
        raise HTTPException(status_code=401, detail="OTP has expired. Please log in again.")

    # Clear OTP
    user.otp_code = None
    user.otp_expires_at = None
    await update_user(db, user)

    # Step 3: behavioral CAPTCHA or direct login
    detector = model_manager.get_detector(user.id)
    if detector.status["trained"]:
        return {
            "status": "challenge_required",
            "message": "Behavioral biometric verification required.",
            "email": user.email,
        }

    # Cold start — no model yet, issue JWT immediately
    access_token = create_access_token(data={"sub": user.email, "user_id": user.id})
    return {
        "status": "success",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "full_name": user.full_name},
    }

@router.post("/verify-challenge", response_model=Dict[str, Any])
async def verify_challenge(data: ChallengeVerify, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_email(db, data.email)
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Verification failed: invalid credentials.")
    
    detector = model_manager.get_detector(user.id)
    result = detector.verify_login_signature(data.keyboard_events, data.mouse_events)

    from backend.core.config import settings as _cfg
    from backend.db.repository import update_user_captcha_score
    
    # ── 1. BOT PROTECTION (Global Model) ────────────────────────────────────
    bot_res = result.get("bot_detection")
    if bot_res and bot_res["label"] == "bot":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Security Alert: Non-human (bot) behavior detected. Access Denied."
        )

    # ── 2. IDENTITY VERIFICATION (Personal Model) ────────────────────────────
    if result.get("model_ready"):
        id_score         = result.get("identity_score", 0.0)
        sim              = result.get("similarity", 0.0)
        # Use the model's OWN per-user adaptive threshold (calibrated from owner's p90 scores)
        # rather than a hard-coded value that may be too permissive.
        adaptive_threshold = result.get("threshold", 0.55)

        identity_failed = (
            result.get("identity_label") == "anomaly"
            or id_score > adaptive_threshold    # exceeds user-specific threshold
            or sim < _cfg.DRIFT_SIMILARITY_THRESHOLD  # cosine similarity vs master centroid
        )
        if identity_failed:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    f"Identity verification failed. "
                    f"Score {id_score:.3f} vs threshold {adaptive_threshold:.3f}, "
                    f"Similarity {sim:.3f} < {_cfg.DRIFT_SIMILARITY_THRESHOLD:.2f}. "
                    "Behavioral signature does not match account owner."
                )
            )


    # ── 3. SESSION SCORE DRIFT GUARD ────────────────────────────────────────
    # identity_score: 0.0 = very normal, 1.0 = very anomalous
    # We use this as the "captcha score" for the drift comparison.
    new_captcha_score = float(result.get("identity_score", 0.0))
    stored_score = user.last_captcha_score
    drift = 0.0
    score_match = True

    from datetime import timezone as _tz, timedelta as _td

    if stored_score is None:
        # COLD START: no previous score — store and grant access
        new_avg = await update_user_captcha_score(db, user, new_captcha_score)
        score_verdict = "cold_start"
        otp_triggered = False
    else:
        drift = abs(new_captcha_score - stored_score)
        if drift > _cfg.SCORE_DRIFT_THRESHOLD:
            # SCORE MISMATCH — lock + send OTP
            otp_code = generate_and_send_otp(user.email)
            user.otp_code = otp_code
            user.otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
            user.locked_out = True
            await update_user(db, user)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "otp_required",
                    "reason": "score_drift",
                    "message": (
                        f"Behavioral score drift detected (Δ{drift:.2f} > threshold {_cfg.SCORE_DRIFT_THRESHOLD}). "
                        f"OTP sent to your registered email to reinforce the score."
                    ),
                    "drift": round(drift, 4),
                    "new_score": round(new_captcha_score, 4),
                    "stored_score": round(stored_score, 4),
                    "email": user.email,
                }
            )
        else:
            # SCORE MATCH — update rolling avg and proceed
            new_avg = await update_user_captcha_score(db, user, new_captcha_score)
            score_verdict = "matched"
            otp_triggered = False
            score_match = True

    # ── 4. Issue JWT ─────────────────────────────────────────────────────────
    access_token = create_access_token(data={"sub": user.email, "user_id": user.id})
    return {
        "status": "success",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "full_name": user.full_name},
        "verification": result,
        # Score breakdown for frontend display
        "captcha_score": round(new_captcha_score, 4),
        "stored_score": round(stored_score, 4) if stored_score is not None else None,
        "new_baseline": round(new_avg, 4),
        "drift": round(drift, 4),
        "score_match": score_match,
        "score_verdict": score_verdict,
    }


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

    # Reset captcha baseline to neutral (0.3) so the next login drift check
    # starts from a clean, low-anomaly reference rather than the anomalous
    # score that triggered the lockout.
    from backend.db.repository import update_user_captcha_score
    await update_user_captcha_score(db, user, 0.3)

    access_token = create_access_token(data={"sub": user.email, "user_id": user.id})
    return {
        "status": "success",
        "message": "MFA verified. Account unlocked. Anomaly baseline reset.",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "full_name": user.full_name}
    }

