"""
Training service.

Trains a Random Forest classifier for payment-risk prediction,
evaluates it on a held-out test set, and persists:
  * the fitted model          -> ml_models/<user_id>/<dataset_id>_<model_id>_v<n>.joblib
  * the sklearn pipeline      -> ml_models/<user_id>/<dataset_id>_<model_id>_v<n>_pipeline.joblib
  * a JSON feature manifest   -> ml_models/<user_id>/<dataset_id>_<model_id>_v<n>_features.json

Model metadata is also written to the ``model_metadata`` Supabase table.

Isolation guarantees
--------------------
* Files are stored under ``ml_models/<user_id>/`` — never accessible to
  another user's path.
* Supabase writes always carry ``user_id`` so RLS policies enforce
  row-level isolation.
* ``dataset_id`` ownership is verified before any data is loaded.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from fastapi import HTTPException, status
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

from app.schemas.model import TrainModelResponse
from app.services.dataset_service import DatasetService
from app.services.training_data_service import TrainingDataService, TARGET_COLUMN
from app.supabase_client import supabase_admin

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL_METADATA_TABLE = "model_metadata"
DATASETS_TABLE = "datasets"

ML_MODELS_DIR = os.path.join(os.getcwd(), "ml_models")

_DEFAULT_HYPERPARAMS: Dict[str, Any] = {
    "n_estimators": 100,
    "max_depth": None,
    "min_samples_split": 2,
    "min_samples_leaf": 1,
    "random_state": 42,
    "class_weight": "balanced",   # handles imbalanced payment datasets
    "n_jobs": -1,
}

_TEST_SIZE = 0.20
_RANDOM_STATE = 42


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class TrainingService:
    """
    Orchestrates end-to-end model training scoped strictly to the
    authenticated user.  No cross-user data is ever read or written.
    """

    def __init__(self, user_id: str) -> None:
        self._user_id = str(user_id)
        self._sb = supabase_admin

    # ------------------------------------------------------------------ #
    # Public entry point                                                   #
    # ------------------------------------------------------------------ #

    def train(self, dataset_id: str) -> TrainModelResponse:
        """
        Full training pipeline:

        1.  Verify dataset ownership.
        2.  Load settled invoice records and rebuild the preprocessing pipeline.
        3.  Stratified 80/20 train/test split.
        4.  Fit RandomForestClassifier.
        5.  Evaluate: accuracy, precision, recall, F1, ROC-AUC.
        6.  Persist model + pipeline + feature list (user/dataset-scoped paths).
        7.  Write metadata row to ``model_metadata`` table.
        8.  Update dataset processing_status.
        9.  Return TrainModelResponse.
        """
        # 1. Verify ownership
        dataset_svc = DatasetService(self._user_id)
        dataset = dataset_svc.get_by_id(dataset_id)
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found or access denied.",
            )

        dataset_name = self._dataset_name(dataset)

        # 2. Build feature matrix reusing TrainingDataService helpers
        X, y, feature_names, pipeline = self._load_and_prepare(dataset_id)

        if len(X) < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Only {len(X)} usable training records found. "
                    "At least 10 settled invoices with a known payment outcome are required."
                ),
            )

        # 3. Stratified 80/20 split
        stratify = y if y.nunique() > 1 else None
        X_train, X_test, y_train, y_test = train_test_split(
            X, y,
            test_size=_TEST_SIZE,
            random_state=_RANDOM_STATE,
            stratify=stratify,
        )

        # 4. Train RandomForestClassifier
        clf = RandomForestClassifier(**_DEFAULT_HYPERPARAMS)
        clf.fit(X_train, y_train)

        # 5. Evaluate
        metrics = self._evaluate(clf, X_test, y_test)

        # 6. Persist artefacts (user + dataset scoped)
        model_id = str(uuid.uuid4())
        model_version = self._next_version(dataset_id)
        model_path, pipe_path, feat_path = self._save_artefacts(
            clf, pipeline, feature_names, dataset_id, model_id, model_version
        )

        # 7. Write metadata to Supabase
        now = datetime.now(tz=timezone.utc).isoformat()
        self._write_metadata(
            model_id=model_id,
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            model_version=model_version,
            feature_names=feature_names,
            metrics=metrics,
            model_path=model_path,
            pipeline_path=pipe_path,
            feature_list_path=feat_path,
            training_records=len(X_train),
            test_records=len(X_test),
            now=now,
        )

        # 8. Update dataset status
        self._update_dataset_status(dataset_id, now)

        # 9. Return response
        return TrainModelResponse(
            model_id=model_id,
            model_name=f"{dataset_name}_rf_v{model_version}",
            model_version=model_version,
            dataset_id=str(dataset_id),
            dataset_name=dataset_name,
            model_type="RandomForestClassifier",
            training_records=len(X_train),
            test_records=len(X_test),
            num_features=len(feature_names),
            feature_names=feature_names,
            accuracy=metrics["accuracy"],
            precision=metrics["precision"],
            recall=metrics["recall"],
            f1_score=metrics["f1_score"],
            roc_auc=metrics["roc_auc"],
            confusion_matrix=metrics["confusion_matrix"],
            model_path=model_path,
            pipeline_path=pipe_path,
            feature_list_path=feat_path,
            processing_status="model_trained",
        )

    # ------------------------------------------------------------------ #
    # Step 2: load + prepare                                               #
    # ------------------------------------------------------------------ #

    def _load_and_prepare(
        self, dataset_id: str
    ) -> Tuple[np.ndarray, pd.Series, List[str], Any]:
        """
        Reuse TrainingDataService helpers to load settled invoices,
        extract the target, derive temporal features, and fit the
        sklearn ColumnTransformer pipeline.

        Returns (X_array, y_series, feature_names, fitted_pipeline).
        """
        tds = TrainingDataService(self._user_id)

        # Load settled records
        raw = tds._fetch_settled_invoices(dataset_id)
        if not raw:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "No settled invoice records found. "
                    "Run /prepare-training-data before /train."
                ),
            )

        df = pd.DataFrame(raw)

        # Extract target — drops undeterminable rows
        df, y = tds._extract_target(df)
        if df.empty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "No records with a determinable 'is_late' target remain. "
                    "Ensure the dataset has been cleaned first."
                ),
            )

        # Derive temporal features (graceful fallback for missing FE columns)
        df = tds._derive_features(df)

        # Select columns
        numeric_cols, bool_cols, categorical_cols, _ = tds._select_columns(df)
        if not (numeric_cols + bool_cols + categorical_cols):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "No usable feature columns after exclusions. "
                    "Run /feature-engineering then /prepare-training-data first."
                ),
            )

        # Build + fit the sklearn pipeline on all available data
        X_raw = df[numeric_cols + bool_cols + categorical_cols].copy()
        pipeline, _, _ = tds._build_pipeline(X_raw, numeric_cols, bool_cols, categorical_cols)
        X_array = pipeline.fit_transform(X_raw)

        # Extract final feature names (post one-hot encoding)
        feature_names = tds._get_feature_names(pipeline, numeric_cols, bool_cols, categorical_cols)

        return X_array, y, feature_names, pipeline

    # ------------------------------------------------------------------ #
    # Step 5: evaluate                                                     #
    # ------------------------------------------------------------------ #

    def _evaluate(self, clf, X_test: np.ndarray, y_test: pd.Series) -> Dict[str, Any]:
        """Compute all required classification metrics on the held-out test set."""
        y_pred = clf.predict(X_test)

        # ROC-AUC requires probability estimates
        try:
            y_prob = clf.predict_proba(X_test)[:, 1]
            roc_auc = float(roc_auc_score(y_test, y_prob))
        except Exception:
            roc_auc = 0.0

        cm = confusion_matrix(y_test, y_pred).tolist()

        return {
            "accuracy": round(float(accuracy_score(y_test, y_pred)), 6),
            "precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 6),
            "recall": round(float(recall_score(y_test, y_pred, zero_division=0)), 6),
            "f1_score": round(float(f1_score(y_test, y_pred, zero_division=0)), 6),
            "roc_auc": round(roc_auc, 6),
            "confusion_matrix": cm,
        }

    # ------------------------------------------------------------------ #
    # Step 6: persist artefacts                                            #
    # ------------------------------------------------------------------ #

    def _user_model_dir(self) -> str:
        """Return (and create) a user-scoped directory inside ml_models/."""
        path = os.path.join(ML_MODELS_DIR, self._user_id)
        os.makedirs(path, exist_ok=True)
        return path

    def _save_artefacts(
        self,
        clf: RandomForestClassifier,
        pipeline: Any,
        feature_names: List[str],
        dataset_id: str,
        model_id: str,
        version: str,
    ) -> Tuple[str, str, str]:
        """
        Save model, pipeline, and feature list to user/dataset-scoped paths.
        Uses model_id in the filename to guarantee uniqueness — never
        overwrites a prior version or another user's file.
        """
        model_dir = self._user_model_dir()
        stem = f"{dataset_id}_{model_id}_v{version}"

        model_path = os.path.join(model_dir, f"{stem}.joblib")
        pipe_path = os.path.join(model_dir, f"{stem}_pipeline.joblib")
        feat_path = os.path.join(model_dir, f"{stem}_features.json")

        joblib.dump(clf, model_path)
        joblib.dump(pipeline, pipe_path)

        with open(feat_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "model_id": model_id,
                    "dataset_id": str(dataset_id),
                    "user_id": self._user_id,
                    "version": version,
                    "feature_names": feature_names,
                    "num_features": len(feature_names),
                },
                f,
                indent=2,
            )

        return model_path, pipe_path, feat_path

    # ------------------------------------------------------------------ #
    # Step 7: metadata DB write                                            #
    # ------------------------------------------------------------------ #

    def _write_metadata(
        self,
        model_id: str,
        dataset_id: str,
        dataset_name: str,
        model_version: str,
        feature_names: List[str],
        metrics: Dict[str, Any],
        model_path: str,
        pipeline_path: str,
        feature_list_path: str,
        training_records: int,
        test_records: int,
        now: str,
    ) -> None:
        """Insert a row into the model_metadata table."""
        row = {
            "id": model_id,
            "user_id": self._user_id,
            "dataset_id": str(dataset_id),
            "dataset_name": dataset_name,
            "model_name": f"{dataset_name}_rf_v{model_version}",
            "model_type": "RandomForestClassifier",
            "model_version": model_version,
            "status": "ready",
            "processing_status": "model_trained",
            "storage_path": model_path,
            "pipeline_path": pipeline_path,
            "feature_list_path": feature_list_path,
            "feature_names": feature_names,
            "num_features": len(feature_names),
            "training_records": training_records,
            "test_records": test_records,
            "hyperparams": _DEFAULT_HYPERPARAMS,
            "accuracy": metrics["accuracy"],
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "f1_score": metrics["f1_score"],
            "roc_auc": metrics["roc_auc"],
            "confusion_matrix": metrics["confusion_matrix"],
            "created_at": now,
            "updated_at": now,
        }
        try:
            self._sb.table(MODEL_METADATA_TABLE).insert(row).execute()
        except Exception:
            # Fallback: minimal row in case some columns don't exist yet in the table
            minimal = {
                "id": model_id,
                "user_id": self._user_id,
                "dataset_id": str(dataset_id),
                "model_version": model_version,
                "status": "ready",
                "storage_path": model_path,
                "created_at": now,
                "updated_at": now,
            }
            try:
                self._sb.table(MODEL_METADATA_TABLE).insert(minimal).execute()
            except Exception:
                pass  # Don't block the response if the table schema is not ready

    # ------------------------------------------------------------------ #
    # Step 8: update dataset status                                        #
    # ------------------------------------------------------------------ #

    def _update_dataset_status(self, dataset_id: str, now: str) -> None:
        try:
            self._sb.table(DATASETS_TABLE).update({
                "processing_status": "model_trained",
                "updated_at": now,
            }).eq("id", str(dataset_id)).eq("user_id", self._user_id).execute()
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _dataset_name(self, dataset) -> str:
        if hasattr(dataset, "original_filename") and dataset.original_filename:
            return os.path.splitext(dataset.original_filename)[0]
        return getattr(dataset, "filename", "dataset")

    def _next_version(self, dataset_id: str) -> str:
        """
        Derive the next sequential version string (1, 2, …) by counting
        existing model .joblib files for this user + dataset in ml_models/.
        Excludes *_pipeline.joblib files from the count.
        """
        model_dir = os.path.join(ML_MODELS_DIR, self._user_id)
        if not os.path.isdir(model_dir):
            return "1"
        prefix = str(dataset_id)
        existing = [
            f for f in os.listdir(model_dir)
            if f.startswith(prefix) and f.endswith(".joblib") and "_pipeline" not in f
        ]
        return str(len(existing) + 1)
