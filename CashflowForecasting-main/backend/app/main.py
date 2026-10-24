"""
FastAPI application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

# ------------------------------------------------------------------
# App instance
# ------------------------------------------------------------------
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-Based Cash Flow Early Warning System API Backend",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ------------------------------------------------------------------
# CORS – allow local frontend origins
# ------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------
# GET /health Endpoint
# ------------------------------------------------------------------
@app.get("/health", summary="Health Check Endpoint")
async def health():
    """
    Health check endpoint returning connection and server status.
    """
    return {
        "status": "running",
        "message": "Backend is connected successfully"
    }


# ------------------------------------------------------------------
# Router Registrations
# ------------------------------------------------------------------
from app.routes.auth import router as auth_router
from app.routes.datasets import router as datasets_router
from app.routes.invoices import router as invoices_router
from app.routes.model import router as model_router
from app.routes.predictions import router as predictions_router

# Mount Auth routers
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication (API)"])

# Mount under standard prefixes
app.include_router(datasets_router, prefix="/datasets", tags=["Datasets"])
app.include_router(invoices_router, prefix="/invoices", tags=["Invoices"])
app.include_router(model_router, prefix="/models", tags=["Models"])
app.include_router(predictions_router, prefix="/predictions", tags=["Predictions"])

# Mount under /api prefixes for frontend API client compatibility
app.include_router(datasets_router, prefix="/api/datasets", tags=["Datasets (API)"])
app.include_router(invoices_router, prefix="/api/invoices", tags=["Invoices (API)"])
app.include_router(model_router, prefix="/api/models", tags=["Models (API)"])
app.include_router(predictions_router, prefix="/api/predictions", tags=["Predictions (API)"])
app.include_router(predictions_router, prefix="/api", tags=["API Root"])
app.include_router(predictions_router, tags=["Root Predictions"])







