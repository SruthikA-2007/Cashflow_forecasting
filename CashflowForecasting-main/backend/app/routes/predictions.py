"""
Prediction routes.

Endpoints:
  POST  /predictions/new-invoice    - Predict payment risk for a new invoice [IMPLEMENTED]
  POST  /predictions/predict        - Run batch predictions on a dataset    [stub]
  POST  /predictions/predict-single - Run a single invoice prediction        [stub]
  GET   /predictions/history        - List past prediction runs             [stub]
  GET   /predictions/{prediction_id}- Fetch a specific prediction result    [stub]

Authentication
--------------
Every endpoint requires a valid Supabase Bearer token.
A user can only run predictions using their own trained models and historical data.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_user
from app.schemas.auth import AuthUser
from app.schemas.prediction import (
    CompanyListResponse,
    NewInvoicePredictionRequest,
    NewInvoicePredictionResponse,
    MonthlyInflowRequest,
    MonthlyInflowResponse,
    MonthlySummaryResponse,
    PredictionHistoryResponse,
    PredictionRequest,
    PredictionResult,
    PredictInvoiceRequest,
    PredictInvoiceResponse,
    SinglePredictionRequest,
)
from app.services.monthly_cashflow_service import monthly_cashflow_service, format_month_label
from app.services.prediction_service import PredictionService

router = APIRouter()

_NOT_IMPLEMENTED = HTTPException(
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    detail="This endpoint is not yet implemented.",
)


# ------------------------------------------------------------------
# POST /predictions/predict & /predict
# ------------------------------------------------------------------
@router.post(
    "/predict",
    response_model=PredictInvoiceResponse,
    status_code=status.HTTP_200_OK,
    summary="Predict invoice payment risk using trained ML model",
)
async def predict_payment(
    body: PredictInvoiceRequest,
    user: AuthUser = Depends(get_current_user),
):
    """
    Accepts Company Name, Invoice Amount, Order Date, and Due Date.
    Resolves historical customer features from existing dataset/DB, applies
    the exact trained preprocessing pipeline, and predicts payment delay risk
    using the trained Random Forest machine learning model.
    """
    user_id = str(user.user_id) if user else "default"
    svc = PredictionService(user_id=user_id)
    return svc.predict_invoice(request=body)


# ------------------------------------------------------------------
# GET /predictions/companies
# ------------------------------------------------------------------
@router.get(
    "/companies",
    response_model=CompanyListResponse,
    status_code=status.HTTP_200_OK,
    summary="List available companies/customers with historical records",
)
async def list_available_companies(
    user: AuthUser = Depends(get_current_user),
):
    """
    Returns list of companies present in the historical dataset/database
    available for risk prediction.
    """
    user_id = str(user.user_id) if user else "default"
    svc = PredictionService(user_id=user_id)
    return svc.get_available_companies()


# ------------------------------------------------------------------
# POST /predictions/new-invoice
# ------------------------------------------------------------------
@router.post(
    "/new-invoice",
    response_model=NewInvoicePredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Predict payment risk for a newly entered invoice",
)
async def predict_new_invoice(
    body: NewInvoicePredictionRequest,
    user: AuthUser = Depends(get_current_user),
):
    """
    Accepts details of a new invoice, runs feature engineering against the user's
    historical dataset, transforms inputs through the user's trained preprocessing
    pipeline, and predicts late payment risk using the user's trained Random Forest model.
    """
    user_id = str(user.user_id) if user else "default"
    svc = PredictionService(user_id=user_id)
    return svc.predict_new_invoice(request=body)


# ------------------------------------------------------------------
# POST /predictions/monthly-inflow
# ------------------------------------------------------------------
@router.post(
    "/monthly-inflow",
    response_model=MonthlyInflowResponse,
    status_code=status.HTTP_200_OK,
    summary="Store or update manually entered expected inflow for a month",
)
async def set_monthly_inflow(
    body: MonthlyInflowRequest,
    user: AuthUser = Depends(get_current_user),
):
    """
    Stores or updates the manually entered expected inflow for a specific month (YYYY-MM).
    In accordance with requirements:
    - If expected inflow for that month already exists, updates it without duplicate records.
    - Does NOT add invoice amounts to the manually entered figure.
    """
    amount = monthly_cashflow_service.set_expected_inflow(body.year_month, body.expected_inflow)
    clean_ym = body.year_month.strip()[:7]
    return MonthlyInflowResponse(
        year_month=clean_ym,
        month_label=format_month_label(clean_ym),
        expected_inflow=amount,
    )


# ------------------------------------------------------------------
# GET /predictions/monthly-inflow
# ------------------------------------------------------------------
@router.get(
    "/monthly-inflow",
    status_code=status.HTTP_200_OK,
    summary="Get all stored monthly expected inflows",
)
async def get_all_monthly_inflows(
    user: AuthUser = Depends(get_current_user),
):
    """Returns dictionary of all stored monthly expected inflows { 'YYYY-MM': amount }."""
    return monthly_cashflow_service.get_all_monthly_inflows()


# ------------------------------------------------------------------
# GET /predictions/monthly-summary/{year_month}
# ------------------------------------------------------------------
@router.get(
    "/monthly-summary/{year_month}",
    response_model=MonthlySummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get monthly cash flow, deductions, shortfall and recommendations",
)
async def get_monthly_summary(
    year_month: str,
    user: AuthUser = Depends(get_current_user),
):
    """
    Returns monthly dashboard figures for the selected month and year:
    - Manually entered expected inflow
    - High-risk invoice deductions (strictly for invoices due in this month)
    - Adjusted expected inflow
    - Potential shortfall
    - Recommended essential and deferrable expenses
    - Invoices ledger for this month with SHAP details
    """
    summary = monthly_cashflow_service.calculate_monthly_summary(year_month)
    return summary


# ------------------------------------------------------------------
# DELETE /predictions/invoices/{invoice_id}
# ------------------------------------------------------------------
@router.delete(
    "/invoices/{invoice_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete an invoice and recalculate monthly deductions",
)
async def delete_invoice(
    invoice_id: str,
    user: AuthUser = Depends(get_current_user),
):
    """
    Removes invoice and triggers dynamic recalculation of monthly risk deductions.
    """
    success = monthly_cashflow_service.delete_invoice(invoice_id)
    return {"success": success, "invoice_id": invoice_id}



# ------------------------------------------------------------------
# Single prediction (stub)
# ------------------------------------------------------------------
@router.post(
    "/predict-single",
    response_model=PredictionResult,
    summary="Predict payment risk for a single invoice record",
)
async def single_predict(
    body: SinglePredictionRequest,
    user: AuthUser = Depends(get_current_user),
):
    raise _NOT_IMPLEMENTED


# ------------------------------------------------------------------
# History (stub)
# ------------------------------------------------------------------
@router.get(
    "/history",
    response_model=PredictionHistoryResponse,
    summary="List previous prediction runs for the current user",
)
async def prediction_history(user: AuthUser = Depends(get_current_user)):
    raise _NOT_IMPLEMENTED


# ------------------------------------------------------------------
# Get by ID (stub)
# ------------------------------------------------------------------
@router.get(
    "/{prediction_id}",
    response_model=PredictionResult,
    summary="Get a specific prediction run result",
)
async def get_prediction(
    prediction_id: str,
    user: AuthUser = Depends(get_current_user),
):
    raise _NOT_IMPLEMENTED
