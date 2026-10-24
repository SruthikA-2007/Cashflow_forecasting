"""
Comprehensive Test Suite for Email OTP-Based Authentication.

Tests:
1. Valid email addresses from any domain (Gmail, Outlook, company domains, etc.)
2. Rejection of invalid email formats
3. OTP generation using cryptographically secure random generator (6 digits)
4. OTP never leaked in API responses
5. Configurable SMTP email service & clear email delivery failure reporting
6. OTP verification and creation of secure authenticated session token
7. 5-minute OTP expiry enforcement
8. Invalidation of previous OTP when a new one is issued
9. Prevention of OTP reuse (single-use guarantee)
10. Rate limiting for resend cooldown (60s)
11. Rate limiting for incorrect verification attempts (max 5)
12. Private route protection (HTTP 401 Unauthorized without valid session)
13. Logout and session token revocation
"""

import time
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services.email_service import EmailDeliveryError, email_service
from app.services.otp_service import otp_service

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_otp_state():
    """Reset OTP service state before each test."""
    otp_service.clear_all_for_testing()
    yield
    otp_service.clear_all_for_testing()


def test_any_email_domain_accepted():
    """Test requirement 3: Accept valid emails from any domain (Gmail, Outlook, company, etc.)"""
    test_emails = [
        "john.doe@gmail.com",
        "sarah.connor@outlook.com",
        "alexander@yahoo.com",
        "finance.director@acme-corporation.co.uk",
        "analyst@fintech.io",
        "cfo@sub.company.org",
    ]

    with patch.object(email_service, "send_otp_email") as mock_send:
        mock_send.return_value = None

        for email in test_emails:
            otp_service.clear_all_for_testing()
            resp = client.post("/auth/send-otp", json={"email": email})
            assert resp.status_code == 200, f"Failed for email {email}: {resp.text}"
            data = resp.json()
            assert data["status"] == "success"
            # Crucial check: OTP must NOT be returned in response!
            assert "otp" not in data
            assert "code" not in data
            assert email in data["message"]


def test_invalid_email_format_rejected():
    """Test rejection of malformed email addresses."""
    invalid_emails = [
        "not-an-email",
        "@missingusername.com",
        "missingatsign.com",
        "",
        "spaces in@email.com",
    ]

    for bad_email in invalid_emails:
        resp = client.post("/auth/send-otp", json={"email": bad_email})
        assert resp.status_code in [400, 422], f"Expected error for {bad_email}, got {resp.status_code}"


def test_otp_never_returned_in_api_response():
    """Test requirement 4: Do not display or return the OTP in API response."""
    with patch.object(email_service, "send_otp_email") as mock_send:
        mock_send.return_value = None

        resp = client.post("/auth/send-otp", json={"email": "audit@company.com"})
        assert resp.status_code == 200
        content = resp.text
        json_data = resp.json()

        # Verify no 6-digit number is contained in the response body
        import re
        digit_matches = re.findall(r"\b\d{6}\b", content)
        assert len(digit_matches) == 0, f"Found 6-digit code leaked in API response: {digit_matches}"
        assert "otp" not in json_data


def test_email_delivery_failure_clear_message():
    """Test requirement 4 & 10: Clear error message when SMTP service fails or is not configured."""
    # Temporarily unset SMTP_HOST to simulate unconfigured SMTP
    original_host = settings.SMTP_HOST
    try:
        settings.SMTP_HOST = ""
        resp = client.post("/auth/send-otp", json={"email": "user@domain.com"})
        assert resp.status_code == 502
        assert "SMTP email service is not configured" in resp.json()["detail"]
    finally:
        settings.SMTP_HOST = original_host


def test_successful_otp_login_flow():
    """Test requirements 5, 6, 8: Complete login flow, verification, session creation."""
    test_email = "analyst@globalfinance.com"
    captured_otp = None

    def capture_otp(to_email, otp):
        nonlocal captured_otp
        captured_otp = otp

    with patch.object(email_service, "send_otp_email", side_effect=capture_otp):
        # 1. Send OTP
        resp = client.post("/auth/send-otp", json={"email": test_email})
        assert resp.status_code == 200
        assert captured_otp is not None
        assert len(captured_otp) == 6
        assert captured_otp.isdigit()

        # 2. Verify OTP
        verify_resp = client.post("/auth/verify-otp", json={"email": test_email, "otp": captured_otp})
        assert verify_resp.status_code == 200
        verify_data = verify_resp.json()
        assert verify_data["status"] == "success"
        token = verify_data["token"]
        assert token is not None
        assert verify_data["user"]["email"] == test_email

        # 3. Access protected /auth/me route with token
        me_resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == test_email


def test_otp_expiry_5_minutes():
    """Test requirement 6: Set a five-minute expiry on OTPs."""
    test_email = "timelimit@example.com"
    captured_otp = None

    def capture_otp(to_email, otp):
        nonlocal captured_otp
        captured_otp = otp

    with patch.object(email_service, "send_otp_email", side_effect=capture_otp):
        resp = client.post("/auth/send-otp", json={"email": test_email})
        assert resp.status_code == 200

        # Simulate time moving past 300 seconds (5 minutes)
        with patch("time.time", return_value=time.time() + 301):
            verify_resp = client.post("/auth/verify-otp", json={"email": test_email, "otp": captured_otp})
            assert verify_resp.status_code == 400
            assert "expired" in verify_resp.json()["detail"].lower()


