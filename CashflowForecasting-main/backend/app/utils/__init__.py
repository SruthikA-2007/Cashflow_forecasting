"""
Shared utility helpers.

Add reusable, stateless functions here – e.g., date parsing,
response formatters, token verification wrappers.
"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(tz=timezone.utc)


def utc_now_iso() -> str:
    """Return the current UTC datetime as an ISO 8601 string."""
    return utc_now().isoformat()
