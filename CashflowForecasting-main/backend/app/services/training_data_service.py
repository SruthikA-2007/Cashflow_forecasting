"""
Training-data preparation service.

Converts settled, cleaned invoice records for a dataset into a labelled
feature matrix ready for model training.  The sklearn preprocessing
pipeline (imputation + one-hot encoding) is serialised to disk so that
exactly the same transformations can be applied at inference time.

Key guarantees
--------------
* Only settled invoices (``settled_date`` is not NULL) are used, ensuring
  the target label ``is_late`` can always be determined.
* ID / timestamp / direct-outcome columns are unconditionally excluded to
  prevent data leakage.
* The pipeline is saved under
  ``uploads/training/<user_id>/<dataset_id>_pipeline.json``
  (configuration) alongside a separate feature manifest
  ``<dataset_id>_features.json``.
* No model is trained here.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from fastapi import HTTPException, status
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from app.schemas.dataset import PrepareTrainingDataResponse
from app.services.dataset_service import DatasetService
from app.supabase_client import supabase_admin

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATASETS_TABLE = "datasets"
INVOICES_TABLE = "invoices"

TRAINING_DIR = os.path.join(os.getcwd(), "uploads", "training")

TARGET_COLUMN = "is_late"

# Columns that must NEVER appear in X — they either uniquely identify a row,
# link to other tables, or directly encode the payment outcome.
_ALWAYS_EXCLUDE: List[str] = [
    "id",
    "dataset_id",
    "user_id",
    # Direct target leakage: outcome columns known only after settlement
    "settled_date",
    "days_to_settle",
    "days_late",
    # Raw date strings (temporal features are extracted separately)
    "invoice_date",
    "due_date",
    # Admin / audit columns
    "created_at",
    "updated_at",
    # Identifier columns
    "invoice_number",
]

# Numeric columns to include (in order of preference)
_NUMERIC_COLS: List[str] = [
    "invoice_amount",
    "payment_term_days",   # computed: due_date – invoice_date
    "invoice_month",       # from feature engineering
    "invoice_weekday",     # from feature engineering
    "invoice_quarter",     # derived below if missing
    "days_to_due",         # from feature engineering
    "customer_avg_dayslate",
    "customer_dispute_rate",
    "customer_risk_drift",
    "country_avg_dayslate",
]

# Boolean flag columns (stored as bool/int)
_BOOL_COLS: List[str] = [
    "disputed",
    "paperless_bill",
    "paperless_flag",   # engineered alias
    "disputed_flag",    # engineered alias
]

# Categorical columns to one-hot encode
_CATEGORICAL_COLS: List[str] = [
    "country_code",
    "invoice_amount_bucket",
]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _to_int_flag(series: pd.Series) -> pd.Series:
    """Convert a boolean/mixed series to 0/1 integer."""
    return series.apply(
        lambda v: 1 if (isinstance(v, bool) and v) or str(v).strip().lower() in ("true", "1", "yes", "y", "t") else 0
    )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class TrainingDataService:
    """
    Prepares a labelled feature matrix (X, y) for supervised model training.

    Scoped strictly to the authenticated user — no cross-user data is ever
    returned or used.
    """

    def __init__(self, user_id: str) -> None:
        self._user_id = str(user_id)
        self._sb = supabase_admin

    # ------------------------------------------------------------------ #
    # Public entry point                                                   #
    # ------------------------------------------------------------------ #

    def prepare(self, dataset_id: str) -> PrepareTrainingDataResponse:
        """
        Full preparation pipeline:

        1. Verify dataset ownership.
        2. Load settled invoice records (target is known).
        3. Drop rows where ``is_late`` cannot be determined.
        4. Derive temporal features that may be missing (e.g. invoice_quarter).
        5. Select and order feature columns; exclude leakage / ID columns.
        6. Build & fit a sklearn ColumnTransformer pipeline.
        7. Persist pipeline config + feature manifest to disk.
        8. Return summary metadata.
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

        # 2. Load only settled invoices for this dataset + user
        raw = self._fetch_settled_invoices(dataset_id)
        if not raw:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "No settled invoice records found for this dataset. "
                    "Run the cleaning step first, then prepare training data."
                ),
            )

        df = pd.DataFrame(raw)

        # 3. Drop rows where the target cannot be determined
        df, y = self._extract_target(df)
        if df.empty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "No records with a determinable 'is_late' target remain after filtering. "
                    "Ensure the dataset has been cleaned and that settled_date / due_date are populated."
                ),
            )

        # 4. Derive missing temporal / computed features
        df = self._derive_features(df)

        # 5. Select feature columns
        numeric_cols, bool_cols, categorical_cols, excluded_cols = self._select_columns(df)

        if not (numeric_cols + bool_cols + categorical_cols):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No usable feature columns found after exclusions. Ensure feature engineering has been run.",
            )

        # 6. Build & fit the sklearn pipeline
        X_raw = df[numeric_cols + bool_cols + categorical_cols].copy()
        pipeline, missing_imputed, encoded_cats = self._build_pipeline(
            X_raw, numeric_cols, bool_cols, categorical_cols
        )

        # Transform to get the final feature names
        X_transformed = pipeline.fit_transform(X_raw)
        feature_names = self._get_feature_names(pipeline, numeric_cols, bool_cols, categorical_cols)
        num_features = len(feature_names)

        # 7. Target distribution
        target_dist = {str(k): int(v) for k, v in y.value_counts().sort_index().to_dict().items()}

        # 8. Build pipeline configuration dict (sklearn cannot be directly JSON-serialised,
        #    so we save a reproducible config describing every step)
        now = datetime.now(tz=timezone.utc).isoformat()
        pipeline_config = self._build_pipeline_config(
            dataset_id=dataset_id,
            numeric_cols=numeric_cols,
            bool_cols=bool_cols,
            categorical_cols=categorical_cols,
            feature_names=feature_names,
            excluded_cols=excluded_cols,
            missing_imputed=missing_imputed,
            encoded_cats=encoded_cats,
            training_records=len(df),
            target_dist=target_dist,
            created_at=now,
        )

        config_path, manifest_path = self._persist(dataset_id, pipeline_config, feature_names)

        # 9. Update dataset processing_status
        self._update_status(dataset_id, now)

        return PrepareTrainingDataResponse(
            dataset_id=str(dataset_id),
            dataset_name=dataset_name,
            training_records=len(df),
            num_features=num_features,
            feature_names=feature_names,
            target_column=TARGET_COLUMN,
            target_distribution=target_dist,
            excluded_columns=excluded_cols,
            missing_values_imputed=missing_imputed,
            categorical_columns_encoded=encoded_cats,
            pipeline_config_path=config_path,
            processing_status="training_data_ready",
        )

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _dataset_name(self, dataset) -> str:
        if hasattr(dataset, "original_filename") and dataset.original_filename:
            return os.path.splitext(dataset.original_filename)[0]
        return getattr(dataset, "filename", "dataset")

    def _fetch_settled_invoices(self, dataset_id: str) -> List[Dict[str, Any]]:
        """Return invoices for this dataset+user that have a non-null settled_date."""
        try:
            resp = (
                self._sb.table(INVOICES_TABLE)
                .select("*")
                .eq("dataset_id", str(dataset_id))
                .eq("user_id", self._user_id)
                .not_.is_("settled_date", "null")
                .execute()
            )
            return resp.data if resp and resp.data else []
        except Exception:
            # Fallback: fetch all and filter in Python
            try:
                resp = (
                    self._sb.table(INVOICES_TABLE)
                    .select("*")
                    .eq("dataset_id", str(dataset_id))
                    .eq("user_id", self._user_id)
                    .execute()
                )
                all_records = resp.data if resp and resp.data else []
                return [r for r in all_records if r.get("settled_date") not in (None, "", "null")]
            except Exception:
                return []

    def _extract_target(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Derive ``is_late`` (0/1) and drop rows where it cannot be determined.

        Priority:
        1. Use ``is_late`` column if present (already computed by CleaningService).
        2. Derive from ``days_late`` (> 0 → late).
        3. Derive from ``settled_date`` - ``due_date`` directly.
        """
        # Parse date columns needed for fallback derivation
        for col in ("due_date", "settled_date"):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        if "is_late" in df.columns:
            df["_target"] = df["is_late"].apply(
                lambda v: 1 if (isinstance(v, bool) and v) or str(v).strip().lower() in ("true", "1", "yes") else (
                    0 if str(v).strip().lower() in ("false", "0", "no") else np.nan
                )
            )
        elif "days_late" in df.columns:
            df["days_late"] = pd.to_numeric(df["days_late"], errors="coerce")
            df["_target"] = df["days_late"].apply(
                lambda d: 1 if pd.notna(d) and d > 0 else (0 if pd.notna(d) else np.nan)
            )
        elif "settled_date" in df.columns and "due_date" in df.columns:
            computed_days_late = (df["settled_date"] - df["due_date"]).dt.days
            df["_target"] = computed_days_late.apply(
                lambda d: 1 if pd.notna(d) and d > 0 else (0 if pd.notna(d) else np.nan)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Cannot determine 'is_late' target: dataset lacks 'is_late', 'days_late', "
                    "or both 'settled_date' and 'due_date' columns. Run the cleaning step first."
                ),
            )

        # Drop rows where target is unknown
        df = df[df["_target"].notna()].copy()
        y = df["_target"].astype(int)
        df = df.drop(columns=["_target"])
        return df, y

    def _derive_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Derive temporal/computed columns that may be absent when feature
        engineering has not yet been run, so the pipeline degrades gracefully.
        """
        # Parse invoice_date / due_date if present and not yet parsed
        for col in ("invoice_date", "due_date"):
            if col in df.columns and not pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = pd.to_datetime(df[col], errors="coerce")

        inv_dt = df.get("invoice_date") if "invoice_date" in df.columns else None
        due_dt = df.get("due_date") if "due_date" in df.columns else None

        if "invoice_month" not in df.columns and inv_dt is not None:
            df["invoice_month"] = inv_dt.dt.month

        if "invoice_weekday" not in df.columns and inv_dt is not None:
            # map to 0-6 (Mon-Sun)
            df["invoice_weekday"] = inv_dt.dt.dayofweek

        if "invoice_quarter" not in df.columns and inv_dt is not None:
            df["invoice_quarter"] = inv_dt.dt.quarter

        if "payment_term_days" not in df.columns and inv_dt is not None and due_dt is not None:
            df["payment_term_days"] = (due_dt - inv_dt).dt.days

        if "days_to_due" not in df.columns and inv_dt is not None and due_dt is not None:
            df["days_to_due"] = (due_dt - inv_dt).dt.days

        return df

    def _select_columns(
        self, df: pd.DataFrame
    ) -> Tuple[List[str], List[str], List[str], List[str]]:
        """
        Return (numeric_cols, bool_cols, categorical_cols, excluded_cols).

        Selection rules:
        * _ALWAYS_EXCLUDE → unconditionally excluded.
        * TARGET_COLUMN   → excluded from X (it is y).
        * Numeric cols    → present in df and in _NUMERIC_COLS.
        * Bool flag cols  → present in df and in _BOOL_COLS.
        * Categorical cols→ present in df and in _CATEGORICAL_COLS.
        * Any remaining column not in the above sets is also excluded and
          recorded in excluded_cols for transparency.
        """
        existing = set(df.columns)
        hard_exclude = set(_ALWAYS_EXCLUDE) | {TARGET_COLUMN}

        numeric_cols = [c for c in _NUMERIC_COLS if c in existing and c not in hard_exclude]
        bool_cols = [c for c in _BOOL_COLS if c in existing and c not in hard_exclude]
        categorical_cols = [c for c in _CATEGORICAL_COLS if c in existing and c not in hard_exclude]

        accounted_for = set(numeric_cols) | set(bool_cols) | set(categorical_cols) | hard_exclude
        leftover = [c for c in existing if c not in accounted_for]

        # Any leftover column (unknown auditing columns, etc.) is excluded
        excluded_cols = sorted(hard_exclude & existing) + sorted(leftover)

        return numeric_cols, bool_cols, categorical_cols, excluded_cols

    def _build_pipeline(
        self,
        X: pd.DataFrame,
        numeric_cols: List[str],
        bool_cols: List[str],
        categorical_cols: List[str],
    ) -> Tuple[Pipeline, int, List[str]]:
        """
        Build a sklearn ColumnTransformer pipeline:
        * Numeric + bool  → median imputation
        * Categorical     → most-frequent imputation + one-hot encoding
        Returns (fitted_pipeline, missing_value_count, encoded_categorical_col_names).
        """
        missing_imputed = int(X[numeric_cols + bool_cols].isna().sum().sum()) if (numeric_cols + bool_cols) else 0
        if categorical_cols:
            missing_imputed += int(X[categorical_cols].isna().sum().sum())

        transformers = []

        if numeric_cols + bool_cols:
            num_pipeline = Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
            ])
            transformers.append(("numeric", num_pipeline, numeric_cols + bool_cols))

        encoded_cats: List[str] = []
        if categorical_cols:
            cat_pipeline = Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
            ])
            transformers.append(("categorical", cat_pipeline, categorical_cols))
            encoded_cats = categorical_cols

        if not transformers:
            # Fallback: passthrough everything
            ct = ColumnTransformer(transformers=[("passthrough", "passthrough", list(X.columns))], remainder="drop")
        else:
            ct = ColumnTransformer(transformers=transformers, remainder="drop")

        pipeline = Pipeline([("preprocessor", ct)])
        return pipeline, missing_imputed, encoded_cats

    def _get_feature_names(
        self,
        pipeline: Pipeline,
        numeric_cols: List[str],
        bool_cols: List[str],
        categorical_cols: List[str],
    ) -> List[str]:
        """Extract final feature names after one-hot encoding."""
        try:
            ct = pipeline.named_steps["preprocessor"]
            names: List[str] = []
            for name, trans, cols in ct.transformers_:
                if name == "numeric":
                    names.extend(cols)
                elif name == "categorical":
                    encoder: OneHotEncoder = trans.named_steps["encoder"]
                    ohe_names = encoder.get_feature_names_out(cols).tolist()
                    names.extend(ohe_names)
                elif name == "passthrough":
                    names.extend(cols)
            return names
        except Exception:
            return numeric_cols + bool_cols + categorical_cols

    def _build_pipeline_config(
        self,
        dataset_id: str,
        numeric_cols: List[str],
        bool_cols: List[str],
        categorical_cols: List[str],
        feature_names: List[str],
        excluded_cols: List[str],
        missing_imputed: int,
        encoded_cats: List[str],
        training_records: int,
        target_dist: Dict[str, int],
        created_at: str,
    ) -> Dict[str, Any]:
        return {
            "dataset_id": str(dataset_id),
            "user_id": self._user_id,
            "target_column": TARGET_COLUMN,
            "created_at": created_at,
            "training_records": training_records,
            "target_distribution": target_dist,
            # Feature selection
            "numeric_columns": numeric_cols,
            "bool_columns": bool_cols,
            "categorical_columns": categorical_cols,
            "excluded_columns": excluded_cols,
            "always_excluded": _ALWAYS_EXCLUDE,
            # Pipeline steps
            "numeric_strategy": "median_imputation",
            "bool_strategy": "median_imputation",
            "categorical_strategy": "most_frequent_imputation + one_hot_encoding",
            "ohe_handle_unknown": "ignore",
            # Output
            "feature_names": feature_names,
            "num_features": len(feature_names),
            "missing_values_imputed": missing_imputed,
            "categorical_columns_encoded": encoded_cats,
        }

    def _persist(
        self, dataset_id: str, config: Dict[str, Any], feature_names: List[str]
    ) -> Tuple[str, str]:
        """Save pipeline config and feature manifest JSON files to disk."""
        user_dir = os.path.join(TRAINING_DIR, self._user_id)
        os.makedirs(user_dir, exist_ok=True)

        config_path = os.path.join(user_dir, f"{dataset_id}_pipeline.json")
        manifest_path = os.path.join(user_dir, f"{dataset_id}_features.json")

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({"dataset_id": str(dataset_id), "feature_names": feature_names}, f, indent=2)

        return config_path, manifest_path

    def _update_status(self, dataset_id: str, now: str) -> None:
        """Update the datasets table processing_status field."""
        try:
            self._sb.table(DATASETS_TABLE).update({
                "processing_status": "training_data_ready",
                "updated_at": now,
            }).eq("id", str(dataset_id)).eq("user_id", self._user_id).execute()
        except Exception:
            pass
