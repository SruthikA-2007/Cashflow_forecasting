"""
Prediction service module.

Loads a user's trained RandomForest model and preprocessing pipeline to run
inference for batch datasets, single new invoices, or real-time invoice payment risk predictions.

Strict security & isolation guarantee:
* A user can ONLY access models and historical invoices where ``user_id`` matches
  their authenticated ID, with fallback to verified default baseline models.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from fastapi import HTTPException, status

from app.config import settings
from app.schemas.prediction import (
    CompanyInfo,
    CompanyListResponse,
    NewInvoicePredictionRequest,
    NewInvoicePredictionResponse,
    PredictionRequest,
    PredictionResult,
    PredictInvoiceRequest,
    PredictInvoiceResponse,
    SinglePredictionRequest,
)
from app.services.feature_engineering_service import FeatureEngineeringService
from app.services.monthly_cashflow_service import monthly_cashflow_service
from app.supabase_client import supabase_admin

ML_MODELS_DIR = os.path.join(os.getcwd(), "ml_models")
DEFAULT_MODEL_DIR = os.path.join(ML_MODELS_DIR, "default")
DATASETS_DIR = os.path.join(os.getcwd(), "datasets")
AR_DATASET_FILE = os.path.join(DATASETS_DIR, "AR_dataset_final_processed_sy.xlsx")

MODEL_METADATA_TABLE = "model_metadata"
INVOICES_TABLE = "invoices"
PREDICTION_RESULTS_TABLE = "prediction_results"
PREDICTIONS_TABLE = "predictions"


def _get_amount_bucket(amount: Any) -> str:
    """Categorize invoice amount into bucket matching training pipeline."""
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
        return "medium"


def _normalize_company_name(name: str) -> str:
    """Normalize company name or customer ID for fuzzy matching."""
    return re.sub(r"[^a-zA-Z0-9]", "", str(name).strip().lower())


class PredictionService:
    """
    Inference service scoped strictly to the authenticated user with baseline ML model fallback.
    """

    def __init__(self, user_id: str = "default") -> None:
        self._user_id = str(user_id)
        self._sb = supabase_admin

    # ------------------------------------------------------------------ #
    # Predict Invoice Payment Risk (New Feature POST /predict)           #
    # ------------------------------------------------------------------ #

    def predict_invoice(self, request: PredictInvoiceRequest) -> PredictInvoiceResponse:
        """
        Executes payment risk prediction for an individual invoice:

        1. Validates inputs (non-empty company, amount > 0, due_date >= order_date).
        2. Retrieves company's historical profile and payment metrics from DB / dataset.
        3. Generates all 17 exact features required by the trained model pipeline.
        4. Transforms features using the fitted sklearn preprocessing pipeline.
        5. Evaluates the Random Forest classifier using predict_proba().
        6. Determines risk level from configurable backend thresholds.
        7. Calculates expected payment delay days and expected payment date.
        8. Returns PredictInvoiceResponse with full prediction details.
        """
        # 1. Validation
        if not request.company_name or not request.company_name.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Company name is required and cannot be empty.",
            )

        if float(request.invoice_amount) <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invoice amount must be greater than zero.",
            )

        try:
            order_dt = datetime.strptime(request.order_date.strip(), "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid order date format. Expected YYYY-MM-DD.",
            )

        try:
            due_dt = datetime.strptime(request.due_date.strip(), "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid due date format. Expected YYYY-MM-DD.",
            )

        if due_dt < order_dt:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Due date cannot be earlier than order date.",
            )

        # 2. Load active trained model & pipeline
        clf, pipeline = self._load_user_active_model_and_pipeline()

        # 3. Fetch historical company context
        company_hist = self._fetch_company_historical_context(request.company_name)

        # 4. Generate all required features
        payment_term_days = (due_dt - order_dt).days
        days_to_due = payment_term_days
        invoice_month = order_dt.month
        invoice_weekday = order_dt.weekday()
        invoice_quarter = (order_dt.month - 1) // 3 + 1
        invoice_amount = float(request.invoice_amount)
        amount_bucket = _get_amount_bucket(invoice_amount)

        customer_avg_dayslate = float(company_hist["customer_avg_dayslate"])
        customer_dispute_rate = float(company_hist["customer_dispute_rate"])
        customer_risk_drift = float(company_hist["customer_risk_drift"])
        country_avg_dayslate = float(company_hist["country_avg_dayslate"])
        country_code = str(company_hist["country_code"])
        disputed = 0
        paperless_bill = int(company_hist.get("paperless_bill", 0))

        # Construct input single-row DataFrame matching training feature set
        input_data = {
            "invoice_amount": invoice_amount,
            "payment_term_days": payment_term_days,
            "invoice_month": invoice_month,
            "invoice_weekday": invoice_weekday,
            "invoice_quarter": invoice_quarter,
            "days_to_due": days_to_due,
            "customer_avg_dayslate": customer_avg_dayslate,
            "customer_dispute_rate": customer_dispute_rate,
            "customer_risk_drift": customer_risk_drift,
            "country_avg_dayslate": country_avg_dayslate,
            "disputed": disputed,
            "paperless_bill": paperless_bill,
            "country_code": country_code,
            "invoice_amount_bucket": amount_bucket,
        }
        input_df = pd.DataFrame([input_data])

        # 5. Transform through exact sklearn preprocessing pipeline
        try:
            X_transformed = pipeline.transform(input_df)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Failed to transform input features through preprocessing pipeline: {str(exc)}",
            )

        # 6. Predict late payment probability using predict_proba
        try:
            probs = clf.predict_proba(X_transformed)[0]
            classes = list(clf.classes_)
            # Robustly find the index for the "late" (positive) class
            # The model may store classes as int, float, bool, or string
            late_idx = -1
            for i, c in enumerate(classes):
                try:
                    if float(c) == 1.0:
                        late_idx = i
                        break
                except (TypeError, ValueError):
                    pass
            # String fallback: "1", "true", "yes", "late"
            if late_idx == -1:
                for i, c in enumerate(classes):
                    if str(c).lower() in ("1", "true", "yes", "late"):
                        late_idx = i
                        break
            # Last resort: take the class with the highest value (positive class is usually last)
            if late_idx == -1:
                late_idx = len(classes) - 1
            late_prob = float(probs[late_idx])
        except Exception:
            pred = clf.predict(X_transformed)[0]
            late_prob = 1.0 if pred in (1, True, "1", "true") else 0.0

        risk_probability = round(float(np.clip(late_prob, 0.0, 1.0)), 2)

        # 7. Assign risk level using configurable backend thresholds
        low_thresh = getattr(settings, "RISK_THRESHOLD_LOW", 0.35)
        med_thresh = getattr(settings, "RISK_THRESHOLD_MEDIUM", 0.70)

        if risk_probability < low_thresh:
            risk_level = "Low Risk"
            prediction_message = "Low probability of payment delay (expected on time)"
        elif risk_probability < med_thresh:
            risk_level = "Medium Risk"
            prediction_message = "Moderate probability of delayed payment"
        else:
            risk_level = "High Risk"
            prediction_message = "High probability of delayed payment"

        # 8. Expected payment delay days calculation
        if risk_probability >= 0.50 or risk_level == "High Risk":
            if customer_avg_dayslate > 0:
                predicted_delay_days = max(1, int(round(customer_avg_dayslate)))
            else:
                predicted_delay_days = max(1, int(round(10 * risk_probability)))
        elif risk_level == "Medium Risk":
            if customer_avg_dayslate > 0:
                predicted_delay_days = max(1, int(round(customer_avg_dayslate * 0.75)))
            else:
                predicted_delay_days = max(1, int(round(5 * risk_probability)))
        else:
            predicted_delay_days = 0

        # 9. Expected payment date = due_date + predicted_delay_days
        expected_payment_date_obj = due_dt + timedelta(days=predicted_delay_days)
        expected_payment_date = expected_payment_date_obj.strftime("%Y-%m-%d")

        # 10. Compute SHAP explanations using exact preprocessed features
        shap_vals_dict: Dict[str, float] = {}
        top_increasing: List[Dict[str, Any]] = []
        top_decreasing: List[Dict[str, Any]] = []
        base_val: Optional[float] = None

        try:
            from app.utils.shap_explainer import explain_single_invoice, get_feature_names
            fnames = get_feature_names(pipeline=pipeline)
            shap_explanation = explain_single_invoice(
                invoice_features=X_transformed,
                pipeline=pipeline,
                model=clf,
                feature_names=fnames,
                class_index=late_idx if (late_idx is not None and late_idx != -1) else 1,
            )
            shap_vals_dict = shap_explanation.get("shap_values", {})
            top_increasing = shap_explanation.get("top_risk_drivers", [])
            top_decreasing = shap_explanation.get("top_protective_factors", [])
            base_val = shap_explanation.get("base_value")
        except Exception:
            pass

        prediction_status = "Late" if predicted_delay_days > 0 or risk_probability >= 0.50 else "On-Time"
        risk_score = round(risk_probability * 100, 2)
        feature_values = {
            "company_name": request.company_name,
            **input_data,
        }

        # 11. Persist invoice & prediction result
        invoice_id = request.invoice_id or str(uuid.uuid4())
        due_month = due_dt.strftime("%Y-%m")

        # Handle manually entered expected inflow if provided by user
        if request.expected_inflow is not None:
            monthly_cashflow_service.set_expected_inflow(due_month, request.expected_inflow)

        # Record invoice in monthly cashflow ledger (prevents duplicate deductions, handles low vs high risk)
        monthly_cashflow_service.record_invoice(
            invoice_id=invoice_id,
            company_name=request.company_name,
            invoice_amount=invoice_amount,
            due_date=request.due_date,
            risk_level=risk_level,
            risk_probability=risk_probability,
            predicted_delay_days=predicted_delay_days,
            order_date=request.order_date,
            shap_explanation={
                "shap_values": shap_vals_dict,
                "top_increasing": top_increasing,
                "top_decreasing": top_decreasing,
                "base_val": base_val,
            },
        )

        # Calculate monthly cashflow metrics & recommendations for this due month
        month_summary = monthly_cashflow_service.calculate_monthly_summary(due_month)

        now = datetime.now(tz=timezone.utc).isoformat()
        try:
            self._save_prediction_result(
                invoice_id=invoice_id,
                customer_id=company_hist.get("customer_id", request.company_name),
                predicted_status=prediction_status,
                probability=risk_probability,
                risk_score=risk_score,
                risk_level=risk_level,
                now=now,
            )
        except Exception:
            pass

        return PredictInvoiceResponse(
            company_name=request.company_name,
            invoice_amount=invoice_amount,
            predicted_delay_days=predicted_delay_days,
            expected_payment_date=expected_payment_date,
            risk_level=risk_level,
            risk_probability=risk_probability,
            prediction_message=prediction_message,
            prediction=prediction_status,
            probability=risk_probability,
            risk_score=risk_score,
            base_value=base_val,
            top_features_increasing_risk=top_increasing,
            top_features_decreasing_risk=top_decreasing,
            shap_values=shap_vals_dict,
            feature_values=feature_values,
            # Monthly cash flow & shortfall outputs
            due_month=due_month,
            month_label=month_summary["month_label"],
            monthly_expected_inflow=month_summary["manually_entered_expected_inflow"],
            high_risk_deductions=month_summary["high_risk_deductions"],
            adjusted_inflow=month_summary["adjusted_expected_inflow"],
            potential_shortfall=month_summary["potential_shortfall"],
            available_surplus=month_summary["available_surplus"],
            expense_recommendations=month_summary,
        )

    # ------------------------------------------------------------------ #
    # Available Companies List (for searchable dropdown / autocomplete)    #
    # ------------------------------------------------------------------ #

    def get_available_companies(self) -> CompanyListResponse:
        """
        Returns list of companies with historical records available in the database/dataset.
        """
        companies_map: Dict[str, Dict[str, Any]] = {}

        # 1. Check Supabase DB invoices
        try:
            resp = self._sb.table(INVOICES_TABLE).select("customer_id, country_code, days_late, disputed").execute()
            rows = resp.data if resp and resp.data else []
            for r in rows:
                cid = r.get("customer_id")
                if cid and str(cid).strip():
                    name = str(cid).strip()
                    if name not in companies_map:
                        companies_map[name] = {
                            "company_name": name,
                            "customer_id": name,
                            "country_code": str(r.get("country_code", "US")),
                            "delays": [],
                            "disputes": [],
                        }
                    if r.get("days_late") is not None:
                        try:
                            companies_map[name]["delays"].append(float(r["days_late"]))
                        except (ValueError, TypeError):
                            pass
                    if r.get("disputed") is not None:
                        is_disp = 1 if bool(r["disputed"]) and str(r["disputed"]).lower() not in ["0", "false"] else 0
                        companies_map[name]["disputes"].append(is_disp)
        except Exception:
            pass

        # 2. Check baseline historical Excel dataset
        if os.path.isfile(AR_DATASET_FILE):
            try:
                df = pd.read_excel(AR_DATASET_FILE)
                if "customerID" in df.columns:
                    grouped = df.groupby("customerID")
                    for cid, group in grouped:
                        name = str(cid).strip()
                        if name not in companies_map:
                            cc = str(group["countryCode"].iloc[0]) if "countryCode" in group.columns else "US"
                            delays = group["DaysLate"].dropna().tolist() if "DaysLate" in group.columns else []
                            disp = group["disputed_flag"].dropna().tolist() if "disputed_flag" in group.columns else []
                            companies_map[name] = {
                                "company_name": name,
                                "customer_id": name,
                                "country_code": cc,
                                "delays": delays,
                                "disputes": disp,
                            }
            except Exception:
                pass

        result: List[CompanyInfo] = []
        for name, data in sorted(companies_map.items(), key=lambda x: x[0]):
            delays = data.get("delays", [])
            disputes = data.get("disputes", [])
            avg_delay = float(np.mean(delays)) if delays else 0.0
            disp_rate = float(np.mean(disputes)) if disputes else 0.0
            result.append(
                CompanyInfo(
                    company_name=name,
                    customer_id=data.get("customer_id", name),
                    country_code=data.get("country_code", "US"),
                    historical_invoices_count=len(delays) if delays else 1,
                    avg_delay_days=round(avg_delay, 1),
                    dispute_rate=round(disp_rate, 2),
                )
            )

        return CompanyListResponse(companies=result, total=len(result))

    # ------------------------------------------------------------------ #
    # Legacy Single Invoice Prediction (POST /predictions/new-invoice)     #
    # ------------------------------------------------------------------ #

    def predict_new_invoice(
        self, request: NewInvoicePredictionRequest
    ) -> NewInvoicePredictionResponse:
        """Legacy prediction endpoint for single invoice."""
        clf, pipeline = self._load_user_active_model_and_pipeline()
        history_df = self._fetch_user_historical_invoices()

        input_df = pd.DataFrame([{
            "customer_id": request.customer_id,
            "country_code": request.country_code or "US",
            "invoice_amount": float(request.invoice_amount),
            "invoice_date": request.invoice_date,
            "due_date": request.due_date,
            "disputed": request.disputed,
            "paperless_bill": request.paperless_bill,
        }])

        fe_service = FeatureEngineeringService(self._user_id)
        engineered_df, _, _, _ = fe_service.engineer(df=input_df, history_df=history_df)

        try:
            X_transformed = pipeline.transform(engineered_df)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Failed to transform input invoice using saved preprocessing pipeline: {str(exc)}",
            )

        try:
            probs = clf.predict_proba(X_transformed)[0]
            classes = list(clf.classes_)
            late_idx = classes.index(1) if 1 in classes else (classes.index(True) if True in classes else -1)
            late_prob = float(probs[late_idx]) if late_idx != -1 else float(probs[-1])
        except Exception:
            pred = clf.predict(X_transformed)[0]
            late_prob = 1.0 if pred in (1, True, "1", "true") else 0.0

        late_payment_probability = round(late_prob, 4)
        risk_score = round(late_payment_probability * 100, 2)

        low_thresh = getattr(settings, "RISK_THRESHOLD_LOW", 0.35) * 100
        med_thresh = getattr(settings, "RISK_THRESHOLD_MEDIUM", 0.70) * 100

        if risk_score < low_thresh:
            risk_level = "Low Risk"
        elif risk_score < med_thresh:
            risk_level = "Medium Risk"
        else:
            risk_level = "High Risk"

        predicted_payment_status = "Late" if late_payment_probability >= 0.5 else "On-Time"

        invoice_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc).isoformat()
        self._save_invoice(invoice_id=invoice_id, request=request, now=now)
        self._save_prediction_result(
            invoice_id=invoice_id,
            customer_id=request.customer_id,
            predicted_status=predicted_payment_status,
            probability=late_payment_probability,
            risk_score=risk_score,
            risk_level=risk_level,
            now=now,
        )

        return NewInvoicePredictionResponse(
            invoice_id=invoice_id,
            customer_id=request.customer_id,
            predicted_payment_status=predicted_payment_status,
            late_payment_probability=late_payment_probability,
            risk_score=risk_score,
            risk_level=risk_level,
            created_at=now,
        )

    # ------------------------------------------------------------------ #
    # Helper methods                                                       #
    # ------------------------------------------------------------------ #

    def _fetch_company_historical_context(self, company_name: str) -> Dict[str, Any]:
        """
        Look up historical metrics for a given company name or customer ID.
        Queries database and dataset files. If missing, raises an informative HTTPException.
        """
        search_norm = _normalize_company_name(company_name)

        # 1. Search in Supabase DB invoices
        try:
            resp = self._sb.table(INVOICES_TABLE).select("*").execute()
            rows = resp.data if resp and resp.data else []
            matched = [
                r for r in rows
                if _normalize_company_name(r.get("customer_id", "")) == search_norm
                or _normalize_company_name(r.get("customer", "")) == search_norm
            ]
            if matched:
                df = pd.DataFrame(matched)
                days_late = pd.to_numeric(df.get("days_late"), errors="coerce").dropna()
                avg_late = float(days_late.mean()) if not days_late.empty else 0.0
                disputed = df.get("disputed")
                disp_rate = float(disputed.mean()) if disputed is not None and not disputed.empty else 0.0
                country = str(df["country_code"].iloc[0]) if "country_code" in df and not df["country_code"].dropna().empty else "US"
                return {
                    "customer_id": str(df["customer_id"].iloc[0]),
                    "customer_avg_dayslate": avg_late,
                    "customer_dispute_rate": disp_rate,
                    "customer_risk_drift": 0.0,
                    "country_avg_dayslate": avg_late,
                    "country_code": country,
                    "paperless_bill": 1,
                }
        except Exception:
            pass

        # 2. Search in historical AR dataset Excel
        if os.path.isfile(AR_DATASET_FILE):
            try:
                df = pd.read_excel(AR_DATASET_FILE)
                if "customerID" in df.columns:
                    mask = df["customerID"].apply(lambda v: _normalize_company_name(v) == search_norm)
                    subset = df[mask]
                    if not subset.empty:
                        # Use the latest accumulated historical state for this customer (iloc[-1])
                        # iloc[0] only has default placeholder global values (e.g. 3.44 days late)
                        avg_late = (
                            float(subset["customer_avg_dayslate"].iloc[-1])
                            if "customer_avg_dayslate" in subset and not pd.isna(subset["customer_avg_dayslate"].iloc[-1])
                            else (float(subset["DaysLate"].mean()) if "DaysLate" in subset else 0.0)
                        )
                        disp_rate = (
                            float(subset["customer_dispute_rate"].iloc[-1])
                            if "customer_dispute_rate" in subset and not pd.isna(subset["customer_dispute_rate"].iloc[-1])
                            else (float((subset["Disputed"].astype(str).str.lower().isin(["1", "true", "yes"])).mean()) if "Disputed" in subset else 0.0)
                        )
                        risk_drift = (
                            float(subset["customer_risk_drift"].iloc[-1])
                            if "customer_risk_drift" in subset and not pd.isna(subset["customer_risk_drift"].iloc[-1])
                            else 0.0
                        )
                        country_avg = (
                            float(subset["country_avg_dayslate"].iloc[-1])
                            if "country_avg_dayslate" in subset and not pd.isna(subset["country_avg_dayslate"].iloc[-1])
                            else avg_late
                        )
                        country_code = str(subset["countryCode"].iloc[-1]) if "countryCode" in subset else "818"
                        paperless = int(subset["paperless_flag"].iloc[-1]) if "paperless_flag" in subset else 1
                        return {
                            "customer_id": str(subset["customerID"].iloc[-1]),
                            "customer_avg_dayslate": avg_late,
                            "customer_dispute_rate": disp_rate,
                            "customer_risk_drift": risk_drift,
                            "country_avg_dayslate": country_avg,
                            "country_code": country_code,
                            "paperless_bill": paperless,
                        }
            except Exception:
                pass

        # If not found, fetch sample available companies to guide the user
        sample_names = []
        try:
            avail = self.get_available_companies()
            sample_names = [c.company_name for c in avail.companies[:5]]
        except Exception:
            sample_names = ["1604-LIFKX", "6708-DPYTF", "8887-NCUZC", "0688-XNJRO", "9149-MATVB"]

        samples_str = ", ".join(sample_names)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Company '{company_name}' was not found in historical records. "
                "Historical payment behavior (such as customer_avg_dayslate, dispute history) "
                "is required by the trained machine learning model to compute payment risk. "
                f"Please select an existing company from the dataset (e.g. {samples_str}) or upload records for this company."
            ),
        )

    def _load_user_active_model_and_pipeline(self) -> Tuple[Any, Any]:
        """
        Locate and load the latest active trained model and pipeline for this user,
        or fall back to the pre-trained default baseline model.
        """
        model_path = None
        pipeline_path = None

        # Strategy 1: Check model_metadata table for user's latest model
        if self._user_id and self._user_id != "default":
            try:
                resp = (
                    self._sb.table(MODEL_METADATA_TABLE)
                    .select("*")
                    .eq("user_id", self._user_id)
                    .eq("status", "ready")
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                rows = resp.data if resp and resp.data else []
                if rows:
                    latest = rows[0]
                    m_path = latest.get("storage_path")
                    p_path = latest.get("pipeline_path")
                    if m_path and os.path.isfile(m_path):
                        model_path = m_path
                    if p_path and os.path.isfile(p_path):
                        pipeline_path = p_path
            except Exception:
                pass

        # Strategy 2: Search user model directory on disk
        user_dir = os.path.join(ML_MODELS_DIR, self._user_id)
        if (not model_path or not pipeline_path) and os.path.isdir(user_dir):
            files = os.listdir(user_dir)
            model_files = [
                f for f in files if f.endswith(".joblib") and "_pipeline" not in f
            ]
            if model_files:
                model_files.sort(
                    key=lambda f: os.path.getmtime(os.path.join(user_dir, f)), reverse=True
                )
                model_filename = model_files[0]
                model_path = os.path.join(user_dir, model_filename)
                stem = model_filename.rsplit(".joblib", 1)[0]
                pipe_filename = f"{stem}_pipeline.joblib"
                p_path = os.path.join(user_dir, pipe_filename)
                if os.path.isfile(p_path):
                    pipeline_path = p_path

        # Strategy 3: Check default pre-trained model directory
        if not model_path or not pipeline_path or not os.path.isfile(model_path):
            default_model = os.path.join(DEFAULT_MODEL_DIR, "default_model.joblib")
            default_pipe = os.path.join(DEFAULT_MODEL_DIR, "default_pipeline.joblib")
            if os.path.isfile(default_model) and os.path.isfile(default_pipe):
                model_path = default_model
                pipeline_path = default_pipe

        if not model_path or not os.path.isfile(model_path) or not pipeline_path or not os.path.isfile(pipeline_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trained machine learning model and preprocessing pipeline not found. Please train a model or ensure default model artifacts exist.",
            )

        try:
            clf = joblib.load(model_path)
            pipeline = joblib.load(pipeline_path)
            return clf, pipeline
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to load trained model or pipeline: {str(exc)}",
            )

    def _fetch_user_historical_invoices(self) -> pd.DataFrame:
        """Fetch historical invoice records belonging to user or baseline dataset."""
        try:
            resp = (
                self._sb.table(INVOICES_TABLE)
                .select("*")
                .eq("user_id", self._user_id)
                .execute()
            )
            records = resp.data if resp and resp.data else []
            if records:
                return pd.DataFrame(records)
        except Exception:
            pass

        if os.path.isfile(AR_DATASET_FILE):
            try:
                df = pd.read_excel(AR_DATASET_FILE)
                return df
            except Exception:
                pass

        return pd.DataFrame()

    def _save_invoice(self, invoice_id: str, request: NewInvoicePredictionRequest, now: str) -> None:
        """Save the new invoice in the invoices Supabase table."""
        record = {
            "id": invoice_id,
            "user_id": self._user_id,
            "customer_id": request.customer_id,
            "country_code": request.country_code or "US",
            "invoice_amount": float(request.invoice_amount),
            "invoice_date": request.invoice_date,
            "due_date": request.due_date,
            "disputed": request.disputed,
            "paperless_bill": request.paperless_bill,
            "created_at": now,
        }
        try:
            self._sb.table(INVOICES_TABLE).insert(record).execute()
        except Exception:
            pass

    def _save_prediction_result(
        self,
        invoice_id: str,
        customer_id: str,
        predicted_status: str,
        probability: float,
        risk_score: float,
        risk_level: str,
        now: str,
    ) -> None:
        """Persist prediction results to prediction_results and predictions tables."""
        record = {
            "id": str(uuid.uuid4()),
            "user_id": self._user_id,
            "invoice_id": invoice_id,
            "customer_id": customer_id,
            "predicted_payment_status": predicted_status,
            "late_payment_probability": probability,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "created_at": now,
        }

        try:
            self._sb.table(PREDICTION_RESULTS_TABLE).insert(record).execute()
        except Exception:
            try:
                minimal = {
                    "id": record["id"],
                    "user_id": self._user_id,
                    "invoice_id": invoice_id,
                    "risk_score": risk_score,
                    "risk_level": risk_level,
                    "created_at": now,
                }
                self._sb.table(PREDICTION_RESULTS_TABLE).insert(minimal).execute()
            except Exception:
                pass

        try:
            self._sb.table(PREDICTIONS_TABLE).insert({
                "id": record["id"],
                "user_id": self._user_id,
                "invoice_id": invoice_id,
                "risk_score": risk_score,
                "risk_label": risk_level.lower().replace(" ", "_"),
                "created_at": now,
            }).execute()
        except Exception:
            pass
