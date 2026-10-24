"""
Dataset Inspection Service.

Provides read-only, authenticated inspection of a dataset across the
full processing pipeline:

  • get_summary()          – Aggregates metadata + per-stage summaries
  • get_processed_preview()– Returns limited cleaned + feature-engineered rows
  • get_features()         – Returns feature catalog with availability metadata
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from fastapi import HTTPException, status

from app.schemas.dataset import (
    DatasetFeaturesResponse,
    DatasetProcessedPreviewResponse,
    DatasetSummaryResponse,
    FeatureMetadataItem,
)
from app.services.dataset_service import DatasetService
from app.services.feature_engineering_service import FeatureEngineeringService
from app.supabase_client import supabase_admin

DATASETS_TABLE = "datasets"
INVOICES_TABLE = "invoices"

# Disk paths written by the pipeline services
_UPLOADS = os.path.join(os.getcwd(), "uploads")
CLEANED_DIR = os.path.join(_UPLOADS, "cleaned")
PREPROCESSED_DIR = os.path.join(_UPLOADS, "preprocessed")
ENGINEERED_DIR = os.path.join(_UPLOADS, "engineered")


# ---------------------------------------------------------------------------
# Feature catalog definition
# All 10 engineered features + key base features shipped with every dataset
# ---------------------------------------------------------------------------
FEATURE_CATALOG: List[Dict[str, Any]] = [
    # ── Engineered features ─────────────────────────────────────────────────
    {
        "feature_name": "days_to_due",
        "description": "Number of days from invoice date to payment due date.",
        "data_type": "integer",
        "used_for_ml": True,
        "requires": ["invoice_date", "due_date"],
    },
    {
        "feature_name": "invoice_month",
        "description": "Calendar month of the invoice issue date (1 = Jan … 12 = Dec).",
        "data_type": "integer",
        "used_for_ml": True,
        "requires": ["invoice_date"],
    },
    {
        "feature_name": "invoice_weekday",
        "description": "Day-of-week of the invoice issue date (0 = Monday … 6 = Sunday).",
        "data_type": "integer",
        "used_for_ml": True,
        "requires": ["invoice_date"],
    },
    {
        "feature_name": "paperless_flag",
        "description": "Binary indicator: 1 if the invoice is delivered via paperless billing, else 0.",
        "data_type": "integer (binary)",
        "used_for_ml": True,
        "requires": ["paperless_bill"],
    },
    {
        "feature_name": "disputed_flag",
        "description": "Binary indicator: 1 if the invoice was disputed by the customer, else 0.",
        "data_type": "integer (binary)",
        "used_for_ml": True,
        "requires": ["disputed"],
    },
    {
        "feature_name": "invoice_amount_bucket",
        "description": "Categorical amount tier: low (< 1 000), medium (< 5 000), high (< 10 000), very_high (≥ 10 000).",
        "data_type": "string (categorical)",
        "used_for_ml": True,
        "requires": ["invoice_amount"],
    },
    {
        "feature_name": "customer_avg_dayslate",
        "description": "User-scoped historical mean days-late for the customer, calculated from invoices prior to the current invoice date (point-in-time safe).",
        "data_type": "float",
        "used_for_ml": True,
        "requires": ["customer_id", "invoice_date", "days_late"],
    },
    {
        "feature_name": "customer_dispute_rate",
        "description": "User-scoped historical dispute rate for the customer (fraction of disputed invoices) prior to current invoice date.",
        "data_type": "float",
        "used_for_ml": True,
        "requires": ["customer_id", "invoice_date", "disputed"],
    },
    {
        "feature_name": "customer_risk_drift",
        "description": "Difference between the customer's recent mean days-late (last 3 invoices) and long-term mean, indicating worsening or improving payment behavior.",
        "data_type": "float",
        "used_for_ml": True,
        "requires": ["customer_id", "invoice_date", "days_late"],
    },
    {
        "feature_name": "country_avg_dayslate",
        "description": "User-scoped historical mean days-late aggregated at country level, computed from invoices prior to the current invoice date.",
        "data_type": "float",
        "used_for_ml": True,
        "requires": ["country_code", "invoice_date", "days_late"],
    },
    # ── Base / cleaned fields used directly by the model ─────────────────────
    {
        "feature_name": "invoice_amount",
        "description": "Numeric invoice amount after cleaning and validation.",
        "data_type": "float",
        "used_for_ml": True,
        "requires": ["invoice_amount"],
    },
    {
        "feature_name": "payment_term_days",
        "description": "Number of days between invoice date and due date (payment window).",
        "data_type": "integer",
        "used_for_ml": True,
        "requires": ["invoice_date", "due_date"],
    },
]


def _load_json(path: str) -> Optional[Dict[str, Any]]:
    """Return parsed JSON from *path*, or None if the file is absent/unreadable."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _safe_val(val: Any) -> Any:
    """Ensure a value is JSON-serialisable (convert NaN / Timestamp to safe types)."""
    if hasattr(val, "isoformat"):
        return val.isoformat()
    try:
        if pd.isna(val):
            return None
    except Exception:
        pass
    return val


