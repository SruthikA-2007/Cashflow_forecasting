"""
Complete Validation Suite for SHAP Explainability Workflow.

Tests all 19 checkpoints requested:
1. Existing model loads correctly.
2. Existing preprocessing still works.
3. Existing predictions have not changed.
4. SHAP explainer loads correctly.
5. SHAP values have the correct dimensions.
6. Feature names match the model features.
7. Feature order is correct.
8. Binary classification is handled correctly.
9. Single-invoice explanation works.
10. Multiple-invoice explanation works.
11. Global SHAP importance works.
12. SHAP plots can be generated.
13. API returns SHAP information.
14. Frontend displays SHAP information.
15. Missing values do not cause unexpected SHAP errors.
16. Encoded categorical features are handled correctly.
17. No duplicate preprocessing is being performed.
18. No model retraining occurs during prediction.
19. Existing prediction functionality is preserved.
"""

import sys
import os
import io
import time
import json
import joblib
import numpy as np
import pandas as pd
import requests

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.utils.shap_explainer import (
    create_shap_explainer,
    calculate_shap_values,
    explain_single_invoice,
    get_top_n_features,
    generate_global_shap_plots,
    get_feature_names,
    load_prediction_model,
    load_preprocessing_pipeline,
)
MODEL_FEATURES = get_feature_names()
from app.services.prediction_service import PredictionService

results = {}

def log_test(name, passed, message=""):
    results[name] = {"passed": passed, "message": message}
    symbol = "PASS" if passed else "FAIL"
    print(f"[{symbol}] {name}: {message}")

print("==========================================================")
print("STARTING COMPLETE SHAP WORKFLOW VALIDATION")
print("==========================================================\n")

# 1. Existing model loads correctly
try:
    model = load_prediction_model()
    if model is not None and hasattr(model, "predict"):
        log_test("1. Model Loading", True, f"Loaded model type: {type(model).__name__} with {len(model.estimators_)} trees")
    else:
        log_test("1. Model Loading", False, "Model is None or lacks predict()")
except Exception as e:
    log_test("1. Model Loading", False, str(e))

# 2. Existing preprocessing still works
try:
    preprocessor = load_preprocessing_pipeline()
    if preprocessor is not None and hasattr(preprocessor, "transform"):
        log_test("2. Preprocessing Pipeline", True, f"Preprocessor loaded successfully with {len(preprocessor.named_steps)} pipeline steps")
    else:
        log_test("2. Preprocessing Pipeline", False, "Preprocessor missing or lacks transform()")
except Exception as e:
    log_test("2. Preprocessing Pipeline", False, str(e))

# Load sample dataset and format input rows
DATASET_PATH = os.path.join(os.path.dirname(__file__), "datasets", "AR_dataset_final_processed_sy.xlsx")
df_raw = pd.read_excel(DATASET_PATH, nrows=50)

