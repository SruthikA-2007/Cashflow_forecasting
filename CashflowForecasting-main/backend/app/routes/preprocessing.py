"""
Preprocessing routes.

Endpoints:
  POST  /api/preprocessing/run/{dataset_id}    – Run preprocessing on a dataset
  GET   /api/preprocessing/status/{job_id}     – Check status of a preprocessing job
  GET   /api/preprocessing/result/{dataset_id} – Fetch preprocessed data summary

Authentication
--------------
Every endpoint requires a valid Supabase Bearer token.
The caller can only trigger / view preprocessing for datasets they own.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_user
from app.schemas.auth import AuthUser
from app.schemas.dataset import PreprocessingResult, PreprocessingStatus
from app.services.preprocessing_service import PreprocessingService

router = APIRouter()


# ------------------------------------------------------------------
# Run preprocessing
# ------------------------------------------------------------------
@router.post(
    "/run/{dataset_id}",
    response_model=PreprocessingStatus,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger preprocessing for a dataset",
)
async def run_preprocessing(
    dataset_id: str,
    user: AuthUser = Depends(get_current_user),
):
    """
    Kicks off a preprocessing pipeline for the specified dataset.
    The dataset must belong to the authenticated user – cross-user
    access is rejected with 404.

    Steps: missing-value imputation, outlier detection,
    date parsing, column normalisation.

    Returns a job ID that can be polled via GET /status/{job_id}.
    """
    svc = PreprocessingService(user_id=user.user_id)
    job = await svc.run(dataset_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found or you do not have access to it.",
        )
    return job


# ------------------------------------------------------------------
# Job status
# ------------------------------------------------------------------
@router.get(
    "/status/{job_id}",
    response_model=PreprocessingStatus,
    summary="Check preprocessing job status",
)
async def preprocessing_status(
    job_id: str,
    user: AuthUser = Depends(get_current_user),
):
    """
    Returns the current status of a preprocessing job.
    Only jobs belonging to the authenticated user are accessible.
    """
    svc = PreprocessingService(user_id=user.user_id)
    job = await svc.get_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


# ------------------------------------------------------------------
# Result summary
# ------------------------------------------------------------------
@router.get(
    "/result/{dataset_id}",
    response_model=PreprocessingResult,
    summary="Fetch preprocessing result summary for a dataset",
)
async def preprocessing_result(
    dataset_id: str,
    user: AuthUser = Depends(get_current_user),
):
    """
    Returns the preprocessing result summary for a dataset.
    The dataset must belong to the authenticated user.
    """
    svc = PreprocessingService(user_id=user.user_id)
    result = await svc.get_result(dataset_id)
    if not result:
        raise HTTPException(status_code=404, detail="No preprocessing result found.")
    return result
