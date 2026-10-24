"""
Authentication schemas.

Defines schemas for:
- OTP generation request and response (strictly without returning the OTP)
- OTP verification request and response
- Session user representation (AuthUser)
- Logout and SMTP status responses
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class SendOtpRequest(BaseModel):
    """Request to generate and email an OTP to the given address."""
    email: str = Field(..., description="User's email address from any domain")


class SendOtpResponse(BaseModel):
    """
    Response confirming OTP generation and dispatch.
    CRITICAL: The OTP code is NEVER returned in the response payload.
    """
    status: str = "success"
    message: str = "A 6-digit verification code has been sent to your email."
    cooldown_seconds: int = 60


class VerifyOtpRequest(BaseModel):
    """Request to verify an OTP code."""
    email: str = Field(..., description="User's email address")
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")


class UserProfile(BaseModel):
    id: str
    email: str


class VerifyOtpResponse(BaseModel):
    """Response containing authenticated session JWT and user profile."""
    status: str = "success"
    message: str = "Verification successful. Authenticated session created."
    token: str
    user: UserProfile


class LogoutResponse(BaseModel):
    """Response confirming session revocation."""
    status: str = "success"
    message: str = "Session invalidated. Logged out successfully."


class SmtpStatusResponse(BaseModel):
    """Status indicating whether SMTP email delivery is configured."""
    configured: bool
    host: Optional[str] = None
    port: Optional[int] = None
    from_email: Optional[str] = None


class AuthUser(BaseModel):
    """
    Canonical representation of an authenticated user.
    Provides both user_id and id attributes for backward compatibility across all routes.
    """
    user_id: str
    email: str
    email_confirmed: bool = True

    @property
    def id(self) -> str:
        return self.user_id

    model_config = {"from_attributes": True}