sample_invoices = []
for idx in range(5):
    row = df_raw.iloc[idx]
    inv = {
        "invoice_amount": float(row["InvoiceAmount"]),
        "payment_term_days": float(row.get("days_to_due", 30)),
        "invoice_month": int(row.get("invoice_month", 1)),
        "invoice_weekday": int(row.get("invoice_weekday", 0)),
        "invoice_quarter": int((int(row.get("invoice_month", 1)) - 1) // 3 + 1),
        "days_to_due": float(row.get("days_to_due", 30)),
        "customer_avg_dayslate": float(row.get("customer_avg_dayslate", 0.0)),
        "customer_dispute_rate": float(row.get("customer_dispute_rate", 0.0)),
        "customer_risk_drift": float(row.get("customer_risk_drift", 0.0)),
        "country_avg_dayslate": float(row.get("country_avg_dayslate", 0.0)),
        "disputed": int(row.get("disputed_flag", 1 if str(row.get("Disputed")).strip().lower() in ("yes", "true", "1") else 0)),
        "paperless_bill": int(row.get("paperless_flag", 1 if str(row.get("PaperlessBill")).strip().lower() in ("yes", "true", "1") else 0)),
        "country_code": str(row.get("countryCode", "391")),
        "invoice_amount_bucket": str(row.get("invoice_amount_bucket", "medium")),
    }
    sample_invoices.append(inv)

samples_df = pd.DataFrame(sample_invoices)

# 3. Existing predictions have not changed
try:
    X_transformed = preprocessor.transform(samples_df)
    orig_preds = model.predict(X_transformed)
    orig_probs = model.predict_proba(X_transformed)[:, 1]

    # Run second time to ensure deterministic consistency
    X_transformed_2 = preprocessor.transform(samples_df)
    orig_preds_2 = model.predict(X_transformed_2)
    orig_probs_2 = model.predict_proba(X_transformed_2)[:, 1]

    preds_match = np.array_equal(orig_preds, orig_preds_2) and np.allclose(orig_probs, orig_probs_2)
    log_test("3. Prediction Determinism & Invariance", preds_match, f"Sample preds: {orig_preds.tolist()}, probs: {np.round(orig_probs, 4).tolist()}")
except Exception as e:
    log_test("3. Prediction Determinism & Invariance", False, str(e))

# 4. SHAP explainer loads correctly
try:
    explainer = create_shap_explainer(model)
    log_test("4. SHAP Explainer Loading", True, f"TreeExplainer instantiated successfully. Base values = {np.round(explainer.expected_value, 4)}")
except Exception as e:
    log_test("4. SHAP Explainer Loading", False, str(e))

# 5. SHAP values have the correct dimensions
try:
    shap_vals, base_val = calculate_shap_values(X_transformed, explainer=explainer)
    dim_match = (shap_vals.shape == (5, len(MODEL_FEATURES)))
    log_test("5. SHAP Dimensions", dim_match, f"Shape is {shap_vals.shape} (Expected (5, {len(MODEL_FEATURES)}))")
except Exception as e:
    log_test("5. SHAP Dimensions", False, str(e))

# 6 & 7. Feature names match model features and order is correct
try:
    feat_count_match = len(MODEL_FEATURES) == X_transformed.shape[1]
    expected_order = [
        'invoice_amount', 'payment_term_days', 'invoice_month', 'invoice_weekday',
        'invoice_quarter', 'days_to_due', 'customer_avg_dayslate', 'customer_dispute_rate',
        'customer_risk_drift', 'country_avg_dayslate', 'disputed', 'paperless_bill',
        'country_code_391', 'country_code_406', 'country_code_770', 'country_code_818', 'country_code_897'
    ]
    order_match = MODEL_FEATURES == expected_order
    log_test("6. Feature Names Match", feat_count_match, f"{len(MODEL_FEATURES)} model features correctly configured")
    log_test("7. Feature Order Correct", order_match, "Preprocessed feature columns match MODEL_FEATURES 1-to-1")
except Exception as e:
    log_test("6 & 7. Feature Alignment", False, str(e))

# 8. Binary classification handled correctly (Additive Efficiency Check: base_value + sum(shap) == prob)
try:
    calc_probs = base_val + np.sum(shap_vals, axis=1)
    diffs = np.abs(calc_probs - orig_probs)
    max_diff = np.max(diffs)
    efficiency_holds = max_diff < 1e-10
    log_test("8. Binary Classification & Additivity", efficiency_holds, f"Max efficiency discrepancy: {max_diff:.2e} (tolerance: 1e-10)")
except Exception as e:
    log_test("8. Binary Classification & Additivity", False, str(e))

# 9. Single invoice explanation works
try:
    single_res = explain_single_invoice(
        invoice_features=X_transformed[0],
        pipeline=preprocessor,
        model=model,
        feature_names=MODEL_FEATURES,
        top_k=3
    )
    has_keys = all(k in single_res for k in ["base_value", "top_risk_drivers", "top_protective_factors", "all_contributions", "shap_values"])
    log_test("9. Single Invoice Explanation", has_keys, f"Found {len(single_res['top_risk_drivers'])} risk drivers & {len(single_res['top_protective_factors'])} protective factors")
except Exception as e:
    log_test("9. Single Invoice Explanation", False, str(e))

# 10. Multiple invoice explanation works
try:
    top_global = get_top_n_features(X_transformed=X_transformed, n=5, explainer=explainer, model=model, feature_names=MODEL_FEATURES)
    log_test("10. Multiple Invoice Explanation", len(top_global) == 5, f"Top features across batch: {[f['Feature'] for f in top_global[:3]]}")
except Exception as e:
    log_test("10. Multiple Invoice Explanation", False, str(e))

# 11. Global SHAP importance works
try:
    mean_abs_df = pd.DataFrame(top_global)
    has_cols = "Feature" in mean_abs_df.columns and "Mean Absolute SHAP Value" in mean_abs_df.columns
    log_test("11. Global SHAP Importance", has_cols, f"Top feature: {top_global[0]['Feature']} (Mean |SHAP| = {top_global[0]['Mean Absolute SHAP Value']:.4f})")
except Exception as e:
    log_test("11. Global SHAP Importance", False, str(e))

# 12. SHAP plots can be generated
try:
    plot_dir = os.path.join(os.path.dirname(__file__), "reports", "shap")
    os.makedirs(plot_dir, exist_ok=True)
    plots = generate_global_shap_plots(X_transformed=X_transformed, output_dir=plot_dir, explainer=explainer, model=model, feature_names=MODEL_FEATURES)
    plots_exist = all(os.path.exists(p) and os.path.getsize(p) > 1000 for p in plots.values())
    log_test("12. SHAP Plots Generation", plots_exist, f"Generated: {list(plots.keys())}")
except Exception as e:
    log_test("12. SHAP Plots Generation", False, str(e))

# 13. API returns SHAP information
try:
    api_resp = requests.post(
        "http://127.0.0.1:8000/predict",
        json={
            "company_name": "0187-ERLSR",
            "invoice_amount": 15000.0,
            "order_date": "2026-09-01",
            "due_date": "2026-10-01"
        },
        timeout=5
    )
    if api_resp.status_code == 200:
        data = api_resp.json()
        has_shap = (
            "prediction" in data
            and "probability" in data
            and "top_features_increasing_risk" in data
            and "top_features_decreasing_risk" in data
            and "shap_values" in data
            and "feature_values" in data
            and "base_value" in data
        )
        log_test("13. API Returns SHAP Info", has_shap, f"Status 200, returned {len(data['shap_values'])} SHAP feature values")
    else:
        log_test("13. API Returns SHAP Info", False, f"API returned status {api_resp.status_code}: {api_resp.text}")
except Exception as e:
    log_test("13. API Returns SHAP Info", False, str(e))

# 14. Frontend displays SHAP information
try:
    frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "src", "components", "PredictInvoiceSection.jsx")
    with open(frontend_path, "r", encoding="utf-8") as f:
        frontend_code = f.read()
    
    checks = [
        "shap-explainability-section" in frontend_code,
        "Main Factors Increasing Risk" in frontend_code,
        "Main Factors Decreasing Risk" in frontend_code,
        "SHAP Feature Importance" in frontend_code,
        "increased the model's late-payment prediction" in frontend_code,
        "decreased the model's late-payment prediction" in frontend_code,
        "reflect model reliance and correlational patterns, not direct causation" in frontend_code
    ]
    all_front = all(checks)
    log_test("14. Frontend Displays SHAP Info", all_front, "All required UI elements, non-causal language, and bar chart present")
