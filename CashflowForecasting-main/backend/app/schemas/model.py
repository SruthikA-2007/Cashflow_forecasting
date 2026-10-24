"""
Pydantic schemas for ML model management.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Model info
# ------------------------------------------------------------------
class ModelHyperparams(BaseModel):
    n_estimators: int = 100
    max_depth: Optional[int] = None
    min_samples_split: int = 2
    random_state: int = 42


class ModelMetrics(BaseModel):
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    roc_auc: Optional[float] = None
    confusion_matrix: Optional[list[list[int]]] = None


class ModelInfo(BaseModel):
    """Metadata for a persisted (joblib) Random Forest model."""

    id: UUID
    user_id: UUID
    dataset_id: UUID
    model_type: str = "RandomForestClassifier"
    version: str
    storage_path: str = Field(description="Path to the .joblib file in ml_models/")
    hyperparams: Optional[ModelHyperparams] = None
    metrics: Optional[ModelMetrics] = None
    feature_names: Optional[list[str]] = None
    status: str = Field(description="One of: training | ready | failed")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ModelListResponse(BaseModel):
    models: list[ModelInfo]
    total: int


# ------------------------------------------------------------------
# Training job
# ------------------------------------------------------------------
class TrainingStatus(BaseModel):
    job_id: str
    dataset_id: UUID
    status: str = Field(description="One of: pending | running | done | failed")
    model_id: Optional[UUID] = None
    message: Optional[str] = None
    progress_pct: Optional[int] = Field(None, ge=0, le=100)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ------------------------------------------------------------------
# Training result (synchronous)
# ------------------------------------------------------------------

class TrainModelResponse(BaseModel):
    """Returned synchronously by POST /models/train/{dataset_id}."""
    model_id: str
    model_name: str
    model_version: str
    dataset_id: str
    dataset_name: str
    model_type: str = "RandomForestClassifier"
    training_records: int
    test_records: int
    num_features: int
    feature_names: List[str]
    # Evaluation metrics
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    roc_auc: float
    confusion_matrix: List[List[int]]
    # Storage
    model_path: str
    pipeline_path: str
    feature_list_path: str
    processing_status: str = "model_trained"
