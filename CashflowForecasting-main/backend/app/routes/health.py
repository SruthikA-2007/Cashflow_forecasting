"""
GET /health  – application liveness / readiness check.
"""

from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import settings

router = APIRouter()


@router.get("/health", summary="Health check")
async def health_check() -> JSONResponse:
    """
    Returns the current application status, version, and UTC timestamp.
    Use this endpoint to verify the service is reachable and running.
    """
    return JSONResponse(
        content={
            "status": "ok",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
    )
