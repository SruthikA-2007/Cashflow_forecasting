"""
Automated test suite verifying the SHAP implementation against the existing
dataset and trained Random Forest model.
"""

import json
import os
import numpy as np
import pandas as pd

from app.utils.shap_explainer import (
    load_prediction_model,
    load_preprocessing_pipeline,
    get_feature_names,
    create_shap_explainer,
    calculate_shap_values,
    explain_single_invoice,
    get_global_feature_importance,
)

def run_tests():
    print("==========================================================")
    print("STEP 1 & 2: Load Existing Trained Model & Pipeline")
    print("==========================================================")
    clf = load_prediction_model()
    pipeline = load_preprocessing_pipeline()
    feature_names = get_feature_names()

    print(f"Model: {type(clf).__name__} (n_estimators={len(clf.estimators_)}, classes={clf.classes_.tolist()})")
    print(f"Pipeline: {type(pipeline).__name__}")
    print(f"Total Model Features: {clf.n_features_in_}")
    print(f"Total Feature Names: {len(feature_names)}")
    assert clf.n_features_in_ == len(feature_names) == 17, "Feature count mismatch!"

    print("\n==========================================================")
    print("STEP 3: Select Several Existing Invoices from Dataset")
    print("==========================================================")
    dataset_path = os.path.join(os.getcwd(), "datasets", "AR_dataset_final_processed_sy.xlsx")
    df_raw = pd.read_excel(dataset_path)

    sample_indices = [0, 45, 120, 350, 780]
    sample_invoices = []

    for idx in sample_indices:
        row = df_raw.iloc[idx]
        inv = {
            "customer_id": str(row["customerID"]),
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
    cids = [s["customer_id"] for s in sample_invoices]
    print(f"Selected {len(sample_invoices)} invoices with Customer IDs: {cids}")

    print("\n==========================================================")
    print("STEP 4: Generate Existing Predictions BEFORE SHAP")
    print("==========================================================")
    X_transformed = pipeline.transform(samples_df)
    orig_probas = clf.predict_proba(X_transformed)[:, 1]
    orig_preds = clf.predict(X_transformed)

    for i, inv in enumerate(sample_invoices):
        print(f"  Invoice {i+1} [Customer: {inv['customer_id']}, Amount: ${inv['invoice_amount']:,.2f}]: "
              f"PredClass={orig_preds[i]}, LateProbability={orig_probas[i]:.4f}")

    print("\n==========================================================")
    print("STEP 5: Generate SHAP Values for the Same Invoices")
    print("==========================================================")
    explainer = create_shap_explainer(clf)
    shap_matrix, base_values = calculate_shap_values(X_transformed, explainer=explainer)
    print(f"Computed SHAP matrix shape: {shap_matrix.shape}")
    print(f"Computed Base values (Late class expected value): {base_values[0]:.4f}")

    print("\n==========================================================")
    print("STEP 6: Verify Predictions Remain Completely Unaltered")
    print("==========================================================")
    probas_after = clf.predict_proba(X_transformed)[:, 1]
    preds_after = clf.predict(X_transformed)

    max_delta = float(np.max(np.abs(orig_probas - probas_after)))
    preds_identical = bool(np.array_equal(orig_preds, preds_after))

    print(f"Prediction Classes match before vs after: {preds_identical}")
    print(f"Maximum Probability Difference: {max_delta}")
    assert preds_identical, "Prediction classes changed!"
    assert max_delta == 0.0, "Prediction probabilities changed!"

    print("\n==========================================================")
    print("STEP 7: Verify SHAP Dimensions Match Features Count")
    print("==========================================================")
    print(f"SHAP Matrix Columns: {shap_matrix.shape[1]}")
    print(f"Model Input Features: {clf.n_features_in_}")
    print(f"Feature Names List Length: {len(feature_names)}")
    assert shap_matrix.shape[1] == clf.n_features_in_ == len(feature_names) == 17, "Shape mismatch!"

    print("\n==========================================================")
    print("STEP 8: Verify Feature Names & Ordering Correspondence")
    print("==========================================================")
    sample_explanation = explain_single_invoice(
        invoice_features=sample_invoices[0],
        pipeline=pipeline,
        model=clf,
        explainer=explainer,
        feature_names=feature_names,
    )
    shap_keys = list(sample_explanation["shap_values"].keys())
    assert shap_keys == feature_names, "Feature names do not match exact ordering!"
    print("Feature names perfectly match the trained model ordering:")
    for idx, name in enumerate(feature_names):
        print(f"  [{idx:02d}] {name} -> SHAP: {sample_explanation['shap_values'][name]:+.6f}")

    print("\n==========================================================")
    print("STEP 9: Integrity Check (NaN, Null, Additive Efficiency)")
    print("==========================================================")
    has_nan_shap = bool(np.isnan(shap_matrix).any())
    has_inf_shap = bool(np.isinf(shap_matrix).any())
    has_nan_base = bool(np.isnan(base_values).any())

    print(f"Contains NaN in SHAP: {has_nan_shap}")
    print(f"Contains Inf in SHAP: {has_inf_shap}")
    print(f"Contains NaN in Base: {has_nan_base}")
    assert not has_nan_shap and not has_inf_shap and not has_nan_base, "NaN/Inf detected in SHAP!"

    print("\nAdditive Property Verification: Base_Value + Sum(SHAP) == Predicted_Probability")
    for i in range(len(sample_invoices)):
        base = base_values[i]
        sum_shap = float(np.sum(shap_matrix[i]))
        reconstructed = base + sum_shap
        pred_prob = orig_probas[i]
        diff = abs(reconstructed - pred_prob)
        print(f"  Invoice {i+1} ({sample_invoices[i]['customer_id']}): "
              f"Base ({base:.4f}) + Sum(SHAP) ({sum_shap:+.4f}) = {reconstructed:.4f} | "
              f"Model Proba = {pred_prob:.4f} | Difference = {diff:.2e}")
        assert diff < 1e-5, f"Additive efficiency violated on invoice {i+1}!"

    print("\n==========================================================")
    print("STEP 10: Detailed Single Invoice Demonstration")
    print("==========================================================")
    demo_invoice = sample_invoices[0]
    demo_exp = explain_single_invoice(
        invoice_features=demo_invoice,
        pipeline=pipeline,
        model=clf,
        explainer=explainer,
        feature_names=feature_names,
        top_k=3,
    )

    print(f"Customer ID: {demo_invoice['customer_id']}")
    print(f"Invoice Amount: ${demo_invoice['invoice_amount']:,.2f}")
    print(f"Model Predicted Late Probability: {demo_exp['predicted_probability']:.4f}")
    print(f"Base (Prior) Probability: {demo_exp['base_value']:.4f}")

    print("\nTop Risk-Increasing Features (Pushing towards Delay):")
    for item in demo_exp["top_risk_drivers"]:
        print(f"  - {item['feature']}: {item['shap_value']:+.4f} (Raw Value: {item['feature_value']})")

    print("\nTop Protective Features (Pushing towards On-Time):")
    for item in demo_exp["top_protective_factors"]:
        print(f"  - {item['feature']}: {item['shap_value']:+.4f} (Raw Value: {item['feature_value']})")

    print("\nGlobal Feature Importance (Across Tested Samples):")
    global_importance = get_global_feature_importance(
        X_transformed=X_transformed,
        explainer=explainer,
        model=clf,
        feature_names=feature_names,
    )
    for rank, item in enumerate(global_importance[:5], start=1):
        print(f"  {rank}. {item['feature']}: mean(|SHAP|) = {item['importance']:.6f}")

    print("\n>>> ALL TESTS COMPLETED AND PASSED WITH ZERO ERRORS. <<<")

if __name__ == "__main__":
    run_tests()
