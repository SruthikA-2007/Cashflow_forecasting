"""
Dataset routes module.
Provides protected endpoints for querying datasets owned by the authenticated user.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from app.auth import get_current_user
from app.schemas.dataset import (
    DatasetMeta,
    DatasetListResponse,
    DatasetUploadResponse,
    DatasetCleanResponse,
    DatasetPreprocessResponse,
    DatasetFeatureEngineeringResponse,
    DatasetSummaryResponse,
    DatasetProcessedPreviewResponse,
    DatasetFeaturesResponse,
    PrepareTrainingDataResponse,
    DatasetUpdateSettlementsResponse,
)
from app.schemas.invoice import InvoiceListResponse
from app.services.dataset_service import DatasetService
from app.services.invoice_service import InvoiceService
from app.services.cleaning_service import CleaningService
from app.services.preprocessing_service import PreprocessingService
from app.services.feature_engineering_service import FeatureEngineeringService
from app.services.dataset_inspection_service import DatasetInspectionService
from app.services.training_data_service import TrainingDataService
from app.services.settlement_service import SettlementUpdateService




router = APIRouter()


# ------------------------------------------------------------------
# POST /datasets/upload
# ------------------------------------------------------------------
@router.post(
    "/upload",
    response_model=DatasetUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and validate a CSV or Excel dataset file",
)
async def upload_dataset(
    file: UploadFile = File(..., description="CSV or XLSX file containing dataset data"),
    user=Depends(get_current_user),
):
    """
    Accepts CSV or XLSX file, validates dataset readability and structure using Pandas,
    stores raw uploaded data separately, saves metadata in Supabase datasets table,
    and returns dataset_id, name, record count, detected columns, and 5-row preview.
    """
    user_id = str(getattr(user, "id", ""))
    svc = DatasetService(user_id=user_id)
    return await svc.process_and_upload(file)


# ------------------------------------------------------------------
# GET /datasets
# ------------------------------------------------------------------
@router.get(
    "",
    response_model=DatasetListResponse,
    summary="List datasets for the authenticated user",
)
async def list_datasets(user=Depends(get_current_user)):
    """
    Returns datasets belonging exclusively to the authenticated user.
    Uses authenticated user ID for query filtering.
    """
    user_id = str(getattr(user, "id", ""))
    svc = DatasetService(user_id=user_id)
    return svc.list_all()


# ------------------------------------------------------------------
# GET /datasets/{dataset_id}
# ------------------------------------------------------------------
@router.get(
    "/{dataset_id}",
    response_model=DatasetMeta,
    summary="Get dataset metadata by ID",
)
async def get_dataset(
    dataset_id: str,
    user=Depends(get_current_user),
):
    """
    Returns metadata for a specific dataset ID.
    Verifies dataset ID and user ownership.
    Returns HTTP 404 if dataset does not exist or does not belong to the user.
    """
    user_id = str(getattr(user, "id", ""))
    svc = DatasetService(user_id=user_id)
    meta = svc.get_by_id(dataset_id)
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found or access denied.",
        )
    return meta



# ------------------------------------------------------------------
# GET /datasets/{dataset_id}/invoices
# ------------------------------------------------------------------
@router.get(
    "/{dataset_id}/invoices",
    response_model=InvoiceListResponse,
    summary="Get paginated invoices for a dataset",
)
async def get_dataset_invoices(
    dataset_id: str,
    page: int = Query(1, ge=1, description="Page number (starts at 1)"),
    limit: int = Query(50, ge=1, le=500, description="Records per page (max 500)"),
    user=Depends(get_current_user),
):
    """
    Returns a paginated list of invoice records belonging to the specified dataset.
    Verifies that both the dataset and invoices belong strictly to the authenticated user.
    Returns HTTP 404 if dataset is missing or access is unauthorized.
    """
    user_id = str(getattr(user, "id", ""))
    invoice_svc = InvoiceService(user_id=user_id)
    return invoice_svc.get_by_dataset(dataset_id=dataset_id, page=page, limit=limit)



# ------------------------------------------------------------------
# POST /datasets/{dataset_id}/clean
# ------------------------------------------------------------------

@router.post(
    "/{dataset_id}/clean",
    response_model=DatasetCleanResponse,
    summary="Clean dataset invoices (deduplicate, validate dates/amounts, calculate metrics)",
)
async def clean_dataset(
    dataset_id: str,
    user=Depends(get_current_user),
):
    """
    Executes dataset cleaning:
    - Verifies dataset ownership
    - Removes duplicate invoice records based on invoice_number & customer_id
    - Standardizes date values and converts invoice amounts to numeric values
    - Standardizes boolean fields
    - Validates date and amount values, removing invalid records
    - Calculates days_to_settle, days_late, and is_late metrics
    - Updates database records and sets dataset processing_status to 'cleaned'
    """
    user_id = str(getattr(user, "id", ""))
    cleaning_svc = CleaningService(user_id=user_id)
    return cleaning_svc.clean_dataset(dataset_id=dataset_id)


# ------------------------------------------------------------------
# POST /datasets/{dataset_id}/preprocess
# ------------------------------------------------------------------
@router.post(
    "/{dataset_id}/preprocess",
    response_model=DatasetPreprocessResponse,
    summary="Preprocess dataset invoices for machine learning",
)
async def preprocess_dataset(
    dataset_id: str,
    user=Depends(get_current_user),
):
    """
    Executes machine learning preprocessing:
    - Verifies dataset ownership
    - Loads cleaned invoice records for authenticated user
    - Extracts date-related features & payment terms without data leakage
    - Imputes missing values and encodes categorical features
    - Saves preprocessing configuration and feature metadata
    - Updates dataset processing_status to 'preprocessed'
    """
    user_id = str(getattr(user, "id", ""))
    prep_svc = PreprocessingService(user_id=user_id)
    return prep_svc.preprocess_dataset(dataset_id=dataset_id)


# ------------------------------------------------------------------
# POST /datasets/{dataset_id}/feature-engineering
# ------------------------------------------------------------------
@router.post(
    "/{dataset_id}/feature-engineering",
    response_model=DatasetFeatureEngineeringResponse,
    summary="Engineer features for authenticated user's dataset",
)
async def feature_engineering_dataset(
    dataset_id: str,
    user=Depends(get_current_user),
):
    """
    Executes feature engineering on cleaned dataset invoices:
    - Verifies dataset ownership
    - Generates 10 domain features (days_to_due, invoice_month, invoice_weekday,
      paperless_flag, disputed_flag, invoice_amount_bucket, customer_avg_dayslate,
      customer_dispute_rate, customer_risk_drift, country_avg_dayslate)
    - Enforces point-in-time calculation to prevent data leakage
    - Gracefully records missing features as unavailable
    - Updates dataset processing_status to 'feature_engineered'
    """
    user_id = str(getattr(user, "id", ""))
    fe_svc = FeatureEngineeringService(user_id=user_id)
    return fe_svc.engineer_dataset(dataset_id=dataset_id)


# ------------------------------------------------------------------
# GET /datasets/{dataset_id}/summary
# ------------------------------------------------------------------
@router.get(
    "/{dataset_id}/summary",
    response_model=DatasetSummaryResponse,
    summary="Aggregated pipeline summary for a dataset",
)
async def get_dataset_summary(
    dataset_id: str,
    user=Depends(get_current_user),
):
    """
    Returns an aggregated view of the dataset processing pipeline:
    - Dataset name, total records, and current processing status
    - Cleaning summary (duplicates removed, invalid records, etc.)
    - Preprocessing summary (features used, imputation stats, etc.)
    - Feature engineering summary (features created, unavailable features)
    Only data belonging to the authenticated user is returned.
    """
    user_id = str(getattr(user, "id", ""))
    svc = DatasetInspectionService(user_id=user_id)
    return svc.get_summary(dataset_id=dataset_id)


# ------------------------------------------------------------------
# GET /datasets/{dataset_id}/processed-preview
# ------------------------------------------------------------------
@router.get(
    "/{dataset_id}/processed-preview",
    response_model=DatasetProcessedPreviewResponse,
    summary="Preview cleaned and feature-engineered records for a dataset",
)
async def get_dataset_processed_preview(
    dataset_id: str,
    limit: int = Query(20, ge=1, le=200, description="Maximum number of records to return (max 200)"),
    user=Depends(get_current_user),
):
    """
    Returns a limited preview of records with cleaned field values and,
    when feature engineering has been run, the computed feature columns.
    Only data belonging to the authenticated user is returned.
    """
    user_id = str(getattr(user, "id", ""))
    svc = DatasetInspectionService(user_id=user_id)
    return svc.get_processed_preview(dataset_id=dataset_id, limit=limit)


# ------------------------------------------------------------------
# GET /datasets/{dataset_id}/features
# ------------------------------------------------------------------
@router.get(
    "/{dataset_id}/features",
    response_model=DatasetFeaturesResponse,
    summary="Feature catalog with availability status for a dataset",
)
async def get_dataset_features(
    dataset_id: str,
    user=Depends(get_current_user),
):
    """
    Returns the full feature catalog for the dataset:
    - Feature name and description
    - Data type
    - Availability status (available / unavailable) based on dataset columns
      and prior feature-engineering results
    - Whether the feature is used for machine learning
    Only data belonging to the authenticated user is returned.
    """
    user_id = str(getattr(user, "id", ""))
    svc = DatasetInspectionService(user_id=user_id)
    return svc.get_features(dataset_id=dataset_id)


# ------------------------------------------------------------------
# POST /datasets/{dataset_id}/prepare-training-data
# ------------------------------------------------------------------
@router.post(
    "/{dataset_id}/prepare-training-data",
    response_model=PrepareTrainingDataResponse,
    status_code=status.HTTP_200_OK,
    summary="Prepare a labelled feature matrix for model training",
)
async def prepare_training_data(
    dataset_id: str,
    user=Depends(get_current_user),
):
    """
    Converts settled, cleaned invoice records into a supervised training dataset:

    - **Filters** to only settled invoices where the payment outcome is known.
    - **Drops** rows where ``is_late`` cannot be determined.
    - **Selects** feature columns; unconditionally excludes invoice ID, dataset ID,
      user ID, ``settled_date``, ``days_to_settle``, ``days_late`` and other
      direct-outcome leakage columns.
    - **Derives** temporal features (``invoice_month``, ``invoice_weekday``,
      ``invoice_quarter``, ``payment_term_days``) when absent.
    - **Imputes** missing numeric values with the median; categorical with the mode.
    - **One-hot encodes** categorical columns (``country_code``,
      ``invoice_amount_bucket``).
    - **Persists** the full preprocessing pipeline configuration and the final
      feature name list to
      ``uploads/training/<user_id>/<dataset_id>_pipeline.json``.

    No model is trained.  Only authenticated users may access their own datasets.
    """
    user_id = str(getattr(user, "id", ""))
    svc = TrainingDataService(user_id=user_id)
    return svc.prepare(dataset_id=dataset_id)


# ------------------------------------------------------------------
# POST /datasets/{dataset_id}/update-settlements
# ------------------------------------------------------------------
@router.post(
    "/{dataset_id}/update-settlements",
    response_model=DatasetUpdateSettlementsResponse,
    status_code=status.HTTP_200_OK,
    summary="Update invoice settlements via CSV or Excel upload",
)
async def update_settlements(
    dataset_id: str,
    file: UploadFile = File(...),
    user=Depends(get_current_user),
):
    """
    Accepts an uploaded CSV or Excel file containing newly settled or updated invoice records:

    - **Verifies** dataset ownership for the authenticated user.
    - **Matches** existing invoices primarily using ``(invoice_number, customer_id)``.
    - **Updates** settlement details: ``settled_date``, ``payment_status``, ``days_to_settle``, ``days_late``, ``is_late``.
    - **Adds** genuinely new invoice records while preventing duplicates.
    - **Preserves** all historical invoice records without deletion.
    - **Recalculates** affected historical features (``customer_avg_dayslate``, ``customer_dispute_rate``, etc.).
    - **Marks** dataset and model status as ``requires_retraining``.
    """
    user_id = str(getattr(user, "id", ""))
    svc = SettlementUpdateService(user_id=user_id)
    return await svc.update_settlements(dataset_id=dataset_id, file=file)


