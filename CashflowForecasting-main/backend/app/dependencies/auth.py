"""
Authentication dependency for protecting private endpoints.

Validates the signed JWT session token created upon successful OTP verification.
Guarantees that:
1. Missing, expired, invalid, or revoked tokens result in HTTP 401 Unauthorized.
2. Returns a canonical `AuthUser` object representing the verified caller.
"""

from __future__ import annotations

import logging
from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.schemas.auth import AuthUser
from app.services.otp_service import otp_service, SessionAuthError

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(
    scheme_name="Session Bearer Token",
    description="Pass the session JWT token in the Authorization header: Bearer <token>",
    auto_error=False,
)


def extract_token_from_request(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = None,
) -> Optional[str]:
    """Extract bearer token from credentials or Authorization header."""
    if credentials and credentials.credentials:
        return credentials.credentials.strip()

    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1].strip()

    return None


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> AuthUser:
    """
    Validate session JWT token and return verified AuthUser.
    Raises HTTP 401 Unauthorized if token is missing, invalid, expired, or revoked.
    """
    token = extract_token_from_request(request, credentials)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in with email OTP.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = otp_service.validate_session_token(token)
        email = payload.get("email") or payload.get("sub", "")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session token payload.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Store verified token on request state for logout handler
        request.state.current_token = token
        request.state.current_user_email = email

        return AuthUser(
            user_id=email,
            email=email,
            email_confirmed=True,
        )

    except SessionAuthError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(err),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as exc:
        logger.error("Authentication validation error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session validation failed. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )


CurrentUser = Depends(get_current_user)
