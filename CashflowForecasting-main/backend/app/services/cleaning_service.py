"""
Data cleaning service module.
Handles loading invoice records for a dataset, deduplication, date standardization,
numeric amount conversion, boolean value standardization, validation, metrics calculation
(days_to_settle, days_late, is_late), updating database, and updating processing status.
"""

import json
import os
import uuid
import pandas as pd
from datetime import datetime, timezone
from typing import Any
from fastapi import HTTPException, status

from app.schemas.dataset import DatasetCleanResponse
from app.services.dataset_service import DatasetService
from app.supabase_client import supabase_admin

DATASETS_TABLE = "datasets"
INVOICES_TABLE = "invoices"
CLEANED_DIR = os.path.join(os.getcwd(), "uploads", "cleaned")


def _standardize_bool(val: Any) -> bool:
    """Standardizes truthy/falsy representations into bool."""
    if pd.isna(val) or val is None:
        return False
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    return s in ["true", "1", "yes", "y", "t"]


class CleaningService:
    """
    Data cleaning service scoped strictly to the authenticated user.
    """

    def __init__(self, user_id: str) -> None:
        self._user_id = str(user_id)
        self._sb = supabase_admin

    def clean_dataset(self, dataset_id: str) -> DatasetCleanResponse:
        """
        Executes data cleaning pipeline on invoice records for the specified dataset.
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
                detail="No invoice records found for this dataset to clean.",
            )

        df = pd.DataFrame(raw_records)
        original_records = len(df)

        # 3. Deduplication based primarily on invoice_number and customer_id
        duplicate_records_removed = 0
        dup_subset = [c for c in ["invoice_number", "customer_id"] if c in df.columns]
        if dup_subset:
            initial_count = len(df)
            df = df.drop_duplicates(subset=dup_subset, keep="first")
            duplicate_records_removed = initial_count - len(df)

        # 4. Standardize & convert data types
        # Numeric invoice amount
        if "invoice_amount" in df.columns:
            df["invoice_amount"] = pd.to_numeric(df["invoice_amount"], errors="coerce")
        else:
            df["invoice_amount"] = None

        # Standardize dates to datetime objects
        date_cols = ["invoice_date", "due_date", "settled_date"]
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
            else:
                df[col] = pd.NaT

        # Standardize boolean fields
        bool_cols = ["disputed", "paperless_bill"]
        for col in bool_cols:
            if col in df.columns:
                df[col] = df[col].apply(_standardize_bool)
            else:
                df[col] = False

        # 5. Validation and invalid record removal
        # Invalid if invoice_amount is missing/<=0 or invoice_date is missing or invoice_number is empty/missing
        invalid_mask = (
            df["invoice_amount"].isna()
            | (df["invoice_amount"] <= 0)
            | df["invoice_date"].isna()
            | df["invoice_number"].isna()
            | (df["invoice_number"].astype(str).str.strip() == "")
        )

        invalid_records_removed = int(invalid_mask.sum())
        df = df[~invalid_mask].copy()

        # 6. Count missing optional values handled
        missing_values_count = (
            df[["due_date", "settled_date", "country_code"]].isna().sum().sum()
            if not df.empty
            else 0
        )
        missing_values_handled = int(missing_values_count)

        # 7. Calculate metrics: days_to_settle, days_late, is_late
        if not df.empty:
            df["days_to_settle"] = (df["settled_date"] - df["invoice_date"]).dt.days
            df["days_late"] = (df["settled_date"] - df["due_date"]).dt.days
            df["is_late"] = df["days_late"].apply(
                lambda d: bool(d > 0) if pd.notna(d) else False
            )
        else:
            df["days_to_settle"] = None
            df["days_late"] = None
            df["is_late"] = False

        final_records = len(df)
        now = datetime.now(tz=timezone.utc).isoformat()

        # 8. Safely update cleaned invoice records in database
        cleaned_records = []
        for _, row in df.iterrows():
            rec = {
                "id": str(row["id"]) if "id" in row and pd.notna(row["id"]) else str(uuid.uuid4()),
                "dataset_id": str(dataset_id),
                "user_id": self._user_id,
                "invoice_number": str(row["invoice_number"]) if pd.notna(row["invoice_number"]) else None,
                "customer_id": str(row["customer_id"]) if pd.notna(row["customer_id"]) else None,
                "country_code": str(row["country_code"]) if pd.notna(row["country_code"]) else None,
                "invoice_date": row["invoice_date"].strftime("%Y-%m-%d") if pd.notna(row["invoice_date"]) else None,
                "due_date": row["due_date"].strftime("%Y-%m-%d") if pd.notna(row["due_date"]) else None,
                "settled_date": row["settled_date"].strftime("%Y-%m-%d") if pd.notna(row["settled_date"]) else None,
                "invoice_amount": float(row["invoice_amount"]) if pd.notna(row["invoice_amount"]) else None,
                "disputed": bool(row["disputed"]) if pd.notna(row["disputed"]) else False,
                "paperless_bill": bool(row["paperless_bill"]) if pd.notna(row["paperless_bill"]) else False,
                "days_to_settle": int(row["days_to_settle"]) if pd.notna(row["days_to_settle"]) else None,
                "days_late": int(row["days_late"]) if pd.notna(row["days_late"]) else None,
                "is_late": bool(row["is_late"]) if pd.notna(row["is_late"]) else False,
                "created_at": now,
            }
            cleaned_records.append(rec)

        # Update DB: Delete old records for dataset and insert cleaned ones
        try:
            self._sb.table(INVOICES_TABLE).delete().eq("dataset_id", str(dataset_id)).eq("user_id", self._user_id).execute()
        except Exception:
            pass

        if cleaned_records:
            batch_size = 500
            for i in range(0, len(cleaned_records), batch_size):
                chunk = cleaned_records[i : i + batch_size]
                try:
                    self._sb.table(INVOICES_TABLE).insert(chunk).execute()
                except Exception:
                    base_chunk = []
                    for r in chunk:
                        base_r = {k: v for k, v in r.items() if k not in ["days_to_settle", "days_late", "is_late"]}
                        base_chunk.append(base_r)
                    try:
                        self._sb.table(INVOICES_TABLE).insert(base_chunk).execute()
                    except Exception:
                        pass

        # 9. Update dataset status to "cleaned"
        dataset_name = getattr(dataset, "filename", "dataset")
        if hasattr(dataset, "original_filename") and dataset.original_filename:
            dataset_name = os.path.splitext(dataset.original_filename)[0]

        try:
            self._sb.table(DATASETS_TABLE).update({
                "status": "cleaned",
                "processing_status": "cleaned",
                "total_records": final_records,
                "row_count": final_records,
                "updated_at": now,
            }).eq("id", str(dataset_id)).eq("user_id", self._user_id).execute()
        except Exception:
            pass

        # 10. Persist cleaning summary to disk for later retrieval by /summary endpoint
        user_cleaned_dir = os.path.join(CLEANED_DIR, self._user_id)
        os.makedirs(user_cleaned_dir, exist_ok=True)
        cleaning_meta = {
            "dataset_id": str(dataset_id),
            "dataset_name": dataset_name,
            "original_records": original_records,
            "duplicate_records_removed": duplicate_records_removed,
            "invalid_records_removed": invalid_records_removed,
            "missing_values_handled": missing_values_handled,
            "final_records": final_records,
            "processing_status": "cleaned",
            "created_at": now,
        }
        try:
            meta_path = os.path.join(user_cleaned_dir, f"{dataset_id}_cleaned.json")
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(cleaning_meta, f, indent=2)
        except Exception:
            pass

        return DatasetCleanResponse(
            dataset_id=str(dataset_id),
            dataset_name=dataset_name,
            original_records=original_records,
            duplicate_records_removed=duplicate_records_removed,
            invalid_records_removed=invalid_records_removed,
            missing_values_handled=missing_values_handled,
            final_records=final_records,
            processing_status="cleaned",
        )
