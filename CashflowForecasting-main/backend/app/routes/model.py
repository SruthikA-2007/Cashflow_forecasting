"""
Model management routes.

Endpoints:
  POST   /models/train/{dataset_id}  - Train the Random Forest model  [IMPLEMENTED]
  GET    /models/status/{job_id}     - Check training job status       [stub]
  GET    /models/info                - List available trained models    [stub]
  DELETE /models/{model_id}          - Remove a saved model            [stub]

Authentication
--------------
Every endpoint requires a valid Supabase Bearer token.
A user can only train models on their own datasets
and view / delete their own models.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_user
from app.schemas.auth import AuthUser
from app.schemas.model import ModelInfo, ModelListResponse, TrainingStatus, TrainModelResponse
from app.services.training_service import TrainingService

router = APIRouter()

_NOT_IMPLEMENTED = HTTPException(
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    detail="This endpoint is not yet implemented.",
)


# ------------------------------------------------------------------
# POST /models/train/{dataset_id}
# ------------------------------------------------------------------
@router.post(
    "/train/{dataset_id}",
    response_model=TrainModelResponse,
    status_code=status.HTTP_200_OK,
    summary="Train a Random Forest model on a prepared dataset",
)
async def train_model(
    dataset_id: str,
    user: AuthUser = Depends(get_current_user),
):
    """
    Trains a RandomForestClassifier on the settled invoice records
    of the specified dataset and returns evaluation metrics.

    Pipeline:

    1. Verifies the dataset belongs to the authenticated user.
    2. Loads settled invoices (settled_date not null) and rebuilds
       the exact preprocessing pipeline used in /prepare-training-data.
    3. Applies a stratified 80/20 train/test split.
    4. Fits RandomForestClassifier with class_weight='balanced'
       to handle imbalanced payment datasets.
    5. Evaluates on the held-out test set:
       accuracy, precision, recall, F1, ROC-AUC, confusion matrix.
    6. Persists three artefacts under ml_models/<user_id>/:
       - <dataset_id>_<model_id>_v<n>.joblib           (trained model)
       - <dataset_id>_<model_id>_v<n>_pipeline.joblib  (preprocessing pipeline)
       - <dataset_id>_<model_id>_v<n>_features.json    (feature manifest)
    7. Writes model metadata to the model_metadata Supabase table.
    8. Increments the model version for this dataset automatically.

    Prerequisites: run /clean -> /feature-engineering ->
    /prepare-training-data before calling this endpoint.

    No invoice prediction is performed here.
    """
    user_id = str(user.user_id)
    svc = TrainingService(user_id=user_id)
    return svc.train(dataset_id=dataset_id)


# ------------------------------------------------------------------
# GET /models/status/{job_id}
# ------------------------------------------------------------------
@router.get(
    "/status/{job_id}",
    response_model=TrainingStatus,
    summary="Check training job status",
)
async def training_status(
    job_id: str,
    user: AuthUser = Depends(get_current_user),
):
    raise _NOT_IMPLEMENTED


# ------------------------------------------------------------------
# GET /models/info
# ------------------------------------------------------------------
@router.get(
    "/info",
    response_model=ModelListResponse,
    summary="List available trained models for the current user",
)
async def list_models(user: AuthUser = Depends(get_current_user)):
    raise _NOT_IMPLEMENTED


# ------------------------------------------------------------------
# DELETE /models/{model_id}
# ------------------------------------------------------------------
@router.delete(
    "/{model_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a trained model",
)
async def delete_model(
    model_id: str,
    user: AuthUser = Depends(get_current_user),
):
    raise _NOT_IMPLEMENTED
