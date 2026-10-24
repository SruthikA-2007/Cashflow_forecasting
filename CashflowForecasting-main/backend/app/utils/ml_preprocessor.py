"""
Reusable Machine Learning Dataset Preprocessor.
Encapsulates feature extraction, date feature engineering, missing value imputation,
and categorical encoding without data leakage (excluding future settled_date and days_late metrics from input features).
Designed for reuse across both offline training and real-time online inference/prediction.
"""

from typing import Dict, List, Tuple, Any, Optional
import pandas as pd
import numpy as np

# Columns explicitly excluded from input features to prevent data leakage
LEAKAGE_COLUMNS = [
    "settled_date",
    "days_to_settle",
    "days_late",
    "id",
    "dataset_id",
    "user_id",
    "created_at",
    "invoice_number",
]

# Core features used for machine learning
BASE_FEATURE_COLUMNS = [
    "invoice_amount",
    "payment_term_days",
    "invoice_month",
    "invoice_dayofweek",
    "invoice_quarter",
    "disputed",
    "paperless_bill",
]


class DatasetPreprocessor:
    """
    Stateless & Configurable Preprocessor for Accounts Receivable invoice data.
    """

    @staticmethod
    def process(
        df: pd.DataFrame,
        saved_config: Optional[Dict[str, Any]] = None,
    ) -> Tuple[pd.DataFrame, Optional[pd.Series], Dict[str, Any]]:
        """
        Transforms raw/cleaned dataset into ML-ready numerical feature matrix (X) and target (y).
        
        Args:
            df: Cleaned pandas DataFrame containing invoice records.
            saved_config: Optional dictionary containing precomputed medians/modes & categories from training.

        Returns:
            Tuple of:
            - X: Prepared features DataFrame
            - y: Prepared target Series (is_late) or None
            - config: Dictionary with feature metadata, imputation statistics, and column mappings
        """
        if df.empty:
            raise ValueError("Input DataFrame for preprocessing is empty.")

        work_df = df.copy()
        missing_count = 0

        # 1. Prepare Date Features & Payment Term
        invoice_dt = pd.to_datetime(work_df.get("invoice_date"), errors="coerce")
        due_dt = pd.to_datetime(work_df.get("due_date"), errors="coerce")

        # Extract non-leaking temporal features
        work_df["invoice_month"] = invoice_dt.dt.month
        work_df["invoice_dayofweek"] = invoice_dt.dt.dayofweek
        work_df["invoice_quarter"] = invoice_dt.dt.quarter

        # Calculate payment terms in days (due_date - invoice_date)
        work_df["payment_term_days"] = (due_dt - invoice_dt).dt.days

        # 2. Extract Target Label (y) if present
        y = None
        if "is_late" in work_df.columns:
            y = work_df["is_late"].apply(lambda v: 1 if bool(v) else 0)
        elif "days_late" in work_df.columns:
            y = work_df["days_late"].apply(lambda d: 1 if (pd.notna(d) and d > 0) else 0)

        # 3. Handle Imputation & Statistics
        if saved_config:
            imputation = saved_config.get("imputation", {})
            country_categories = saved_config.get("country_categories", [])
        else:
            imputation = {
                "invoice_amount": float(work_df["invoice_amount"].median()) if "invoice_amount" in work_df and not work_df["invoice_amount"].dropna().empty else 0.0,
                "payment_term_days": float(work_df["payment_term_days"].median()) if "payment_term_days" in work_df and not work_df["payment_term_days"].dropna().empty else 30.0,
                "invoice_month": int(work_df["invoice_month"].mode().iloc[0]) if "invoice_month" in work_df and not work_df["invoice_month"].dropna().empty else 1,
                "invoice_dayofweek": int(work_df["invoice_dayofweek"].mode().iloc[0]) if "invoice_dayofweek" in work_df and not work_df["invoice_dayofweek"].dropna().empty else 0,
                "invoice_quarter": int(work_df["invoice_quarter"].mode().iloc[0]) if "invoice_quarter" in work_df and not work_df["invoice_quarter"].dropna().empty else 1,
                "country_code": str(work_df["country_code"].mode().iloc[0]) if "country_code" in work_df and not work_df["country_code"].dropna().empty else "UNKNOWN",
            }
            country_categories = sorted(list(work_df["country_code"].dropna().astype(str).unique())) if "country_code" in work_df else ["UNKNOWN"]

        # Track missing values handled
        for col in ["invoice_amount", "payment_term_days", "invoice_month", "invoice_dayofweek", "invoice_quarter", "country_code"]:
            if col in work_df.columns:
                missing_count += int(work_df[col].isna().sum())

        # Perform Imputation
        work_df["invoice_amount"] = work_df["invoice_amount"].fillna(imputation["invoice_amount"])
        work_df["payment_term_days"] = work_df["payment_term_days"].fillna(imputation["payment_term_days"])
        work_df["invoice_month"] = work_df["invoice_month"].fillna(imputation["invoice_month"]).astype(int)
        work_df["invoice_dayofweek"] = work_df["invoice_dayofweek"].fillna(imputation["invoice_dayofweek"]).astype(int)
        work_df["invoice_quarter"] = work_df["invoice_quarter"].fillna(imputation["invoice_quarter"]).astype(int)

        # 4. Standardize Booleans
        for bool_col in ["disputed", "paperless_bill"]:
            if bool_col in work_df.columns:
                work_df[bool_col] = work_df[bool_col].apply(lambda v: 1 if bool(v) else 0)
            else:
                work_df[bool_col] = 0

        # 5. One-Hot Encoding for Categorical Country Code
        country_series = work_df["country_code"].fillna(imputation["country_code"]).astype(str) if "country_code" in work_df else pd.Series(["UNKNOWN"] * len(work_df))
        
        country_dummies = pd.DataFrame(index=work_df.index)
        for cat in country_categories:
            col_name = f"country_{cat}"
            country_dummies[col_name] = (country_series == cat).astype(int)

        # Assemble final numerical X DataFrame
        feature_cols = [c for c in BASE_FEATURE_COLUMNS if c in work_df.columns]
        X = pd.concat([work_df[feature_cols], country_dummies], axis=1)

        # Columns used vs excluded
        all_original_columns = list(df.columns)
        used_columns = list(X.columns)
        excluded_columns = [c for c in all_original_columns if c in LEAKAGE_COLUMNS or c in ["invoice_date", "due_date", "country_code"]]

        config = {
            "imputation": imputation,
            "country_categories": country_categories,
            "feature_columns": used_columns,
            "columns_used": used_columns,
            "columns_excluded": excluded_columns,
            "leakage_columns_blocked": LEAKAGE_COLUMNS,
            "missing_values_handled": missing_count,
            "num_features": len(used_columns),
        }

        return X, y, config
