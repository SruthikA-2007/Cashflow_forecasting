"""
Pydantic schemas for prediction-related request/response bodies.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Requests
# ------------------------------------------------------------------
class PredictionRequest(BaseModel):
    dataset_id: UUID = Field(..., description="Preprocessed dataset to run predictions on")
    model_id: Optional[UUID] = Field(
        None, description="Specific model version to use; defaults to latest"
    )


class SingleInvoiceFeatures(BaseModel):
    """
    Feature set for a single invoice.
    Fields map to engineered features produced by the preprocessing pipeline.
    Extend as needed when ML is implemented.
    """

    invoice_amount: float
    days_since_invoice: int
    customer_payment_history_score: float
    invoice_age_bucket: str = Field(description="e.g. '0-30', '31-60', '61-90', '90+'")
    customer_segment: Optional[str] = None
    overdue_ratio: Optional[float] = None
    # Add more features here during ML phase


class SinglePredictionRequest(BaseModel):
    features: SingleInvoiceFeatures
    model_id: Optional[UUID] = None


class NewInvoicePredictionRequest(BaseModel):
    customer_id: str = Field(..., description="Customer ID")
    country_code: Optional[str] = Field("US", description="Country code e.g. US, UK, DE")
    invoice_amount: float = Field(..., gt=0, description="Invoice amount")
    invoice_date: str = Field(..., description="Invoice date in YYYY-MM-DD format")
    due_date: str = Field(..., description="Due date in YYYY-MM-DD format")
    disputed: bool = Field(False, description="Whether the invoice is disputed")
    paperless_bill: bool = Field(False, description="Whether the bill is paperless")


class PredictInvoiceRequest(BaseModel):
    """
    Request payload for Predict Invoice Payment Risk endpoint (POST /predict).
    """
    company_name: str = Field(..., min_length=1, description="Company name or customer ID")
    invoice_amount: float = Field(..., gt=0, description="Invoice amount (must be > 0)")
    order_date: str = Field(..., description="Order / invoice date in YYYY-MM-DD format")
    due_date: str = Field(..., description="Payment due date in YYYY-MM-DD format")
    expected_inflow: Optional[float] = Field(
        None, ge=0, description="Manually entered expected inflow for the month in which the invoice is due"
    )
    invoice_id: Optional[str] = Field(None, description="Optional invoice ID for tracking/deduplication")


# ------------------------------------------------------------------
# Responses
# ------------------------------------------------------------------
class InvoicePrediction(BaseModel):
    invoice_id: Optional[str] = None
    risk_score: float = Field(ge=0.0, le=1.0, description="Probability of late payment [0–1]")
    risk_label: str = Field(description="One of: low | medium | high | critical")
    predicted_delay_days: Optional[int] = None
    confidence: Optional[float] = None
    shap_values: Optional[dict[str, float]] = None  # populated in ML phase


class PredictionResult(BaseModel):
    prediction_id: UUID
    dataset_id: Optional[UUID] = None
    model_id: Optional[UUID] = None
    created_at: datetime
    predictions: list[InvoicePrediction]
    summary: Optional[dict[str, Any]] = Field(
        None, description="Aggregate stats: counts per risk label, expected shortfall, etc."
    )


class PredictionHistoryResponse(BaseModel):
    history: list[PredictionResult]
    total: int


class NewInvoicePredictionResponse(BaseModel):
    invoice_id: Optional[str] = Field(None, description="ID of the newly created invoice record")
    customer_id: str
    predicted_payment_status: str = Field(description="Payment prediction outcome: 'Late' or 'On-Time'")
    late_payment_probability: float = Field(description="Late payment probability from 0.0 to 1.0")
    risk_score: float = Field(description="Risk score from 0 to 100")
    risk_level: str = Field(description="Risk category: 'Low Risk', 'Medium Risk', or 'High Risk'")
    created_at: str = Field(description="ISO timestamp of the prediction")


class PredictInvoiceResponse(BaseModel):
    """
    Response payload for Predict Invoice Payment Risk endpoint (POST /predict).
    Maintains 100% backward compatibility while adding SHAP explainability.
    """
    # Existing fields
    company_name: str = Field(..., description="Company name or customer identifier")
    invoice_amount: float = Field(..., description="Invoice amount")
    predicted_delay_days: int = Field(..., description="Predicted payment delay in days")
    expected_payment_date: str = Field(..., description="Expected payment date (YYYY-MM-DD)")
    risk_level: str = Field(..., description="'Low Risk', 'Medium Risk', or 'High Risk'")
    risk_probability: float = Field(..., description="Late payment probability (0.0 to 1.0)")
    prediction_message: str = Field(..., description="Human-readable prediction explanation message")

    # SHAP Explainability & Enhanced Response fields
    prediction: str = Field("Late", description="Predicted payment status: 'Late' or 'On-Time'")
    probability: float = Field(..., description="Late payment probability (same as risk_probability)")
    risk_score: float = Field(..., description="Risk score from 0 to 100")
    base_value: Optional[float] = Field(None, description="Prior baseline expected probability")
    top_features_increasing_risk: list[dict[str, Any]] = Field(
        default_factory=list, description="Top features pushing probability towards delay"
    )
    top_features_decreasing_risk: list[dict[str, Any]] = Field(
        default_factory=list, description="Top features pushing probability towards on-time payment"
    )
    shap_values: dict[str, float] = Field(
        default_factory=dict, description="SHAP value for each feature"
    )
    feature_values: dict[str, Any] = Field(
        default_factory=dict, description="Input and preprocessed feature values"
    )

    # Monthly Cash Flow & Risk-Based Shortfall fields
    due_month: Optional[str] = Field(None, description="Due date year-month (YYYY-MM)")
    month_label: Optional[str] = Field(None, description="Human readable month label e.g. 'November 2026'")
    monthly_expected_inflow: Optional[float] = Field(None, description="Manually entered expected inflow for due month")
    high_risk_deductions: Optional[float] = Field(None, description="Total deductions for high-risk invoices in this month")
    adjusted_inflow: Optional[float] = Field(None, description="Adjusted expected inflow (expected - deductions)")
    potential_shortfall: Optional[float] = Field(None, description="Potential liquidity shortfall for the month")
    available_surplus: Optional[float] = Field(None, description="Available surplus if no shortfall exists")
    expense_recommendations: Optional[dict[str, Any]] = Field(None, description="Categorized expense recommendations")


class CompanyInfo(BaseModel):
    company_name: str
    customer_id: Optional[str] = None
    country_code: Optional[str] = None
    historical_invoices_count: int = 0
    avg_delay_days: float = 0.0
    dispute_rate: float = 0.0


class CompanyListResponse(BaseModel):
    companies: list[CompanyInfo]
    total: int


class MonthlyInflowRequest(BaseModel):
    year_month: str = Field(..., description="Month and year in YYYY-MM format (e.g. '2026-11')")
    expected_inflow: float = Field(..., ge=0, description="Manually entered monthly expected inflow amount")


class MonthlyInflowResponse(BaseModel):
    year_month: str
    month_label: str
    expected_inflow: float


class MonthlySummaryResponse(BaseModel):
    year_month: str
    month_label: str
    manually_entered_expected_inflow: float
    high_risk_deductions: float
    adjusted_expected_inflow: float
    potential_shortfall: float
    available_surplus: float
    status: str
    total_planned_expenses: float
    essential_expenses_total: float
    deferrable_expenses_total: float
    essential_expenses: list[dict[str, Any]]
    deferrable_expenses: list[dict[str, Any]]
    recommendations: list[str]
    invoices_count: int
    high_risk_invoices_count: int
    low_risk_invoices_count: int
    invoices: list[dict[str, Any]]


