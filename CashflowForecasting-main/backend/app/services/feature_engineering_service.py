"""
Feature engineering service module.
Transforms cleaned invoice datasets into ML-ready engineered features.
Prevents data leakage by ensuring historical features are strictly computed from past records.
Gracefully records unavailable features when required columns are absent.
Designed for reuse across both batch dataset engineering and online prediction.
"""

import json
import os
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import Optional, Dict, List, Tuple, Any
from fastapi import HTTPException, status

from app.schemas.dataset import DatasetFeatureEngineeringResponse
from app.services.dataset_service import DatasetService
from app.supabase_client import supabase_admin

DATASETS_TABLE = "datasets"
INVOICES_TABLE = "invoices"
ENGINEERED_DIR = os.path.join(os.getcwd(), "uploads", "engineered")


def _get_amount_bucket(amount: Any) -> Optional[str]:
    """Helper to categorize invoice amounts into discrete buckets."""
    if pd.isna(amount) or amount is None:
        return None
    try:
        val = float(amount)
        if val < 1000:
            return "low"
        elif val < 5000:
            return "medium"
        elif val < 10000:
            return "high"
        else:
            return "very_high"
    except (ValueError, TypeError):
        return None


class FeatureEngineeringService:
    """
    Feature engineering service scoped strictly to the authenticated user.
    """

    def __init__(self, user_id: str) -> None:
        self._user_id = str(user_id)
        self._sb = supabase_admin

    def engineer_dataset(self, dataset_id: str) -> DatasetFeatureEngineeringResponse:
        """
        Executes feature engineering on invoice records for the specified dataset.
        Verifies ownership, loads current dataset invoices, retrieves user history,
        engineers features, saves metadata, and updates dataset status.
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
                detail="No cleaned invoice records found for this dataset to engineer features.",
            )

        df = pd.DataFrame(raw_records)

        # 3. Fetch all user historical invoice records to provide historical context without data leakage
        try:
            hist_response = (
                self._sb.table(INVOICES_TABLE)
                .select("*")
                .eq("user_id", self._user_id)
                .execute()
            )
            hist_records = hist_response.data if hist_response and hist_response.data else []
            history_df = pd.DataFrame(hist_records) if hist_records else pd.DataFrame()
        except Exception:
            history_df = pd.DataFrame()

        # 4. Generate features using reusable feature engineering logic
        engineered_df, features_created, unavailable_features, feature_summary = self.engineer(
            df=df, history_df=history_df
        )

        # 5. Save engineered feature configuration and summary metadata
        user_eng_dir = os.path.join(ENGINEERED_DIR, self._user_id)
        os.makedirs(user_eng_dir, exist_ok=True)
        config_path = os.path.join(user_eng_dir, f"{dataset_id}_features.json")

        now = datetime.now(tz=timezone.utc).isoformat()
        metadata = {
            "dataset_id": str(dataset_id),
            "user_id": self._user_id,
            "created_at": now,
            "records_processed": len(engineered_df),
            "features_created": features_created,
            "unavailable_features": unavailable_features,
            "feature_summary": feature_summary,
        }

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        # 6. Update dataset status to "feature_engineered"
        dataset_name = getattr(dataset, "filename", "dataset")
        if hasattr(dataset, "original_filename") and dataset.original_filename:
            dataset_name = os.path.splitext(dataset.original_filename)[0]

        try:
            self._sb.table(DATASETS_TABLE).update({
                "status": "ready",
                "processing_status": "feature_engineered",
                "updated_at": now,
            }).eq("id", str(dataset_id)).eq("user_id", self._user_id).execute()
        except Exception:
            pass

        return DatasetFeatureEngineeringResponse(
            dataset_id=str(dataset_id),
            dataset_name=dataset_name,
            records_processed=len(engineered_df),
            features_created=features_created,
            unavailable_features=unavailable_features,
            feature_summary=feature_summary,
            processing_status="feature_engineered",
        )

    def engineer(
        self, df: pd.DataFrame, history_df: Optional[pd.DataFrame] = None
    ) -> Tuple[pd.DataFrame, List[str], List[Dict[str, str]], Dict[str, Any]]:
        """
        Reusable feature engineering method.
        Transforms invoice DataFrame `df` into engineered feature DataFrame.
        Uses `history_df` (if provided) for point-in-time historical aggregations.

        Returns:
            - engineered_df: DataFrame with original + engineered feature columns
            - features_created: List of created feature names
            - unavailable_features: List of unavailable features with reasons
            - feature_summary: Dictionary of summary statistics
        """
        if df.empty:
            return df, [], [], {"error": "Input DataFrame is empty."}

        work_df = df.copy()
        features_created: List[str] = []
        unavailable_features: List[Dict[str, str]] = []
        summary_stats: Dict[str, Any] = {}

        # Standardize dates
        date_cols = ["invoice_date", "due_date", "settled_date"]
        for col in date_cols:
            if col in work_df.columns:
                work_df[col] = pd.to_datetime(work_df[col], errors="coerce")

        # -------------------------------------------------------------
        # Feature 1: days_to_due
        # -------------------------------------------------------------
        if "invoice_date" in work_df.columns and "due_date" in work_df.columns:
            has_valid_dates = (
                work_df["invoice_date"].notna() & work_df["due_date"].notna()
            ).any()
            if has_valid_dates:
                work_df["days_to_due"] = (
                    work_df["due_date"] - work_df["invoice_date"]
                ).dt.days
                features_created.append("days_to_due")
                summary_stats["days_to_due"] = {
                    "mean": float(work_df["days_to_due"].mean()) if work_df["days_to_due"].notna().any() else 0.0,
                    "median": float(work_df["days_to_due"].median()) if work_df["days_to_due"].notna().any() else 0.0,
                    "min": float(work_df["days_to_due"].min()) if work_df["days_to_due"].notna().any() else 0.0,
                    "max": float(work_df["days_to_due"].max()) if work_df["days_to_due"].notna().any() else 0.0,
                }
            else:
                unavailable_features.append({
                    "feature": "days_to_due",
                    "reason": "All 'invoice_date' or 'due_date' values are null or invalid.",
                })
        else:
            unavailable_features.append({
                "feature": "days_to_due",
                "reason": "Dataset lacks required 'invoice_date' or 'due_date' column.",
            })

        # -------------------------------------------------------------
        # Feature 2: invoice_month
        # -------------------------------------------------------------
        if "invoice_date" in work_df.columns and work_df["invoice_date"].notna().any():
            work_df["invoice_month"] = work_df["invoice_date"].dt.month
            features_created.append("invoice_month")
            summary_stats["invoice_month"] = {
                "unique_months": [int(m) for m in work_df["invoice_month"].dropna().unique()],
                "most_common": int(work_df["invoice_month"].mode().iloc[0]) if not work_df["invoice_month"].dropna().empty else None,
            }
        else:
            unavailable_features.append({
                "feature": "invoice_month",
                "reason": "Dataset lacks required 'invoice_date' column or valid date values.",
            })

        # -------------------------------------------------------------
        # Feature 3: invoice_weekday
        # -------------------------------------------------------------
        if "invoice_date" in work_df.columns and work_df["invoice_date"].notna().any():
            work_df["invoice_weekday"] = work_df["invoice_date"].dt.dayofweek
            features_created.append("invoice_weekday")
            summary_stats["invoice_weekday"] = {
                "unique_weekdays": [int(w) for w in work_df["invoice_weekday"].dropna().unique()],
                "most_common": int(work_df["invoice_weekday"].mode().iloc[0]) if not work_df["invoice_weekday"].dropna().empty else None,
            }
        else:
            unavailable_features.append({
                "feature": "invoice_weekday",
                "reason": "Dataset lacks required 'invoice_date' column or valid date values.",
            })

        # -------------------------------------------------------------
        # Feature 4: paperless_flag
        # -------------------------------------------------------------
        if "paperless_bill" in work_df.columns:
            work_df["paperless_flag"] = work_df["paperless_bill"].apply(
                lambda v: 1 if bool(v) and str(v).strip().lower() not in ["0", "false", "none", "nan", "<na>"] else 0
            )
            features_created.append("paperless_flag")
            summary_stats["paperless_flag"] = {
                "paperless_count": int(work_df["paperless_flag"].sum()),
                "paperless_ratio": float(work_df["paperless_flag"].mean()),
            }
        else:
            unavailable_features.append({
                "feature": "paperless_flag",
                "reason": "Dataset lacks required 'paperless_bill' column.",
            })

        # -------------------------------------------------------------
        # Feature 5: disputed_flag
        # -------------------------------------------------------------
        if "disputed" in work_df.columns:
            work_df["disputed_flag"] = work_df["disputed"].apply(
                lambda v: 1 if bool(v) and str(v).strip().lower() not in ["0", "false", "none", "nan", "<na>"] else 0
            )
            features_created.append("disputed_flag")
            summary_stats["disputed_flag"] = {
                "disputed_count": int(work_df["disputed_flag"].sum()),
                "dispute_ratio": float(work_df["disputed_flag"].mean()),
            }
        else:
            unavailable_features.append({
                "feature": "disputed_flag",
                "reason": "Dataset lacks required 'disputed' column.",
            })

        # -------------------------------------------------------------
        # Feature 6: invoice_amount_bucket
        # -------------------------------------------------------------
        if "invoice_amount" in work_df.columns and work_df["invoice_amount"].notna().any():
            work_df["invoice_amount_bucket"] = work_df["invoice_amount"].apply(_get_amount_bucket)
            features_created.append("invoice_amount_bucket")
            counts = work_df["invoice_amount_bucket"].value_counts().to_dict()
            summary_stats["invoice_amount_bucket"] = {str(k): int(v) for k, v in counts.items()}
        else:
            unavailable_features.append({
                "feature": "invoice_amount_bucket",
                "reason": "Dataset lacks required 'invoice_amount' column or valid numeric values.",
            })

        # -------------------------------------------------------------
        # Historical Context Preparation for Features 7, 8, 9, 10
        # -------------------------------------------------------------
        # Prepare historical DataFrame strictly belonging to user
        if history_df is not None and not history_df.empty:
            h_df = history_df.copy()
        else:
            h_df = work_df.copy()

        for col in date_cols:
            if col in h_df.columns:
                h_df[col] = pd.to_datetime(h_df[col], errors="coerce")

        if "days_late" not in h_df.columns and "settled_date" in h_df.columns and "due_date" in h_df.columns:
            h_df["days_late"] = (h_df["settled_date"] - h_df["due_date"]).dt.days

        has_cust_id = "customer_id" in work_df.columns and work_df["customer_id"].notna().any()
        has_hist_days_late = "days_late" in h_df.columns and h_df["days_late"].notna().any()
        has_country = "country_code" in work_df.columns and work_df["country_code"].notna().any()
        has_hist_disputed = "disputed" in h_df.columns

        # Pre-convert disputed in h_df
        if has_hist_disputed:
            h_df["_disputed_num"] = h_df["disputed"].apply(
                lambda v: 1 if bool(v) and str(v).strip().lower() not in ["0", "false", "none", "nan", "<na>"] else 0
            )

        # -------------------------------------------------------------
        # Feature 7: customer_avg_dayslate
        # -------------------------------------------------------------
        if has_cust_id and has_hist_days_late:
            cust_avg_list = []
            for idx, row in work_df.iterrows():
                cid = row.get("customer_id")
                inv_dt = row.get("invoice_date")
                if pd.isna(cid) or pd.isna(inv_dt):
                    cust_avg_list.append(0.0)
                    continue

                # Point-in-time historical filter (past invoices prior to current invoice_date)
                past_records = h_df[
                    (h_df["customer_id"] == cid)
                    & (h_df["invoice_date"] < inv_dt)
                    & (h_df["days_late"].notna())
                ]
                if not past_records.empty:
                    cust_avg_list.append(float(past_records["days_late"].mean()))
                else:
                    cust_avg_list.append(0.0)

            work_df["customer_avg_dayslate"] = cust_avg_list
            features_created.append("customer_avg_dayslate")
            summary_stats["customer_avg_dayslate"] = {
                "mean": float(work_df["customer_avg_dayslate"].mean()),
                "max": float(work_df["customer_avg_dayslate"].max()),
                "min": float(work_df["customer_avg_dayslate"].min()),
            }
        else:
            unavailable_features.append({
                "feature": "customer_avg_dayslate",
                "reason": "Dataset lacks required 'customer_id' column or user historical settlement data.",
            })

        # -------------------------------------------------------------
        # Feature 8: customer_dispute_rate
        # -------------------------------------------------------------
        if has_cust_id and has_hist_disputed:
            cust_disp_list = []
            for idx, row in work_df.iterrows():
                cid = row.get("customer_id")
                inv_dt = row.get("invoice_date")
                if pd.isna(cid) or pd.isna(inv_dt):
                    cust_disp_list.append(0.0)
                    continue

                past_records = h_df[
                    (h_df["customer_id"] == cid)
                    & (h_df["invoice_date"] < inv_dt)
                ]
                if not past_records.empty:
                    cust_disp_list.append(float(past_records["_disputed_num"].mean()))
                else:
                    cust_disp_list.append(0.0)

            work_df["customer_dispute_rate"] = cust_disp_list
            features_created.append("customer_dispute_rate")
            summary_stats["customer_dispute_rate"] = {
                "mean": float(work_df["customer_dispute_rate"].mean()),
                "max": float(work_df["customer_dispute_rate"].max()),
                "min": float(work_df["customer_dispute_rate"].min()),
            }
        else:
            unavailable_features.append({
                "feature": "customer_dispute_rate",
                "reason": "Dataset lacks required 'customer_id' or historical 'disputed' information.",
            })

        # -------------------------------------------------------------
        # Feature 9: customer_risk_drift
        # -------------------------------------------------------------
        if has_cust_id and has_hist_days_late:
            drift_list = []
            for idx, row in work_df.iterrows():
                cid = row.get("customer_id")
                inv_dt = row.get("invoice_date")
                if pd.isna(cid) or pd.isna(inv_dt):
                    drift_list.append(0.0)
                    continue

                past_records = h_df[
                    (h_df["customer_id"] == cid)
                    & (h_df["invoice_date"] < inv_dt)
                    & (h_df["days_late"].notna())
                ].sort_values("invoice_date")

                if len(past_records) >= 2:
                    recent_avg = past_records.tail(3)["days_late"].mean()
                    overall_avg = past_records["days_late"].mean()
                    drift_list.append(float(recent_avg - overall_avg))
                else:
                    drift_list.append(0.0)

            work_df["customer_risk_drift"] = drift_list
            features_created.append("customer_risk_drift")
            summary_stats["customer_risk_drift"] = {
                "mean": float(work_df["customer_risk_drift"].mean()),
                "max": float(work_df["customer_risk_drift"].max()),
                "min": float(work_df["customer_risk_drift"].min()),
            }
        else:
            unavailable_features.append({
                "feature": "customer_risk_drift",
                "reason": "Dataset lacks required 'customer_id' column or user historical settlement data.",
            })

        # -------------------------------------------------------------
        # Feature 10: country_avg_dayslate
        # -------------------------------------------------------------
        if has_country and has_hist_days_late:
            country_avg_list = []
            for idx, row in work_df.iterrows():
                code = row.get("country_code")
                inv_dt = row.get("invoice_date")
                if pd.isna(code) or pd.isna(inv_dt):
                    country_avg_list.append(0.0)
                    continue

                past_records = h_df[
                    (h_df["country_code"] == code)
                    & (h_df["invoice_date"] < inv_dt)
                    & (h_df["days_late"].notna())
                ]
                if not past_records.empty:
                    country_avg_list.append(float(past_records["days_late"].mean()))
                else:
                    country_avg_list.append(0.0)

            work_df["country_avg_dayslate"] = country_avg_list
            features_created.append("country_avg_dayslate")
            summary_stats["country_avg_dayslate"] = {
                "mean": float(work_df["country_avg_dayslate"].mean()),
                "max": float(work_df["country_avg_dayslate"].max()),
                "min": float(work_df["country_avg_dayslate"].min()),
            }
        else:
            unavailable_features.append({
                "feature": "country_avg_dayslate",
                "reason": "Dataset lacks required 'country_code' column or user historical settlement data.",
            })

        # Assemble summary structure
        feature_summary = {
            "total_features_requested": 10,
            "total_features_created": len(features_created),
            "total_features_unavailable": len(unavailable_features),
            "feature_statistics": summary_stats,
        }

        # Convert datetime columns back to ISO format strings for JSON compatibility
        for col in date_cols:
            if col in work_df.columns and pd.api.types.is_datetime64_any_dtype(work_df[col]):
                work_df[col] = work_df[col].dt.strftime("%Y-%m-%d")

        return work_df, features_created, unavailable_features, feature_summary
