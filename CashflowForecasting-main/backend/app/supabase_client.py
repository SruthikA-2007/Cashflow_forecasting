"""
Reusable Supabase client module.
Initializes Supabase clients using environment variables configured in app.config.
"""

from supabase import create_client, Client
from app.config import settings


def get_supabase_client() -> Client:
    """
    Creates and returns a reusable Supabase client instance
    using SUPABASE_URL and SUPABASE_ANON_KEY.
    """
    url = settings.SUPABASE_URL
    key = settings.SUPABASE_ANON_KEY
    if not url or not key:
        # Fallback to placeholder if environment variables are not populated yet
        url = url or "https://placeholder.supabase.co"
        key = key or "placeholder-key"
    return create_client(url, key)


def get_supabase_admin_client() -> Client:
    """
    Creates and returns a Supabase admin client using SUPABASE_SERVICE_ROLE_KEY
    or SUPABASE_ANON_KEY if service role key is absent.
    """
    url = settings.SUPABASE_URL
    key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
    if not url or not key:
        url = url or "https://placeholder.supabase.co"
        key = key or "placeholder-key"
    return create_client(url, key)


# Global reusable Supabase client instances
supabase: Client = get_supabase_client()
supabase_admin: Client = get_supabase_admin_client()

