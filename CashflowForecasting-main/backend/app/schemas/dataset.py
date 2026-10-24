"""
Pydantic schemas for dataset request and response bodies.
"""

from datetime import datetime
from typing import Any, Dict, Optional, List, Union
from uuid import UUID
from pydantic import BaseModel, Field


class DatasetMeta(BaseModel):
    """Metadata record representing a row in the datasets table."""
    id: Union[int, str, UUID]  # Supports both BIGINT (existing table) and UUID
    user_id: Union[UUID, str, None] = None
    filename: str
    dataset_name: Optional[str] = None
    original_filename: Optional[str] = None
    file_size_bytes: Optional[int] = None
    row_count: Optional[int] = None
    total_records: Optional[int] = None
    column_count: Optional[int] = None
    storage_path: Optional[str] = None
    status: str = Field(default="uploaded", description="One of: uploaded | cleaning | cleaned | preprocessed | feature_engineered | ready | error")
    processing_status: Optional[str] = Field(default=None, description="Fine-grained pipeline stage: uploaded | cleaned | preprocessed | feature_engineered")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DatasetListResponse(BaseModel):
    datasets: List[DatasetMeta]
    total: int


class DatasetUploadResponse(BaseModel):
    """Response returned after successful dataset upload, mapping, and invoice storage."""
    dataset_id: str
    dataset_name: str
    original_filename: str
    total_records: int
    total_uploaded_records: int
    successfully_stored_records: int
    invalid_records: int
    detected_columns: List[str]
    detected_column_mapping: dict
    preview: List[dict]
    processing_status: str = "uploaded"


class DatasetCleanResponse(BaseModel):
    """Cleaning summary returned after data cleaning."""
    dataset_id: str
    dataset_name: str
    original_records: int
    duplicate_records_removed: int
    invalid_records_removed: int
    missing_values_handled: int
    final_records: int
    processing_status: str = "cleaned"


class DatasetPreprocessResponse(BaseModel):
    """Preprocessing summary returned after machine learning preprocessing."""
    dataset_id: str
    dataset_name: str
    records_processed: int
    columns_used: List[str]
    columns_excluded: List[str]
    missing_values_handled: int
    preprocessing_summary: dict
    processing_status: str = "preprocessed"


class DatasetFeatureEngineeringResponse(BaseModel):
    """Feature engineering summary returned after feature generation."""
    dataset_id: str
    dataset_name: str
    records_processed: int
    features_created: List[str]
    unavailable_features: List[dict]
    feature_summary: dict
    processing_status: str = "feature_engineered"


# ------------------------------------------------------------------
# Inspection schemas (summary, processed preview, features catalog)
# ------------------------------------------------------------------

class DatasetSummaryResponse(BaseModel):
    """Aggregated pipeline summary for a dataset."""
    dataset_id: str
    dataset_name: str
    total_records: int
    processing_status: str
    cleaning_summary: Optional[dict] = None
    preprocessing_summary: Optional[dict] = None
    feature_engineering_summary: Optional[dict] = None


class DatasetProcessedPreviewResponse(BaseModel):
    """Previews a limited number of cleaned + feature-engineered records."""
    dataset_id: str
    dataset_name: str
    total_records: int
    preview_count: int
    records: List[dict]


class FeatureMetadataItem(BaseModel):
    """Metadata entry for a single engineered or base feature."""
    feature_name: str
    description: str
    data_type: str
    status: str = Field(description="'available' or 'unavailable'")
    used_for_ml: bool
    unavailable_reason: Optional[str] = None


class DatasetFeaturesResponse(BaseModel):
    """Full feature catalog for a dataset."""
    dataset_id: str
    dataset_name: str
    total_features: int
    available_features: int
    unavailable_features: int
    features: List[FeatureMetadataItem]


# ------------------------------------------------------------------
# Training-data preparation schema
# ------------------------------------------------------------------

class PrepareTrainingDataResponse(BaseModel):
    """Returned after the training-data preparation step."""
    dataset_id: str
    dataset_name: str
    training_records: int
    num_features: int
    feature_names: List[str]
    target_column: str = "is_late"
    target_distribution: Dict[str, int]
    excluded_columns: List[str]
    missing_values_imputed: int
    categorical_columns_encoded: List[str]
    pipeline_config_path: str
    processing_status: str = "training_data_ready"


class DatasetUpdateSettlementsResponse(BaseModel):
    """Returned after updating settlements with an uploaded CSV/Excel file."""
    dataset_id: str
    dataset_name: str
    updated_records: int
    new_records: int
    duplicate_records_skipped: int
    unmatched_records: int
    model_refresh_status: str = "requires_retraining"
    processing_status: str = "requires_retraining"










