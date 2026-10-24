"""
Authentication routes for Email OTP login, verification, and session lifecycle.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.config import settings
from app.dependencies.auth import get_current_user, extract_token_from_request
from app.schemas.auth import (
    AuthUser,
    LogoutResponse,
    SendOtpRequest,
    SendOtpResponse,
    SmtpStatusResponse,
    UserProfile,
    VerifyOtpRequest,
    VerifyOtpResponse,
)
from app.services.email_service import EmailDeliveryError, email_service
from app.services.otp_service import (
    OtpExpiredError,
    OtpInvalidError,
    OtpNotFoundError,
    OtpRateLimitError,
    otp_service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ------------------------------------------------------------------
# POST /auth/send-otp
# ------------------------------------------------------------------
@router.post(
    "/send-otp",
    response_model=SendOtpResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate and email a 6-digit OTP code",
)
async def send_otp(request: Request, body: SendOtpRequest):
    """
    Accepts any valid email address regardless of domain (Gmail, Outlook, company emails).
    Enforces resend cooldown and request rate limiting.
    Dispatches OTP via configured SMTP email service.
    
    SECURITY: The OTP code is NEVER returned in the API response.
    """
    email = body.email.strip().lower()

    if not otp_service.is_valid_email(email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Please enter a valid email address.",
        )

    try:
        # Generate OTP & apply rate limits + invalidation of prior OTP
        otp = otp_service.request_otp(email)

        # Dispatch via SMTP service
        email_service.send_otp_email(to_email=email, otp=otp)

        return SendOtpResponse(
            status="success",
            message=f"A 6-digit verification code has been sent to {email}. Code expires in 5 minutes.",
            cooldown_seconds=settings.OTP_RESEND_COOLDOWN_SECONDS,
        )

    except OtpRateLimitError as rate_err:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(rate_err),
            headers={"Retry-After": str(rate_err.retry_after_seconds or 60)},
        )
    except EmailDeliveryError as email_err:
        logger.error("Failed to deliver OTP to %s: %s", email, email_err)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(email_err),
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        logger.error("Unexpected error in send_otp: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process OTP request. Please try again later.",
        )


# ------------------------------------------------------------------
# POST /auth/verify-otp
# ------------------------------------------------------------------
@router.post(
    "/verify-otp",
    response_model=VerifyOtpResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify OTP and issue authenticated session token",
)
async def verify_otp(body: VerifyOtpRequest):
    """
    Verifies 6-digit OTP code against backend store.
    If valid:
      - Immediately invalidates OTP to prevent reuse.
      - Issues cryptographically signed session JWT.
      - Returns token and user profile.
    If invalid:
      - Tracks attempt count.
      - If max attempts reached, invalidates OTP.
    """
    email = body.email.strip().lower()
    otp = body.otp.strip()

    try:
        session_token = otp_service.verify_otp(email=email, input_otp=otp)

        return VerifyOtpResponse(
            status="success",
            message="Verification successful. Access granted.",
            token=session_token,
            user=UserProfile(id=email, email=email),
        )

    except OtpNotFoundError as not_found:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(not_found),
        )
    except OtpExpiredError as expired_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(expired_err),
        )
    except OtpRateLimitError as rate_err:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(rate_err),
        )
    except OtpInvalidError as invalid_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(invalid_err),
        )
    except Exception as exc:
        logger.error("Unexpected error in verify_otp: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Verification processing error. Please try again.",
        )


# ------------------------------------------------------------------
# POST /auth/logout
# ------------------------------------------------------------------
@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke active session token and log out",
)
async def logout(
    request: Request,
    user: AuthUser = Depends(get_current_user),
):
    """
    Invalidates current session JWT, preventing any further API calls with this token.
    """
    token = getattr(request.state, "current_token", None) or extract_token_from_request(request)
    if token:
        otp_service.revoke_session(token)

    return LogoutResponse(
        status="success",
        message="Session revoked successfully. Logged out.",
    )


# ------------------------------------------------------------------
# GET /auth/me
# ------------------------------------------------------------------
@router.get(
    "/me",
    summary="Get current authenticated user profile",
)
async def get_me(user: AuthUser = Depends(get_current_user)):
    """
    Returns profile information for the authenticated user session.
    Requires Bearer token in Authorization header.
    """
    return {
        "id": user.user_id,
        "email": user.email,
        "email_confirmed": user.email_confirmed,
    }


# ------------------------------------------------------------------
# GET /auth/smtp-status
# ------------------------------------------------------------------
@router.get(
    "/smtp-status",
    response_model=SmtpStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Check if SMTP email delivery is configured",
)
async def get_smtp_status():
    """
    Public diagnostic check for SMTP configuration.
    Does NOT reveal SMTP passwords.
    """
    return SmtpStatusResponse(
        configured=email_service.is_configured,
        host=settings.SMTP_HOST if settings.SMTP_HOST else None,
        port=settings.SMTP_PORT if settings.SMTP_HOST else None,
        from_email=settings.SMTP_FROM_EMAIL or settings.SMTP_USER if settings.SMTP_HOST else None,
    )