def test_otp_invalidation_after_successful_verification_prevent_reuse():
    """Test requirement 6: Invalidate OTP after successful verification, prevent reuse."""
    test_email = "onetime@example.com"
    captured_otp = None

    def capture_otp(to_email, otp):
        nonlocal captured_otp
        captured_otp = otp

    with patch.object(email_service, "send_otp_email", side_effect=capture_otp):
        client.post("/auth/send-otp", json={"email": test_email})
        assert captured_otp is not None

        # First verification must succeed
        v1 = client.post("/auth/verify-otp", json={"email": test_email, "otp": captured_otp})
        assert v1.status_code == 200

        # Second verification with identical OTP must FAIL (prevent reuse)
        v2 = client.post("/auth/verify-otp", json={"email": test_email, "otp": captured_otp})
        assert v2.status_code == 400
        assert "no active verification code" in v2.json()["detail"].lower() or "expired" in v2.json()["detail"].lower()


def test_invalidate_previous_otp_when_new_one_issued():
    """Test requirement 7: Invalidate previous OTPs when a new one is issued."""
    test_email = "replacement@example.com"
    otps = []

    def capture_otp(to_email, otp):
        otps.append(otp)

    with patch.object(email_service, "send_otp_email", side_effect=capture_otp):
        # 1. Request first OTP
        r1 = client.post("/auth/send-otp", json={"email": test_email})
        assert r1.status_code == 200
        otp1 = otps[0]

        # Simulate 65 seconds passed so cooldown allows resend
        with patch("time.time", return_value=time.time() + 65):
            r2 = client.post("/auth/send-otp", json={"email": test_email})
            assert r2.status_code == 200
            otp2 = otps[1]

            # Trying to use old OTP1 MUST fail because it was invalidated by OTP2
            v1 = client.post("/auth/verify-otp", json={"email": test_email, "otp": otp1})
            assert v1.status_code in [400, 429]

            # Using new OTP2 MUST succeed
            v2 = client.post("/auth/verify-otp", json={"email": test_email, "otp": otp2})
            assert v2.status_code == 200


def test_resend_cooldown_rate_limit():
    """Test requirement 7: Implement resend cooldown rate limit (60s)."""
    test_email = "cooldown@example.com"

    with patch.object(email_service, "send_otp_email"):
        # First request succeeds
        r1 = client.post("/auth/send-otp", json={"email": test_email})
        assert r1.status_code == 200

        # Immediate second request must trigger HTTP 429 Too Many Requests
        r2 = client.post("/auth/send-otp", json={"email": test_email})
        assert r2.status_code == 429
        assert "wait" in r2.json()["detail"].lower()


def test_incorrect_verification_attempts_rate_limit():
    """Test requirement 7: Limit incorrect verification attempts and invalidate OTP on max failed attempts."""
    test_email = "security@example.com"
    captured_otp = None

    def capture_otp(to_email, otp):
        nonlocal captured_otp
        captured_otp = otp

    with patch.object(email_service, "send_otp_email", side_effect=capture_otp):
        client.post("/auth/send-otp", json={"email": test_email})

        # Submit wrong OTPs up to the limit
        for i in range(1, 5):
            wrong_otp = f"{i:06d}"
            if wrong_otp == captured_otp:
                wrong_otp = "999999"
            v = client.post("/auth/verify-otp", json={"email": test_email, "otp": wrong_otp})
            assert v.status_code == 400
            assert "remaining" in v.json()["detail"]

        # 5th failed attempt must invalidate the OTP
        v_final = client.post("/auth/verify-otp", json={"email": test_email, "otp": "000000"})
        assert v_final.status_code == 429 or "invalidated" in v_final.json()["detail"].lower()

        # Even if the correct OTP is now supplied, it was invalidated and must be rejected!
        v_correct = client.post("/auth/verify-otp", json={"email": test_email, "otp": captured_otp})
        assert v_correct.status_code in [400, 429]


def test_protected_routes_require_authentication():
    """Test requirement 8: Protect private backend APIs with HTTP 401."""
    # 1. Access without Authorization header -> 401
    resp_no_auth = client.get("/auth/me")
    assert resp_no_auth.status_code == 401

    # 2. Access with malformed token -> 401
    resp_bad_auth = client.get("/auth/me", headers={"Authorization": "Bearer invalid.jwt.token"})
    assert resp_bad_auth.status_code == 401

    # 3. Access private predictions endpoint without token -> 401
    resp_pred_no_auth = client.get("/predictions/companies")
    assert resp_pred_no_auth.status_code == 401


def test_logout_invalidates_session():
    """Test requirement 8: Implement logout and invalidate session token."""
    test_email = "logout.user@example.com"
    captured_otp = None

    def capture_otp(to_email, otp):
        nonlocal captured_otp
        captured_otp = otp

    with patch.object(email_service, "send_otp_email", side_effect=capture_otp):
        client.post("/auth/send-otp", json={"email": test_email})
        login_resp = client.post("/auth/verify-otp", json={"email": test_email, "otp": captured_otp})
        token = login_resp.json()["token"]

        # Verify access works before logout
        auth_header = {"Authorization": f"Bearer {token}"}
        me1 = client.get("/auth/me", headers=auth_header)
        assert me1.status_code == 200

        # Perform logout
        logout_resp = client.post("/auth/logout", headers=auth_header)
        assert logout_resp.status_code == 200

        # Subsequent call with the revoked token must be rejected with 401
        me2 = client.get("/auth/me", headers=auth_header)
        assert me2.status_code == 401
        assert "revoked" in me2.json()["detail"].lower() or "invalid" in me2.json()["detail"].lower()


if __name__ == "__main__":
    pytest.main(["-s", "--capture=no", "test_otp_auth.py"])
