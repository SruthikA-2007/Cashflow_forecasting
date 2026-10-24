"""
Settlement update service module.

Handles uploading new or updated settlement records (CSV or Excel) for a dataset:
  1. Verifies dataset ownership.
  2. Matches existing invoices using (invoice_number, customer_id) primary key.
  3. Updates settlement fields: settled_date, payment_status, days_to_settle, days_late, is_late.
  4. Adds genuinely new invoice records while preventing duplicates.
  5. Preserves all historical records without deletion.
  6. Recalculates affected historical features via FeatureEngineeringService.
  7. Marks the dataset and trained models as requiring retraining ("requires_retraining").
"""

import io
import os
import uuid
import pandas as pd
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from fastapi import UploadFile, HTTPException, status

from app.schemas.dataset import DatasetUpdateSettlementsResponse
from app.services.dataset_service import DatasetService
from app.services.feature_engineering_service import FeatureEngineeringService
from app.supabase_client import supabase_admin
from app.utils.column_mapper import detect_column_mapping

DATASETS_TABLE = "datasets"
INVOICES_TABLE = "invoices"
MODEL_METADATA_TABLE = "model_metadata"


def _clean_str(val: Any) -> Optional[str]:
    if pd.isna(val) or val is None:
        return None
    s = str(val).strip()
    if s == "" or s.lower() in ["null", "none", "nan", "<na>"]:
        return None
    return s


def _parse_date(val: Any) -> Optional[pd.Timestamp]:
    if pd.isna(val) or val is None:
        return None
    try:
        dt = pd.to_datetime(val, errors="coerce")
        if pd.isna(dt):
            return None
        return dt
    except Exception:
        return None


def _format_date_str(dt: Optional[pd.Timestamp]) -> Optional[str]:
    if dt is None or pd.isna(dt):
        return None
    return dt.strftime("%Y-%m-%d")