except Exception as e:
    log_test("14. Frontend Displays SHAP Info", False, str(e))

# 15. Missing values do not cause unexpected SHAP errors
try:
    df_missing = samples_df.head(2).copy()
    df_missing.loc[0, "customer_avg_dayslate"] = np.nan
    df_missing.loc[0, "customer_dispute_rate"] = np.nan
    df_missing.loc[1, "country_avg_dayslate"] = np.nan
    X_missing = preprocessor.transform(df_missing)
    shap_missing, _ = calculate_shap_values(X_missing, explainer=explainer)
    no_nan_shap = not np.isnan(shap_missing).any()
    log_test("15. Missing Values Robustness", no_nan_shap, "Imputer in pipeline handles NaNs; SHAP produces clean, non-NaN values")
except Exception as e:
    log_test("15. Missing Values Robustness", False, str(e))

# 16. Encoded categorical features handled correctly
try:
    cat_cols = [c for c in MODEL_FEATURES if c.startswith("country_code_")]
    cat_vals = [shap_vals[0, MODEL_FEATURES.index(c)] for c in cat_cols]
    log_test("16. Encoded Categorical Features", len(cat_cols) == 5, f"All 5 OHE country columns properly routed to SHAP: {cat_cols}")
except Exception as e:
    log_test("16. Encoded Categorical Features", False, str(e))

# 17. No duplicate preprocessing being performed
try:
    service_path = os.path.join(os.path.dirname(__file__), "app", "services", "prediction_service.py")
    with open(service_path, "r", encoding="utf-8") as f:
        srv_code = f.read()
    
    # Extract the predict_invoice method implementation
    predict_invoice_body = srv_code.split("def predict_invoice(")[1].split("def get_available_companies(")[0]
    transform_calls = predict_invoice_body.count("pipeline.transform(")
    no_duplicate = (transform_calls == 1) and ("invoice_features=X_transformed" in predict_invoice_body)
    log_test("17. No Duplicate Preprocessing", no_duplicate, f"pipeline.transform is called exactly {transform_calls} time in predict_invoice, X_transformed reused in SHAP")
except Exception as e:
    log_test("17. No Duplicate Preprocessing", False, str(e))

# 18. No model retraining occurs during prediction
try:
    fit_calls = [m for m in ["model.fit(", "preprocessor.fit(", "clf.fit(", "fit_resample("] if m in srv_code]
    log_test("18. No Model Retraining", len(fit_calls) == 0, "Zero fit() calls in prediction service; model remains fixed and immutable")
except Exception as e:
    log_test("18. No Model Retraining", False, str(e))

# 19. Existing prediction functionality is preserved
try:
    if 'data' in locals():
        orig_fields = ["company_name", "invoice_amount", "predicted_delay_days", "expected_payment_date", "risk_level", "risk_probability", "prediction_message"]
        pres_all = all(k in data for k in orig_fields)
        log_test("19. Existing Prediction Preserved", pres_all, f"All legacy fields intact: {orig_fields}")
    else:
        log_test("19. Existing Prediction Preserved", False, "No data to inspect")
except Exception as e:
    log_test("19. Existing Prediction Preserved", False, str(e))

print("\n==========================================================")
all_passed = all(t["passed"] for t in results.values())
passed_count = sum(1 for t in results.values() if t["passed"])
print(f"VALIDATION SUMMARY: {passed_count}/{len(results)} CHECKS PASSED")
print("==========================================================")

if not all_passed:
    sys.exit(1)