class DatasetInspectionService:
    """
    Read-only inspection service scoped to the authenticated user.
    Raises HTTP 404 or 400 on error; never exposes other users' data.
    """

    def __init__(self, user_id: str) -> None:
        self._user_id = str(user_id)
        self._sb = supabase_admin

    # ------------------------------------------------------------------ #
    # Internal helpers                                                      #
    # ------------------------------------------------------------------ #

    def _verify_dataset(self, dataset_id: str):
        """Return dataset metadata or raise 404."""
        svc = DatasetService(self._user_id)
        dataset = svc.get_by_id(dataset_id)
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found or access denied.",
            )
        return dataset

    def _fetch_invoices(self, dataset_id: str) -> List[Dict[str, Any]]:
        """Load all invoice rows for this dataset + user."""
        try:
            resp = (
                self._sb.table(INVOICES_TABLE)
                .select("*")
                .eq("dataset_id", str(dataset_id))
                .eq("user_id", self._user_id)
                .execute()
            )
            return resp.data if resp and resp.data else []
        except Exception:
            return []

    def _dataset_name(self, dataset) -> str:
        if hasattr(dataset, "original_filename") and dataset.original_filename:
            import os as _os
            return _os.path.splitext(dataset.original_filename)[0]
        return getattr(dataset, "filename", "dataset")

    def _load_cleaning_summary(self, dataset_id: str) -> Optional[Dict]:
        path = os.path.join(CLEANED_DIR, self._user_id, f"{dataset_id}_cleaned.json")
        return _load_json(path)

    def _load_preprocessing_summary(self, dataset_id: str) -> Optional[Dict]:
        path = os.path.join(PREPROCESSED_DIR, self._user_id, f"{dataset_id}_config.json")
        data = _load_json(path)
        if data is None:
            return None
        # Flatten the nested config for a clean API response
        cfg = data.get("config", {})
        return {
            "records_processed": data.get("sample_shape", [None])[0],
            "num_features": cfg.get("num_features"),
            "columns_used": cfg.get("columns_used", []),
            "columns_excluded": cfg.get("columns_excluded", []),
            "missing_values_handled": cfg.get("missing_values_handled"),
            "country_categories": cfg.get("country_categories", []),
            "target_distribution": data.get("target_distribution", {}),
        }

    def _load_feature_engineering_summary(self, dataset_id: str) -> Optional[Dict]:
        path = os.path.join(ENGINEERED_DIR, self._user_id, f"{dataset_id}_features.json")
        data = _load_json(path)
        if data is None:
            return None
        return {
            "records_processed": data.get("records_processed"),
            "features_created": data.get("features_created", []),
            "unavailable_features": data.get("unavailable_features", []),
            "feature_summary": data.get("feature_summary", {}),
        }

    # ------------------------------------------------------------------ #
    # Public API                                                            #
    # ------------------------------------------------------------------ #

    def get_summary(self, dataset_id: str) -> DatasetSummaryResponse:
        """
        Aggregate dataset metadata with cleaning, preprocessing, and
        feature-engineering summaries from persisted JSON files.
        """
        dataset = self._verify_dataset(dataset_id)
        name = self._dataset_name(dataset)

        # Prefer total_records; fall back to row_count
        total = (
            getattr(dataset, "total_records", None)
            or getattr(dataset, "row_count", None)
            or 0
        )

        # Prefer the fine-grained processing_status stored by the pipeline services
        # (e.g. "cleaned", "preprocessed", "feature_engineered") over the coarser
        # "status" field which collapses multiple stages to "ready".
        proc_status = (
            getattr(dataset, "processing_status", None)
            or getattr(dataset, "status", "uploaded")
        )

        return DatasetSummaryResponse(
            dataset_id=str(dataset_id),
            dataset_name=name,
            total_records=total,
            processing_status=proc_status,
            cleaning_summary=self._load_cleaning_summary(dataset_id),
            preprocessing_summary=self._load_preprocessing_summary(dataset_id),
            feature_engineering_summary=self._load_feature_engineering_summary(dataset_id),
        )

    def get_processed_preview(
        self, dataset_id: str, limit: int = 20
    ) -> DatasetProcessedPreviewResponse:
        """
        Return up to *limit* records that include cleaned invoice fields
        plus feature-engineered columns if feature engineering has been run.
        Falls back to cleaned records only when FE data is not available.
        """
        dataset = self._verify_dataset(dataset_id)
        name = self._dataset_name(dataset)

        raw = self._fetch_invoices(dataset_id)
        if not raw:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No invoice records found for this dataset.",
            )

        df = pd.DataFrame(raw)
        total_records = len(df)

        # Try to apply feature engineering if columns are present
        fe_summary = self._load_feature_engineering_summary(dataset_id)
        if fe_summary and fe_summary.get("features_created"):
            try:
                fe_svc = FeatureEngineeringService(user_id=self._user_id)
                history_resp = (
                    self._sb.table(INVOICES_TABLE)
                    .select("*")
                    .eq("user_id", self._user_id)
                    .execute()
                )
                hist_records = history_resp.data if history_resp and history_resp.data else []
                history_df = pd.DataFrame(hist_records) if hist_records else pd.DataFrame()
                engineered_df, _, _, _ = fe_svc.engineer(df=df, history_df=history_df)
                df = engineered_df
            except Exception:
                pass  # Fallback: use cleaned records as-is

        preview_df = df.head(limit)

        # Serialise to plain dicts, converting non-JSON types
        records = []
        for row in preview_df.to_dict(orient="records"):
            records.append({k: _safe_val(v) for k, v in row.items()})

        return DatasetProcessedPreviewResponse(
            dataset_id=str(dataset_id),
            dataset_name=name,
            total_records=total_records,
            preview_count=len(records),
            records=records,
        )

    def get_features(self, dataset_id: str) -> DatasetFeaturesResponse:
        """
        Return the full feature catalog enriched with availability status
        derived from the feature-engineering metadata persisted on disk.
        When no FE run has been completed the status is derived from the
        presence of required columns in the actual invoice records.
        """
        dataset = self._verify_dataset(dataset_id)
        name = self._dataset_name(dataset)

        # Determine actually available columns from a sample of invoice records
        raw = self._fetch_invoices(dataset_id)
        available_cols: set = set()
        if raw:
            sample_df = pd.DataFrame(raw[:5])
            available_cols = set(sample_df.columns)
            # Also treat computed cleaning columns as present
            if "days_late" not in available_cols and "settled_date" in available_cols and "due_date" in available_cols:
                available_cols.add("days_late")

        # Load persisted FE results for richer unavailable reasons
        fe_summary = self._load_feature_engineering_summary(dataset_id)
        features_created_set: set = set()
        unavail_reason_map: Dict[str, str] = {}
        if fe_summary:
            features_created_set = set(fe_summary.get("features_created", []))
            for item in fe_summary.get("unavailable_features", []):
                unavail_reason_map[item.get("feature", "")] = item.get("reason", "")

        items: List[FeatureMetadataItem] = []
        for entry in FEATURE_CATALOG:
            fname = entry["feature_name"]
            requires = entry.get("requires", [])

            # Determine status
            if features_created_set:
                # Trust the stored FE run result
                if fname in features_created_set:
                    feat_status = "available"
                    reason = None
                elif fname in unavail_reason_map:
                    feat_status = "unavailable"
                    reason = unavail_reason_map[fname]
                else:
                    # Base/cleaning columns not produced by FE but present in data
                    missing = [c for c in requires if c not in available_cols]
                    feat_status = "unavailable" if missing else "available"
                    reason = f"Missing columns: {missing}" if missing else None
            else:
                # No FE run yet – derive from column presence
                missing = [c for c in requires if c not in available_cols]
                feat_status = "unavailable" if missing else "available"
                reason = (
                    f"Feature engineering not yet run. Missing columns: {missing}"
                    if missing
                    else "Feature engineering not yet run (columns are present)."
                )

            items.append(
                FeatureMetadataItem(
                    feature_name=fname,
                    description=entry["description"],
                    data_type=entry["data_type"],
                    status=feat_status,
                    used_for_ml=entry["used_for_ml"],
                    unavailable_reason=reason,
                )
            )

        avail_count = sum(1 for i in items if i.status == "available")
        unavail_count = len(items) - avail_count

        return DatasetFeaturesResponse(
            dataset_id=str(dataset_id),
            dataset_name=name,
            total_features=len(items),
            available_features=avail_count,
            unavailable_features=unavail_count,
            features=items,
        )
