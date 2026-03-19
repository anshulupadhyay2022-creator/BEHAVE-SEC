"""
backend/models/schemas.py
Pydantic data-validation models for the BEHAVE-SEC API.
Extracted verbatim from the original backend_api.py.
"""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class BehavioralEvent(BaseModel):
    """Model for a single behavioral event."""

    eventType: str = Field(..., description="Type of event: keydown, keyup, mousemove, click, or scroll")
    timestamp: int = Field(..., description="Unix timestamp in milliseconds")
    relativeTime: int = Field(..., description="Time since session start in milliseconds")

    # Keyboard fields
    key: Optional[str] = Field(None, description="Key pressed")
    keyCode: Optional[int] = Field(None, description="Key code")

    # Mouse fields
    clientX: Optional[int] = Field(None, description="Mouse X relative to viewport")
    clientY: Optional[int] = Field(None, description="Mouse Y relative to viewport")
    pageX: Optional[int] = Field(None, description="Mouse X relative to page")
    pageY: Optional[int] = Field(None, description="Mouse Y relative to page")

    # Target element
    target: Optional[str] = Field(None, description="HTML target element")
    targetId: Optional[str] = Field(None, description="ID of target element")
    targetName: Optional[str] = Field(None, description="Name of target element")

    # Scroll fields
    scrollX: Optional[int] = Field(None, description="Scroll X position")
    scrollY: Optional[int] = Field(None, description="Scroll Y position")

    @field_validator("eventType")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        allowed_types = {"keydown", "keyup", "mousemove", "click", "scroll"}
        if v not in allowed_types:
            raise ValueError(f"Event type must be one of: {', '.join(allowed_types)}")
        return v


class SessionMetadata(BaseModel):
    """Metadata about the user's session."""

    userAgent: str = Field(..., description="Browser user agent string")
    screenWidth: int = Field(..., description="Screen width in pixels")
    screenHeight: int = Field(..., description="Screen height in pixels")
    sessionDuration: int = Field(..., description="Total session duration in milliseconds")


class BehavioralDataPayload(BaseModel):
    """Complete payload sent from the frontend."""

    userId: str = Field(..., description="Unique identifier for the user")
    sessionId: str = Field(..., description="Unique identifier for this session")
    events: List[BehavioralEvent] = Field(..., description="List of behavioral events")
    metadata: SessionMetadata = Field(..., description="Session metadata")

    @field_validator("events")
    @classmethod
    def validate_events_not_empty(cls, v: List[BehavioralEvent]) -> List[BehavioralEvent]:
        if not v:
            raise ValueError("Events list cannot be empty")
        return v

# --- Auth Schemas ---

class UserCreate(BaseModel):
    full_name: str
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class OTPVerify(BaseModel):
    email: str
    otp_code: str

class Token(BaseModel):
    access_token: str
    token_type: str

