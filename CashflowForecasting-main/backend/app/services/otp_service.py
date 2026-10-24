"""
OTP and Session Authentication Service.

Implements:
1. Cryptographically secure 6-digit random OTP generation using `secrets`.
2. 5-minute OTP expiry.
3. Invalidation of previous OTPs when a new one is issued.
4. Single-use OTP enforcement (invalidation immediately after verification, preventing reuse).
5. Rate limiting for OTP requests, resend cooldown, and max verification attempts.
6. Signed JWT session tokens with revocation support on logout.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import jwt

from app.config import settings

logger = logging.getLogger(__name__)

# Standard RFC-compliant email regex accepting any domain
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class OtpError(Exception):
    """Base exception for OTP authentication errors."""
    pass


class OtpRateLimitError(OtpError):
    """Raised when request cooldown or attempt rate limits are exceeded."""
    def __init__(self, message: str, retry_after_seconds: int = 0):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class OtpExpiredError(OtpError):
    """Raised when submitted OTP has expired."""
    pass


class OtpInvalidError(OtpError):
    """Raised when submitted OTP does not match."""
    def __init__(self, message: str, attempts_remaining: int = 0):
        super().__init__(message)
        self.attempts_remaining = attempts_remaining


class OtpNotFoundError(OtpError):
    """Raised when no active OTP exists for the email."""
    pass


class SessionAuthError(OtpError):
    """Raised when session token is invalid, expired, or revoked."""
    pass


class OtpService:
    """Manages secure OTP generation, verification, rate limiting, and session tokens."""

    def __init__(self):
        self._lock = threading.Lock()
        # email -> {
        #   "otp_hash": str,
        #   "salt": str,
        #   "expires_at": float,
        #   "attempts": int,
        #   "created_at": float,
        #   "last_sent_at": float
        # }
        self._otp_store: Dict[str, Dict[str, Any]] = {}

        # email -> list of request timestamps within rate window
        self._request_history: Dict[str, List[float]] = {}

        # Set of revoked JWT `jti` identifiers
        self._revoked_tokens: Set[str] = set()

    @staticmethod
    def is_valid_email(email: str) -> bool:
        """Validate email format without any domain restriction."""
        if not email or not isinstance(email, str):
            return False
        trimmed = email.strip()
        return bool(EMAIL_REGEX.match(trimmed))

    @staticmethod
    def _hash_otp(otp: str, salt: str) -> str:
        """Hash OTP with a per-record salt using SHA-256."""
        combined = f"{salt}:{otp}".encode("utf-8")
        return hashlib.sha256(combined).hexdigest()

    def request_otp(self, email: str) -> str:
        """
        Generate a new 6-digit OTP for the given email address.

        Enforces:
        - Email domain independence (any domain allowed)
        - Resend cooldown (default 60s)
        - Window request limit (default 5 requests / 10m)
        - Invalidation of any previous OTP for this email
        - 5-minute expiry

        Returns:
            The raw 6-digit OTP string to be sent via email (never returned to frontend API).

        Raises:
            ValueError: If email format is invalid.
            OtpRateLimitError: If resend cooldown or request rate limit is hit.
        """
        cleaned_email = email.strip().lower()
        if not self.is_valid_email(cleaned_email):
            raise ValueError("Please enter a valid email address.")

        now = time.time()

        with self._lock:
            # 1. Check Resend Cooldown
            existing = self._otp_store.get(cleaned_email)
            if existing:
                elapsed = now - existing.get("last_sent_at", 0)
                cooldown = settings.OTP_RESEND_COOLDOWN_SECONDS
                if elapsed < cooldown:
                    remaining = int(cooldown - elapsed)
                    logger.warning("OTP resend rate limit triggered for %s (remaining: %ss)", cleaned_email, remaining)
                    raise OtpRateLimitError(
                        f"Please wait {remaining} second{'s' if remaining != 1 else ''} before requesting a new code.",
                        retry_after_seconds=remaining,
                    )

            # 2. Check Window Request Limit (e.g. max 5 requests per 10 minutes)
            window_seconds = settings.OTP_REQUEST_WINDOW_SECONDS
            cutoff = now - window_seconds
            timestamps = [ts for ts in self._request_history.get(cleaned_email, []) if ts > cutoff]
            if len(timestamps) >= settings.OTP_MAX_REQUESTS_PER_WINDOW:
                oldest_in_window = min(timestamps)
                retry_after = int(window_seconds - (now - oldest_in_window))
                logger.warning("OTP window request limit exceeded for %s", cleaned_email)
                raise OtpRateLimitError(
                    f"Too many OTP requests for this email. Please try again in {max(retry_after, 1)} seconds.",
                    retry_after_seconds=max(retry_after, 1),
                )

            timestamps.append(now)
            self._request_history[cleaned_email] = timestamps

            # 3. Generate Cryptographically Secure 6-Digit OTP
            # Using secrets.randbelow ensures unbiased, cryptographically strong random numbers
            otp = f"{secrets.randbelow(1_000_000):06d}"

            # Salt and hash the OTP for secure memory storage
            salt = secrets.token_hex(16)
            otp_hash = self._hash_otp(otp, salt)

            # 4. Store in OTP Store, replacing and immediately invalidating any prior OTP
            self._otp_store[cleaned_email] = {
                "otp_hash": otp_hash,
                "salt": salt,
                "expires_at": now + settings.OTP_EXPIRE_SECONDS,  # 5 minutes
                "attempts": 0,
                "max_attempts": settings.OTP_MAX_VERIFY_ATTEMPTS,  # 5 attempts
                "created_at": now,
                "last_sent_at": now,
            }

            logger.info("Generated new 6-digit OTP for %s (expires in %ds, invalidates previous)", cleaned_email, settings.OTP_EXPIRE_SECONDS)
            return otp

    def verify_otp(self, email: str, input_otp: str) -> str:
        """
        Verify the OTP entered by the user.

        Enforces:
        - OTP existence and 5-minute expiry
        - Max verification attempts limit (default 5 attempts)
        - Constant-time comparison
        - Invalidation of OTP upon successful verification (prevents reuse)
        - Generation of signed JWT session token

        Returns:
            Signed JWT session token for the authenticated user.

        Raises:
            OtpNotFoundError: If no OTP was requested or already used.
            OtpExpiredError: If OTP has expired.
            OtpRateLimitError: If max verification attempts exceeded.
            OtpInvalidError: If OTP is incorrect.
        """
        cleaned_email = email.strip().lower()
        cleaned_otp = (input_otp or "").strip()

        if not cleaned_otp or len(cleaned_otp) != 6 or not cleaned_otp.isdigit():
            raise OtpInvalidError("OTP must be a 6-digit numeric code.")

        now = time.time()

        with self._lock:
            record = self._otp_store.get(cleaned_email)
            if not record:
                raise OtpNotFoundError(
                    "No active verification code found for this email. It may have expired or already been used. Please request a new code."
                )

            # Check Expiry (5 minutes)
            if now > record["expires_at"]:
                del self._otp_store[cleaned_email]
                raise OtpExpiredError(
                    "The verification code has expired (5-minute validity). Please request a new one."
                )

            # Check Max Verification Attempts
            if record["attempts"] >= record["max_attempts"]:
                del self._otp_store[cleaned_email]
                raise OtpRateLimitError(
                    "Too many incorrect verification attempts. For security, this OTP has been invalidated. Please request a new code."
                )

            # Compare OTP using constant-time comparison
            expected_hash = record["otp_hash"]
            computed_hash = self._hash_otp(cleaned_otp, record["salt"])

            if not hmac.compare_digest(expected_hash, computed_hash):
                record["attempts"] += 1
                remaining = record["max_attempts"] - record["attempts"]
                if remaining <= 0:
                    del self._otp_store[cleaned_email]
                    raise OtpRateLimitError(
                        "Too many incorrect verification attempts. For security, this OTP has been invalidated. Please request a new code."
                    )
                raise OtpInvalidError(
                    f"Invalid verification code. {remaining} attempt{'s' if remaining != 1 else ''} remaining.",
                    attempts_remaining=remaining,
                )

            # Verification successful!
            # Invalidate immediately to prevent reuse
            del self._otp_store[cleaned_email]
            logger.info("OTP verified successfully for %s; OTP invalidated to prevent reuse.", cleaned_email)

            # Create authenticated session token
            token = self.create_session_token(cleaned_email)
            return token

    def create_session_token(self, email: str) -> str:
        """Create a signed JWT session token."""
        now = int(time.time())
        exp = now + (settings.SESSION_EXPIRE_MINUTES * 60)
        jti = secrets.token_hex(16)

        payload = {
            "sub": email,
            "email": email,
            "jti": jti,
            "iat": now,
            "exp": exp,
            "iss": "cashflow-forecasting-auth",
        }

        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        return token

    def validate_session_token(self, token: str) -> Dict[str, Any]:
        """
        Validate signed session JWT token and verify it has not been revoked.

        Raises:
            SessionAuthError: If invalid, expired, or revoked.
        """
        if not token:
            raise SessionAuthError("No authorization token provided.")

        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=["HS256"],
                options={"verify_exp": True},
            )
        except jwt.ExpiredSignatureError as exc:
            raise SessionAuthError("Session has expired. Please log in again.") from exc
        except jwt.InvalidTokenError as exc:
            raise SessionAuthError("Invalid session token. Please log in again.") from exc

        jti = payload.get("jti")
        with self._lock:
            if jti and jti in self._revoked_tokens:
                raise SessionAuthError("Session has been logged out and invalidated.")

        return payload

    def revoke_session(self, token: str) -> None:
        """Revoke a session token on logout, invalidating it permanently."""
        if not token:
            return

        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=["HS256"],
                options={"verify_exp": False},
            )
            jti = payload.get("jti")
            if jti:
                with self._lock:
                    self._revoked_tokens.add(jti)
                logger.info("Session token jti=%s revoked on logout.", jti)
        except Exception as exc:
            logger.warning("Failed to parse token during revocation: %s", exc)

    def clear_all_for_testing(self) -> None:
        """Reset internal stores for test isolation."""
        with self._lock:
            self._otp_store.clear()
            self._request_history.clear()
            self._revoked_tokens.clear()


# Singleton instance
otp_service = OtpService()
