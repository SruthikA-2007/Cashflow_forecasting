"""
Authentication module re-exporting canonical `get_current_user` dependency.
"""

from app.dependencies.auth import get_current_user, CurrentUser, extract_token_from_request

__all__ = ["get_current_user", "CurrentUser", "extract_token_from_request"]