class SettlementUpdateService:
    """
    Settlement update service scoped strictly to the authenticated user.
    """

    def __init__(self, user_id: str) -> None:
        self._user_id = str(user_id)
        self._sb = supabase_admin

    async def update_settlements(
        self, dataset_id: str, file: UploadFile
    ) -> DatasetUpdateSettlementsResponse:
        """
        Processes an uploaded CSV or Excel file containing updated or new settlement records.
        """
        # 1. Verify dataset ownership
        dataset_svc = DatasetService(self._user_id)
        dataset = dataset_svc.get_by_id(dataset_id)
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found or access denied.",
            )

        dataset_name = getattr(dataset, "filename", "dataset")
        if hasattr(dataset, "original_filename") and dataset.original_filename:
            dataset_name = os.path.splitext(dataset.original_filename)[0]

        # 2. Read file content
        filename = file.filename or "settlement_update"
        ext = os.path.splitext(filename)[1].lower()
        if ext not in [".csv", ".xlsx", ".xls"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{ext}'. Only CSV and Excel (.xlsx, .xls) files are supported.",
            )

        content = await file.read()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        try:
            if ext == ".csv":
                df = pd.read_csv(io.BytesIO(content))
            else:
                df = pd.read_excel(io.BytesIO(content))
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse uploaded file: {str(exc)}",
            )

        if df.empty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file contains no rows.",
            )

        # 3. Detect column mapping
        col_mapping = detect_column_mapping(list(df.columns))

        # Rename columns to standard names where mapped
        rename_dict = {v: k for k, v in col_mapping.items() if v and v in df.columns}
        df = df.rename(columns=rename_dict)

        # 4. Fetch existing invoices for this dataset + user to build matching lookup
        try:
            resp = (
                self._sb.table(INVOICES_TABLE)
                .select("*")
                .eq("dataset_id", str(dataset_id))
                .eq("user_id", self._user_id)
                .execute()
            )
            existing_invoices = resp.data if resp and resp.data else []
        except Exception:
            existing_invoices = []

        # Index existing records for primary lookup: (invoice_number, customer_id)
        # and secondary lookup: (customer_id, invoice_date, invoice_amount)
        primary_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
        secondary_map: Dict[Tuple[str, str, float], Dict[str, Any]] = {}
        existing_ids: set = set()

        for inv in existing_invoices:
            inv_id = inv.get("id")
            if inv_id:
                existing_ids.add(inv_id)

            inv_num = _clean_str(inv.get("invoice_number"))
            cust_id = _clean_str(inv.get("customer_id"))
            inv_date = _clean_str(inv.get("invoice_date"))
            amt = inv.get("invoice_amount")

            if inv_num and cust_id:
                primary_map[(inv_num.lower(), cust_id.lower())] = inv

            if cust_id and inv_date and amt is not None:
                try:
                    amt_float = round(float(amt), 2)
                    secondary_map[(cust_id.lower(), inv_date[:10], amt_float)] = inv
                except (ValueError, TypeError):
                    pass

        # Track counters
        updated_records = 0
        new_records = 0
        duplicate_records_skipped = 0
        unmatched_records = 0

        # Keep track of newly added invoice keys during this batch to prevent duplicates
        seen_new_keys: set = set()

        now_iso = datetime.now(tz=timezone.utc).isoformat()

        # 5. Process each row in the uploaded file
        for idx, row in df.iterrows():
            inv_num = _clean_str(row.get("invoice_number"))
            cust_id = _clean_str(row.get("customer_id"))
            settled_dt_val = _parse_date(row.get("settled_date"))
            due_dt_val = _parse_date(row.get("due_date"))
            inv_dt_val = _parse_date(row.get("invoice_date"))
            amount_val = row.get("invoice_amount")
            payment_status_val = _clean_str(row.get("payment_status"))

            # Match against existing invoices
            matched_inv = None
            if inv_num and cust_id:
                matched_inv = primary_map.get((inv_num.lower(), cust_id.lower()))

            if not matched_inv and cust_id and inv_dt_val is not None and amount_val is not None:
                try:
                    amt_float = round(float(amount_val), 2)
                    dt_str = _format_date_str(inv_dt_val)
                    if dt_str:
                        matched_inv = secondary_map.get((cust_id.lower(), dt_str, amt_float))
                except (ValueError, TypeError):
                    pass

            if matched_inv:
                # UPDATE existing invoice record
                target_id = matched_inv.get("id")

                # Resolve date values (use uploaded if present, else keep existing)
                existing_settled = _parse_date(matched_inv.get("settled_date"))
                existing_due = _parse_date(matched_inv.get("due_date"))
                existing_inv = _parse_date(matched_inv.get("invoice_date"))

                final_settled = settled_dt_val if settled_dt_val is not None else existing_settled
                final_due = due_dt_val if due_dt_val is not None else existing_due
                final_inv = inv_dt_val if inv_dt_val is not None else existing_inv

                settled_str = _format_date_str(final_settled)
                due_str = _format_date_str(final_due)
                inv_str = _format_date_str(final_inv)

                # Calculate days_to_settle, days_late, is_late
                days_to_settle = None
                days_late = None
                is_late = None

                if final_settled is not None:
                    if final_inv is not None:
                        days_to_settle = int((final_settled - final_inv).days)
                    if final_due is not None:
                        days_late = int((final_settled - final_due).days)
                        is_late = bool(days_late > 0)

                payment_status = payment_status_val
                if not payment_status:
                    if final_settled is not None:
                        payment_status = "settled"
                    else:
                        payment_status = matched_inv.get("payment_status", "unsettled")

                update_fields = {
                    "settled_date": settled_str,
                    "payment_status": payment_status,
                    "days_to_settle": days_to_settle,
                    "days_late": days_late,
                    "is_late": is_late,
                    "updated_at": now_iso,
                }
                if due_str:
                    update_fields["due_date"] = due_str
                if inv_str:
                    update_fields["invoice_date"] = inv_str

                try:
                    self._sb.table(INVOICES_TABLE).update(update_fields).eq("id", target_id).eq("user_id", self._user_id).execute()
                    updated_records += 1
                except Exception:
                    unmatched_records += 1

            else:
                # Add GENUINELY NEW invoice or skip duplicate / unmatched
                if not cust_id or (not inv_num and amount_val is None):
                    unmatched_records += 1
                    continue

                # Batch deduplication check
                key = (
                    inv_num.lower() if inv_num else "",
                    cust_id.lower(),
                    _format_date_str(inv_dt_val) or "",
                )
                if key in seen_new_keys:
                    duplicate_records_skipped += 1
                    continue
                seen_new_keys.add(key)

                # Format new invoice record
                settled_str = _format_date_str(settled_dt_val)
                due_str = _format_date_str(due_dt_val)
                inv_str = _format_date_str(inv_dt_val)

                days_to_settle = None
                days_late = None
                is_late = None

                if settled_dt_val is not None:
                    if inv_dt_val is not None:
                        days_to_settle = int((settled_dt_val - inv_dt_val).days)
                    if due_dt_val is not None:
                        days_late = int((settled_dt_val - due_dt_val).days)
                        is_late = bool(days_late > 0)

                payment_status = payment_status_val or ("settled" if settled_dt_val else "unsettled")

                new_inv_id = str(uuid.uuid4())
                new_record = {
                    "id": new_inv_id,
                    "dataset_id": str(dataset_id),
                    "user_id": self._user_id,
                    "invoice_number": inv_num,
                    "customer_id": cust_id,
                    "country_code": _clean_str(row.get("country_code")) or "US",
                    "invoice_amount": float(amount_val) if amount_val is not None and not pd.isna(amount_val) else None,
                    "invoice_date": inv_str,
                    "due_date": due_str,
                    "settled_date": settled_str,
                    "payment_status": payment_status,
                    "days_to_settle": days_to_settle,
                    "days_late": days_late,
                    "is_late": is_late,
                    "disputed": bool(row.get("disputed", False)),
                    "paperless_bill": bool(row.get("paperless_bill", False)),
                    "created_at": now_iso,
                    "updated_at": now_iso,
                }

                try:
                    self._sb.table(INVOICES_TABLE).insert(new_record).execute()
                    new_records += 1
                except Exception:
                    unmatched_records += 1

        # 6. Recalculate affected historical features
        try:
            fe_svc = FeatureEngineeringService(self._user_id)
            fe_svc.engineer_dataset(dataset_id=dataset_id)
        except Exception:
            pass

        # 7. Mark dataset and trained models as requiring retraining
        self._mark_requires_retraining(dataset_id=dataset_id, now=now_iso)

        return DatasetUpdateSettlementsResponse(
            dataset_id=str(dataset_id),
            dataset_name=dataset_name,
            updated_records=updated_records,
            new_records=new_records,
            duplicate_records_skipped=duplicate_records_skipped,
            unmatched_records=unmatched_records,
            model_refresh_status="requires_retraining",
            processing_status="requires_retraining",
        )

    def _mark_requires_retraining(self, dataset_id: str, now: str) -> None:
        """Updates dataset processing_status and model metadata status to 'requires_retraining'."""
        try:
            self._sb.table(DATASETS_TABLE).update({
                "processing_status": "requires_retraining",
                "status": "ready",
                "updated_at": now,
            }).eq("id", str(dataset_id)).eq("user_id", self._user_id).execute()
        except Exception:
            pass

        try:
            self._sb.table(MODEL_METADATA_TABLE).update({
                "status": "requires_retraining",
                "processing_status": "requires_retraining",
                "updated_at": now,
            }).eq("dataset_id", str(dataset_id)).eq("user_id", self._user_id).execute()
        except Exception:
            pass
