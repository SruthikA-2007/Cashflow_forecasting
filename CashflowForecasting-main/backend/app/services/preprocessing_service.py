"""
Preprocessing service module.
Handles loading cleaned invoice records for a dataset, applying ML feature transformations
without data leakage, persisting preprocessing configurations, and updating processing status.
"""

import json
import os
import pandas as pd
from datetime import datetime, timezone
from fastapi import HTTPException, status

from app.schemas.dataset import DatasetPreprocessResponse
from app.services.dataset_service import DatasetService
from app.supabase_client import supabase_admin
from app.utils.ml_preprocessor import DatasetPreprocessor

DATASETS_TABLE = "datasets"
INVOICES_TABLE = "invoices"
PREPROCESSED_DIR = os.path.join(os.getcwd(), "uploads", "preprocessed")


class PreprocessingService:
    """
    ML Preprocessing service scoped strictly to the authenticated user.
    """

    def __init__(self, user_id: str) -> None:
        self._user_id = str(user_id)
        self._sb = supabase_admin

    def preprocess_dataset(self, dataset_id: str) -> DatasetPreprocessResponse:
        """
        Executes ML preprocessing on invoice records for the specified dataset.
        """
        # 1. Verify dataset ownership
        dataset_svc = DatasetService(self._user_id)
        dataset = dataset_svc.get_by_id(dataset_id)
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found or access denied.",
            )

        # 2. Fetch invoice records belonging to dataset & user
        try:
            response = (
                self._sb.table(INVOICES_TABLE)
                .select("*")
                .eq("dataset_id", str(dataset_id))
                .eq("user_id", self._user_id)
                .execute()
            )
            raw_records = response.data if response and response.data else []
        except Exception:
            raw_records = []

        if not raw_records:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No cleaned invoice records found for this dataset to preprocess.",
            )

        df = pd.DataFrame(raw_records)

        # 3. Transform features using reusable DatasetPreprocessor (Leakage-free)
        try:
            X, y, config = DatasetPreprocessor.process(df)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Preprocessing failed: {str(e)}",
            )

        # 4. Save preprocessing configuration and feature metadata
        user_prep_dir = os.path.join(PREPROCESSED_DIR, self._user_id)
        os.makedirs(user_prep_dir, exist_ok=True)
        config_path = os.path.join(user_prep_dir, f"{dataset_id}_config.json")

        prep_metadata = {
            "dataset_id": str(dataset_id),
            "user_id": self._user_id,
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "config": config,
            "sample_shape": list(X.shape),
            "target_distribution": {str(k): int(v) for k, v in y.value_counts().to_dict().items()} if y is not None else {},
        }

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(prep_metadata, f, indent=2)

        # 5. Update datasets table status to 'preprocessed'
        dataset_name = getattr(dataset, "filename", "dataset")
        if hasattr(dataset, "original_filename") and dataset.original_filename:
            dataset_name = os.path.splitext(dataset.original_filename)[0]

        now = datetime.now(tz=timezone.utc).isoformat()
        try:
            self._sb.table(DATASETS_TABLE).update({
                "status": "ready",
                "processing_status": "preprocessed",
                "updated_at": now,
            }).eq("id", str(dataset_id)).eq("user_id", self._user_id).execute()
        except Exception:
            pass

        return DatasetPreprocessResponse(
            dataset_id=str(dataset_id),
            dataset_name=dataset_name,
            records_processed=len(X),
            columns_used=config["columns_used"],
            columns_excluded=config["columns_excluded"],
            missing_values_handled=config["missing_values_handled"],
            preprocessing_summary={
                "num_samples": len(X),
                "num_features": config["num_features"],
                "feature_columns": config["columns_used"],
                "imputation_statistics": config["imputation"],
                "country_categories": config["country_categories"],
                "target_positive_cases": int((y == 1).sum()) if y is not None else 0,
            },
            processing_status="preprocessed",
        )
