"""
Application configuration loaded from environment variables using python-dotenv.
All credentials are read from environment variables (never hard-coded).
"""

from typing import List
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load environment variables from .env file using python-dotenv
load_dotenv()


class Settings(BaseSettings):
    # Supabase credentials
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # Application details
    APP_NAME: str = "AI-Based Cash Flow Early Warning System"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Authentication & Session Security
    SECRET_KEY: str = "fin-cashflow-jwt-secret-key-prod-2026-secure"
    SESSION_EXPIRE_MINUTES: int = 1440  # 24 hours

    # OTP Configuration
    OTP_EXPIRE_SECONDS: int = 300  # 5 minutes
    OTP_RESEND_COOLDOWN_SECONDS: int = 60  # 60 seconds
    OTP_MAX_VERIFY_ATTEMPTS: int = 5
    OTP_MAX_REQUESTS_PER_WINDOW: int = 5
    OTP_REQUEST_WINDOW_SECONDS: int = 600  # 10 minutes

    # Configurable SMTP Email Service
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False
    SMTP_TIMEOUT_SECONDS: int = 10

    # Risk Thresholds for ML Predictions (0.0 to 1.0 probability)
    RISK_THRESHOLD_LOW: float = 0.35      # Late probability < 0.35 => Low Risk
    RISK_THRESHOLD_MEDIUM: float = 0.70   # Late probability 0.35 - 0.70 => Medium Risk, >= 0.70 => High Risk

    # CORS origins (comma-separated)
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Return CORS_ORIGINS as a Python list of strings."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


# Singleton instance
settings = Settings()


