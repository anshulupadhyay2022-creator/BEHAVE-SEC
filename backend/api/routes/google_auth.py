"""
backend/api/routes/google_auth.py
POST /auth/google — verify Google ID token and issue a BEHAVE-SEC JWT.

Flow:
  1. Frontend sends the credential (ID token) from Google Identity Services.
  2. We verify it with Google's public keys (no extra round-trip to Google UI).
  3. We upsert the user in the DB (create on first sign-in, find on subsequent).
  4. If the user's behavioral model is trained → return challenge_required so
     the frontend runs the same keyboard+mouse CAPTCHA used by password login.
  5. Otherwise → issue JWT and let them into the dashboard (cold start).
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.engine import AsyncSessionLocal
from backend.db import repository
from backend.core.security import get_password_hash, create_access_token
from backend.ml.model import model_manager

router = APIRouter()

# ── Google Client ID ──────────────────────────────────────────────────────────
# Reads from environment first so it can be overridden in production without
# a code change.  Falls back to the compile-time constant.
GOOGLE_CLIENT_ID: str = os.environ.get(
    "GOOGLE_CLIENT_ID",
    "712400673827-4d3u6bi41fs47nqs4urjntv6ib3712hu.apps.googleusercontent.com",
)


# ── DB dependency ─────────────────────────────────────────────────────────────
async def get_db() -> AsyncSession:  # type: ignore[return]
    async with AsyncSessionLocal() as session:
        yield session


# ── Request schema ────────────────────────────────────────────────────────────
class GoogleAuthPayload(BaseModel):
    credential: str   # the ID token returned by Google Identity Services


# ── Helper: verify Google ID token ───────────────────────────────────────────
def _verify_google_token(credential: str) -> Dict[str, Any]:
    """
    Verify the Google ID token and return the decoded claims.
    Raises HTTPException 401 on any failure.
    """
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as g_requests
        request = g_requests.Request()
        id_info = id_token.verify_oauth2_token(credential, request, GOOGLE_CLIENT_ID)
        return id_info
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google token: {exc}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Google token verification failed: {exc}",
        )


# ── Route ─────────────────────────────────────────────────────────────────────
@router.post("/google", response_model=Dict[str, Any])
async def google_auth(
    payload: GoogleAuthPayload,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Authenticate via Google OAuth.
    - Verifies the Google ID token received from the frontend.
    - Creates the user account on first sign-in (upsert by email).
    - Returns challenge_required if the behavioral model is trained,
      otherwise issues a JWT directly (cold-start path).
    """
    # 1. Verify token with Google
    id_info = _verify_google_token(payload.credential)

    email: str     = id_info.get("email", "")
    full_name: str = id_info.get("name", email.split("@")[0])
    google_sub: str = id_info.get("sub", "")   # unique Google user ID
    picture: str   = id_info.get("picture", "")

    if not email:
        raise HTTPException(status_code=400, detail="Google token missing email claim.")

    # 2. Upsert user in DB
    user = await repository.get_user_by_email(db, email)
    is_new_user = False

    if user is None:
        # First-ever Google sign-in → create account.
        # Password is a random secret (Google users never log in with password).
        random_pw = secrets.token_urlsafe(32)
        hashed_pw = get_password_hash(random_pw)
        user = await repository.create_user(db, full_name, email, hashed_pw)
        is_new_user = True
        print(f"[GOOGLE AUTH] New user created: {email} (Google UID: {google_sub})")
    else:
        print(f"[GOOGLE AUTH] Existing user sign-in: {email}")

    # 3. Account locked?
    if user.locked_out:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account locked. MFA required.",
        )

    # 4. Behavioral model trained? → require CAPTCHA challenge
    detector = model_manager.get_detector(user.id)
    if detector.status["trained"] and not is_new_user:
        return {
            "status": "challenge_required",
            "message": "Behavioral biometric verification required.",
            "email": email,
        }

    # 5. Cold start or brand-new user → issue JWT immediately
    access_token = create_access_token(data={"sub": user.email, "user_id": user.id})
    return {
        "status": "success",
        "access_token": access_token,
        "token_type": "bearer",
        "is_new_user": is_new_user,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "picture": picture,
        },
    }
