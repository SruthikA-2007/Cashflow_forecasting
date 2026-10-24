"""
Configurable SMTP Email Service for OTP delivery.

Sends one-time passcodes to users via standard SMTP with support for
STARTTLS (port 587) and SSL/TLS (port 465).
Credentials and host configurations are loaded from environment variables.
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    """Raised when OTP email delivery fails."""
    pass


class EmailService:
    """Configurable SMTP email service for Cash Flow Early Warning System."""

    def __init__(self):
        pass

    @property
    def is_configured(self) -> bool:
        """Check if SMTP credentials and host are configured."""
        return bool(settings.SMTP_HOST and settings.SMTP_HOST.strip())

    def send_otp_email(self, to_email: str, otp: str) -> None:
        """
        Send a 6-digit OTP code to the recipient email via configured SMTP server.

        Raises:
            EmailDeliveryError: If SMTP is not configured or sending fails.
        """
        if not self.is_configured:
            logger.error("SMTP delivery attempted but SMTP_HOST is not configured.")
            raise EmailDeliveryError(
                "SMTP email service is not configured. Please set SMTP_HOST, SMTP_PORT, "
                "SMTP_USER, and SMTP_PASSWORD in backend/.env"
            )

        from_email = (
            settings.SMTP_FROM_EMAIL.strip()
            if settings.SMTP_FROM_EMAIL
            else settings.SMTP_USER.strip()
        )
        if not from_email:
            from_email = f"noreply@{settings.SMTP_HOST}"

        subject = "Your Verification Code - Cash Flow Early Warning System"

        # Construct Plain Text Body
        text_body = (
            f"Hello,\n\n"
            f"Your one-time passcode (OTP) for the Cash Flow Early Warning System is: {otp}\n\n"
            f"This code is valid for 5 minutes and can only be used once.\n"
            f"If you did not request this code, please ignore this email.\n\n"
            f"Best regards,\n"
            f"Cash Flow Forecasting & Risk Analytics Team"
        )

        # Construct Styled HTML Body
        html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Your Verification Code</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 32px 16px; margin: 0;">
  <div style="max-width: 520px; margin: 0 auto; background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 32px; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);">
    <div style="border-bottom: 1px solid #334155; padding-bottom: 20px; margin-bottom: 24px;">
      <h2 style="margin: 0; color: #38bdf8; font-size: 20px; font-weight: 700; letter-spacing: -0.025em;">
        Cash Flow Early Warning System
      </h2>
      <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 13px;">Secure OTP Authentication</p>
    </div>

    <p style="margin: 0 0 16px 0; color: #cbd5e1; font-size: 15px; line-height: 1.5;">
      Use the one-time passcode (OTP) below to authenticate and access your financial dashboard:
    </p>

    <div style="background: #0f172a; border: 1px solid #38bdf8; border-radius: 8px; padding: 20px; text-align: center; margin: 24px 0;">
      <span style="font-family: 'Courier New', Courier, monospace; font-size: 36px; font-weight: 800; letter-spacing: 8px; color: #38bdf8;">
        {otp}
      </span>
    </div>

    <div style="background: rgba(245, 158, 11, 0.1); border-left: 4px solid #f59e0b; padding: 12px 16px; border-radius: 4px; margin-bottom: 24px;">
      <p style="margin: 0; color: #fde68a; font-size: 13px; line-height: 1.4;">
        <strong>Notice:</strong> This code expires in <strong>5 minutes</strong>. It can only be used once and previous codes are invalidated.
      </p>
    </div>

    <p style="margin: 0 0 8px 0; color: #94a3b8; font-size: 12px; line-height: 1.4;">
      If you did not request this verification code, please ignore this email. No access will be granted without the code.
    </p>

    <div style="border-top: 1px solid #334155; padding-top: 16px; margin-top: 24px; text-align: center;">
      <p style="margin: 0; color: #64748b; font-size: 12px;">
        AI-Based Cash Flow Forecasting &amp; Early Warning System
      </p>
    </div>
  </div>
</body>
</html>"""

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email

        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        timeout = settings.SMTP_TIMEOUT_SECONDS

        try:
            if settings.SMTP_USE_SSL:
                server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=timeout)
            else:
                server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=timeout)

            with server:
                server.ehlo()
                if settings.SMTP_USE_TLS and not settings.SMTP_USE_SSL:
                    server.starttls()
                    server.ehlo()

                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)

                server.sendmail(from_email, [to_email], msg.as_string())
                logger.info("Successfully sent OTP email to %s via %s:%s", to_email, settings.SMTP_HOST, settings.SMTP_PORT)

        except smtplib.SMTPAuthenticationError as auth_err:
            logger.error("SMTP authentication failed for user %s: %s", settings.SMTP_USER, auth_err)
            raise EmailDeliveryError(
                "SMTP authentication failed. Please verify your SMTP_USER and SMTP_PASSWORD credentials in backend/.env"
            ) from auth_err
        except (smtplib.SMTPException, OSError) as exc:
            logger.error("SMTP delivery error sending to %s: %s", to_email, exc)
            raise EmailDeliveryError(
                f"Failed to deliver OTP email to {to_email}: {str(exc)}"
            ) from exc
        except Exception as exc:
            logger.error("Unexpected error during SMTP email delivery: %s", exc)
            raise EmailDeliveryError(
                f"Unexpected email delivery failure: {str(exc)}"
            ) from exc


# Singleton instance
email_service = EmailService()
