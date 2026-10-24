"""
SHAP Explainability Module for Random Forest Cashflow / Invoice Payment-Delay Prediction.

Key Design & Constraints:
--------------------------
1. Model Reuse: Loads the exact same trained Random Forest model (.joblib) used by the prediction system.
2. Zero Retraining: Explains existing tree ensembles without retraining.
3. TreeExplainer: Uses shap.TreeExplainer optimized specifically for tree ensembles.
4. Pipeline Reuse: Leverages the exact fitted sklearn ColumnTransformer pipeline from the prediction system.
5. Exact Features & Order: Preserves the exact 17 feature names and ordering matching the model input.
6. Robust Output Parsing: Handles multi-class / binary classification output formats across SHAP versions (including SHAP 0.52+).
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd
import shap


# ---------------------------------------------------------------------------
# Constants & Paths
# ---------------------------------------------------------------------------
ML_MODELS_DIR = os.path.join(os.getcwd(), "ml_models")
DEFAULT_MODEL_DIR = os.path.join(ML_MODELS_DIR, "default")
DEFAULT_MODEL_PATH = os.path.join(DEFAULT_MODEL_DIR, "default_model.joblib")
DEFAULT_PIPELINE_PATH = os.path.join(DEFAULT_MODEL_DIR, "default_pipeline.joblib")
DEFAULT_FEATURES_PATH = os.path.join(DEFAULT_MODEL_DIR, "default_features.json")

# In-memory explainer cache to eliminate redundant TreeExplainer reconstruction latency
_EXPLAINER_CACHE: Dict[str, shap.TreeExplainer] = {}
_MODEL_CACHE: Dict[str, Any] = {}
_PIPELINE_CACHE: Dict[str, Any] = {}
_FEATURE_NAMES_CACHE: Dict[str, List[str]] = {}


# ---------------------------------------------------------------------------
# 1. Loading Model, Pipeline & Feature Names
# ---------------------------------------------------------------------------

def load_prediction_model(model_path: Optional[str] = None) -> Any:
    """
    Load the trained Random Forest classifier currently used by the prediction system.
    Defaults to the pre-trained default_model.joblib.
    """
    target_path = model_path or DEFAULT_MODEL_PATH
    if not os.path.isfile(target_path):
        raise FileNotFoundError(f"Trained Random Forest model not found at: {target_path}")

    if target_path not in _MODEL_CACHE:
        _MODEL_CACHE[target_path] = joblib.load(target_path)

    return _MODEL_CACHE[target_path]


def load_preprocessing_pipeline(pipeline_path: Optional[str] = None) -> Any:
    """
    Load the exact fitted preprocessing pipeline used by the prediction system.
    Defaults to default_pipeline.joblib.
    """
    target_path = pipeline_path or DEFAULT_PIPELINE_PATH
    if not os.path.isfile(target_path):
        raise FileNotFoundError(f"Preprocessing pipeline not found at: {target_path}")

    if target_path not in _PIPELINE_CACHE:
        _PIPELINE_CACHE[target_path] = joblib.load(target_path)

    return _PIPELINE_CACHE[target_path]


def get_feature_names(
    pipeline: Optional[Any] = None,
    features_json_path: Optional[str] = None,
) -> List[str]:
    """
    Extract the exact feature names in the exact order expected by the model.
    First inspects features_json_path (or default_features.json), falling back
    to extracting from the ColumnTransformer inside the pipeline.
    """
    manifest_path = features_json_path or DEFAULT_FEATURES_PATH

    if manifest_path in _FEATURE_NAMES_CACHE:
        return _FEATURE_NAMES_CACHE[manifest_path]

    # Strategy 1: Load from feature manifest JSON
    if os.path.isfile(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                names = data.get("feature_names")
                if names and isinstance(names, list):
                    _FEATURE_NAMES_CACHE[manifest_path] = names
                    return names
        except Exception:
            pass

    # Strategy 2: Extract from fitted ColumnTransformer inside pipeline
    pipe = pipeline or load_preprocessing_pipeline()
    try:
        ct = pipe.named_steps.get("preprocessor")
        if ct and hasattr(ct, "transformers_"):
            names: List[str] = []
            for name, trans, cols in ct.transformers_:
                if name == "numeric":
                    names.extend(cols)
                elif name == "categorical":
                    encoder = trans.named_steps["encoder"]
                    ohe_names = encoder.get_feature_names_out(cols).tolist()
                    names.extend(ohe_names)
                elif name == "passthrough":
                    names.extend(cols)
            if names:
                _FEATURE_NAMES_CACHE[manifest_path] = names
                return names
    except Exception:
        pass

    raise RuntimeError("Unable to determine feature names for the trained model.")


# ---------------------------------------------------------------------------
# 2. Creating / Loading SHAP Explainer
# ---------------------------------------------------------------------------

def create_shap_explainer(
    model: Optional[Any] = None,
    model_path: Optional[str] = None,
) -> shap.TreeExplainer:
    """
    Create or retrieve a cached shap.TreeExplainer for the Random Forest model.
    Uses model_output="probability" where supported or defaults to TreeExplainer.
    """
    clf = model or load_prediction_model(model_path)
    cache_key = str(id(clf))

    if cache_key not in _EXPLAINER_CACHE:
        # shap.TreeExplainer is specifically optimized for scikit-learn RandomForest
        _EXPLAINER_CACHE[cache_key] = shap.TreeExplainer(clf)

    return _EXPLAINER_CACHE[cache_key]


# ---------------------------------------------------------------------------
# Helper: SHAP Output Parsing for Binary Classification Across Versions
# ---------------------------------------------------------------------------

def _parse_shap_output(
    shap_out: Any,
    explainer: shap.TreeExplainer,
    class_idx: int = 1,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Normalize SHAP output across different shap versions for binary classification.

    Returns:
        values: 2D numpy array of shape (N, n_features) representing SHAP values for class_idx.
        base_values: 1D numpy array of shape (N,) representing base values for class_idx.
    """
    # Case A: Explanation object returned (explainer(X))
    if hasattr(shap_out, "values") and hasattr(shap_out, "base_values"):
        vals = shap_out.values
        base = shap_out.base_values

        # If shape is (N, n_features, n_classes)
        if vals.ndim == 3:
            vals_for_class = vals[:, :, class_idx]
            if base.ndim == 2:
                base_for_class = base[:, class_idx]
            elif base.ndim == 1:
                base_for_class = np.full(vals.shape[0], base[class_idx])
            else:
                base_for_class = np.array([float(base)])
        elif vals.ndim == 2:
            vals_for_class = vals
            base_for_class = np.ravel(base)
        else:
            vals_for_class = np.atleast_2d(vals)
            base_for_class = np.ravel(base)

        return vals_for_class, base_for_class

    # Case B: raw shap_values (list or ndarray from explainer.shap_values(X))
    if isinstance(shap_out, list):
        # List of arrays [class_0, class_1]
        vals_for_class = np.atleast_2d(shap_out[class_idx])
    elif isinstance(shap_out, np.ndarray):
        if shap_out.ndim == 3:
            vals_for_class = shap_out[:, :, class_idx]
        else:
            vals_for_class = np.atleast_2d(shap_out)
    else:
        vals_for_class = np.atleast_2d(shap_out)

    # Base values from explainer.expected_value
    exp_val = getattr(explainer, "expected_value", 0.5)
    if isinstance(exp_val, (list, tuple, np.ndarray)):
        arr = np.array(exp_val)
        if len(arr) > class_idx:
            base_scalar = float(arr[class_idx])
        else:
            base_scalar = float(arr[0])
    else:
        base_scalar = float(exp_val)

    base_for_class = np.full(vals_for_class.shape[0], base_scalar)
    return vals_for_class, base_for_class


# ---------------------------------------------------------------------------
# 3. Calculating SHAP Values
# ---------------------------------------------------------------------------

def calculate_shap_values(
    X_transformed: Union[np.ndarray, pd.DataFrame],
    explainer: Optional[shap.TreeExplainer] = None,
    model: Optional[Any] = None,
    class_index: int = 1,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculate SHAP values for preprocessed feature matrix X_transformed.

    Args:
        X_transformed: Preprocessed feature matrix (N, num_features) produced
                       by the existing pipeline.
        explainer: Optional pre-created TreeExplainer instance.
        model: Optional trained RandomForest model (used if explainer is None).
        class_index: Target class index to explain (default 1 for late payment).

    Returns:
        Tuple of:
        - shap_matrix: 2D numpy array (N, num_features) of SHAP values for class_index.
        - base_values: 1D numpy array (N,) of base values for class_index.
    """
    if explainer is None:
        explainer = create_shap_explainer(model=model)

    # Ensure 2D numpy array
    if isinstance(X_transformed, pd.DataFrame):
        X_arr = X_transformed.to_numpy()
    else:
        X_arr = np.atleast_2d(X_transformed)

    # Call explainer
    shap_out = explainer(X_arr)
    return _parse_shap_output(shap_out, explainer, class_idx=class_index)


# ---------------------------------------------------------------------------
# 4. Explaining a Single Invoice
# ---------------------------------------------------------------------------

def explain_single_invoice(
    invoice_features: Union[np.ndarray, pd.DataFrame, Dict[str, Any]],
    pipeline: Optional[Any] = None,
    model: Optional[Any] = None,
    explainer: Optional[shap.TreeExplainer] = None,
    feature_names: Optional[List[str]] = None,
    class_index: int = 1,
    top_k: int = 5,
) -> Dict[str, Any]:
    """
    Generate complete SHAP explanation for a single invoice prediction.

    Reuses existing preprocessing pipeline if raw features are passed,
    or operates directly on preprocessed features.

    Args:
        invoice_features: Either raw invoice dict / single-row DataFrame,
                          OR a preprocessed 1D/2D array (1, 17).
        pipeline: Existing fitted preprocessing pipeline (optional).
        model: Existing trained RandomForestClassifier (optional).
        explainer: Existing TreeExplainer (optional).
        feature_names: Exact list of feature names (optional).
        class_index: Target class index (1 = late payment).
        top_k: Number of top driving and protective factors to return.

    Returns:
        Structured explanation dict containing:
        - base_value: Baseline probability (expected value).
        - predicted_probability: Model's predicted late payment probability.
        - shap_values: Dict mapping feature_name -> shap_value.
        - top_risk_drivers: Top features pushing prediction towards late payment.
        - top_protective_factors: Top features pushing prediction towards on-time.
        - all_contributions: Full sorted list of feature contributions.
    """
    clf = model or load_prediction_model()
    pipe = pipeline or load_preprocessing_pipeline()
    fnames = feature_names or get_feature_names(pipeline=pipe)

    # If raw dictionary or raw DataFrame, reuse existing pipeline.transform (NO duplicate logic)
    if isinstance(invoice_features, dict):
        raw_df = pd.DataFrame([invoice_features])
        # Standardize boolean strings ('Yes'/'No', 'True'/'False') to 1/0 for boolean flag columns
        for col in ["disputed", "paperless_bill"]:
            if col in raw_df.columns:
                raw_df[col] = raw_df[col].apply(
                    lambda v: 1 if (isinstance(v, bool) and v) or str(v).strip().lower() in ("true", "1", "yes", "y", "t") else 0
                )
        X_trans = pipe.transform(raw_df)
    elif isinstance(invoice_features, pd.DataFrame) and invoice_features.shape[1] != len(fnames):
        raw_df = invoice_features.copy()
        for col in ["disputed", "paperless_bill"]:
            if col in raw_df.columns:
                raw_df[col] = raw_df[col].apply(
                    lambda v: 1 if (isinstance(v, bool) and v) or str(v).strip().lower() in ("true", "1", "yes", "y", "t") else 0
                )
        X_trans = pipe.transform(raw_df)
    else:
        if isinstance(invoice_features, pd.DataFrame):
            X_trans = invoice_features.to_numpy()
        else:
            X_trans = np.atleast_2d(invoice_features)

    # Compute model predicted probability for sanity alignment
    try:
        probs = clf.predict_proba(X_trans)[0]
        classes = list(getattr(clf, "classes_", [0, 1]))
        target_idx = classes.index(1) if 1 in classes else (classes.index(True) if True in classes else class_index)
        predicted_proba = float(probs[target_idx])
    except Exception:
        predicted_proba = 0.5

    # Compute SHAP values
    shap_vals_2d, base_vals = calculate_shap_values(
        X_transformed=X_trans,
        explainer=explainer,
        model=clf,
        class_index=class_index,
    )

    sample_shap = shap_vals_2d[0]
    base_val = float(base_vals[0])

    # Align SHAP values with feature names
    shap_dict: Dict[str, float] = {}
    contributions: List[Dict[str, Any]] = []

    for idx, name in enumerate(fnames):
        val = float(sample_shap[idx]) if idx < len(sample_shap) else 0.0
        shap_dict[name] = round(val, 6)
        raw_val = float(X_trans[0, idx]) if idx < X_trans.shape[1] else None

        impact = "increases_risk" if val > 0 else ("decreases_risk" if val < 0 else "neutral")
        contributions.append({
            "feature": name,
            "shap_value": round(val, 6),
            "feature_value": round(raw_val, 4) if raw_val is not None else None,
            "impact": impact,
            "abs_impact": round(abs(val), 6),
        })

    # Sort contributions by absolute impact
    contributions.sort(key=lambda item: item["abs_impact"], reverse=True)

    # Top risk drivers (positive SHAP pushing probability UP)
    risk_drivers = [c for c in contributions if c["shap_value"] > 0]
    risk_drivers.sort(key=lambda item: item["shap_value"], reverse=True)

    # Top protective factors (negative SHAP pushing probability DOWN)
    protective_factors = [c for c in contributions if c["shap_value"] < 0]
    protective_factors.sort(key=lambda item: item["shap_value"])

    return {
        "base_value": round(base_val, 4),
        "predicted_probability": round(predicted_proba, 4),
        "shap_values": shap_dict,
        "top_risk_drivers": risk_drivers[:top_k],
        "top_protective_factors": protective_factors[:top_k],
        "all_contributions": contributions,
    }


# ---------------------------------------------------------------------------
# 5. Global Feature Importance
# ---------------------------------------------------------------------------

def get_global_feature_importance(
    X_transformed: Union[np.ndarray, pd.DataFrame],
    explainer: Optional[shap.TreeExplainer] = None,
    model: Optional[Any] = None,
    feature_names: Optional[List[str]] = None,
    class_index: int = 1,
) -> List[Dict[str, Any]]:
    """
    Calculate global feature importance based on mean absolute SHAP values:
    importance_j = (1/N) * sum(|SHAP_{i, j}|).

    Args:
        X_transformed: 2D array or DataFrame of preprocessed samples (N, num_features).
        explainer: Optional TreeExplainer.
        model: Optional trained RandomForest model.
        feature_names: Optional feature names list.
        class_index: Target class (1 = late payment).

    Returns:
        Sorted list of dicts: [{"feature": name, "importance": mean_abs_val}, ...]
    """
    pipe = load_preprocessing_pipeline()
    fnames = feature_names or get_feature_names(pipeline=pipe)

    shap_matrix, _ = calculate_shap_values(
        X_transformed=X_transformed,
        explainer=explainer,
        model=model,
        class_index=class_index,
    )

    # Mean absolute value per feature across samples
    mean_abs = np.mean(np.abs(shap_matrix), axis=0)

    importance_list = []
    for idx, name in enumerate(fnames):
        imp = float(mean_abs[idx]) if idx < len(mean_abs) else 0.0
        importance_list.append({
            "feature": name,
            "importance": round(imp, 6),
        })

    # Sort descending by importance
    importance_list.sort(key=lambda item: item["importance"], reverse=True)
    return importance_list


def get_top_n_features(
    X_transformed: Optional[Union[np.ndarray, pd.DataFrame]] = None,
    n: int = 10,
    explainer: Optional[shap.TreeExplainer] = None,
    model: Optional[Any] = None,
    feature_names: Optional[List[str]] = None,
    class_index: int = 1,
    as_dataframe: bool = False,
) -> Union[List[Dict[str, Any]], pd.DataFrame]:
    """
    Returns the top N most important features based on mean absolute SHAP value.

    Output format (table-ready):
        Feature | Mean Absolute SHAP Value

    Args:
        X_transformed: Preprocessed feature matrix (N, num_features). If None,
                       loads representative records from the default dataset.
        n: Number of top features to return (default 10).
        explainer: Optional TreeExplainer instance.
        model: Optional trained Random Forest model.
        feature_names: Optional feature names list.
        class_index: Target class (default 1 for late payment).
        as_dataframe: If True, returns a pandas DataFrame; otherwise list of dicts.

    Returns:
        List of dicts or DataFrame containing 'Feature' and 'Mean Absolute SHAP Value'.
    """
    if X_transformed is None:
        X_transformed, _ = load_default_dataset_preprocessed(sample_size=500)

    all_importances = get_global_feature_importance(
        X_transformed=X_transformed,
        explainer=explainer,
        model=model,
        feature_names=feature_names,
        class_index=class_index,
    )

    top_n = all_importances[:n]
    formatted = [
        {
            "Feature": item["feature"],
            "Mean Absolute SHAP Value": item["importance"],
        }
        for item in top_n
    ]

    if as_dataframe:
        return pd.DataFrame(formatted)

    return formatted


# ---------------------------------------------------------------------------
# 6. Global SHAP Plot Generation
# ---------------------------------------------------------------------------

def load_default_dataset_preprocessed(
    dataset_path: Optional[str] = None,
    sample_size: int = 500,
) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
    """
    Load and preprocess records from the default Accounts Receivable Excel dataset
    using the existing preprocessing pipeline (zero duplicate logic).
    """
    path = dataset_path or os.path.join(os.getcwd(), "datasets", "AR_dataset_final_processed_sy.xlsx")
    if not os.path.isfile(path):
        # Also check relative to backend directory
        alt_path = os.path.join(os.getcwd(), "backend", "datasets", "AR_dataset_final_processed_sy.xlsx")
        if os.path.isfile(alt_path):
            path = alt_path
        else:
            raise FileNotFoundError(f"Dataset file not found at: {path}")

    df_raw = pd.read_excel(path)
    sample_df = df_raw.head(sample_size) if sample_size and sample_size < len(df_raw) else df_raw

    invoices = []
    for _, row in sample_df.iterrows():
        inv = {
            "customer_id": str(row.get("customerID", "")),
            "invoice_amount": float(row.get("InvoiceAmount", 0.0)),
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
        invoices.append(inv)

    pipe = load_preprocessing_pipeline()
    X_transformed = pipe.transform(pd.DataFrame(invoices))
    return X_transformed, invoices


def generate_global_shap_plots(
    X_transformed: Optional[Union[np.ndarray, pd.DataFrame]] = None,
    output_dir: Optional[str] = None,
    explainer: Optional[shap.TreeExplainer] = None,
    model: Optional[Any] = None,
    feature_names: Optional[List[str]] = None,
    class_index: int = 1,
    dpi: int = 300,
) -> Dict[str, str]:
    """
    Generate and save both global SHAP plots:
      1. shap_summary.png: Beeswarm summary plot showing impact distribution
      2. shap_feature_importance.png: Bar chart showing mean absolute SHAP values

    Args:
        X_transformed: Preprocessed feature matrix. If None, loaded from dataset.
        output_dir: Directory where plots should be saved (defaults to 'reports/shap').
        explainer: Optional TreeExplainer.
        model: Optional Random Forest model.
        feature_names: Optional feature names list.
        class_index: Target class (1 = late payment).
        dpi: Resolution of saved image files.

    Returns:
        Dict mapping plot name to saved absolute filepath:
        {"summary_plot": path, "feature_importance_plot": path}
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    target_dir = output_dir or os.path.join(os.getcwd(), "reports", "shap")
    os.makedirs(target_dir, exist_ok=True)

    if X_transformed is None:
        X_transformed, _ = load_default_dataset_preprocessed(sample_size=500)

    pipe = load_preprocessing_pipeline()
    fnames = feature_names or get_feature_names(pipeline=pipe)

    shap_matrix, _ = calculate_shap_values(
        X_transformed=X_transformed,
        explainer=explainer,
        model=model,
        class_index=class_index,
    )

    summary_filename = os.path.join(target_dir, "shap_summary.png")
    bar_filename = os.path.join(target_dir, "shap_feature_importance.png")

    # 1. SHAP Beeswarm Summary Plot
    plt.figure(figsize=(10, 6))
    shap.summary_plot(shap_matrix, X_transformed, feature_names=fnames, show=False)
    plt.title("SHAP Summary Plot - Random Forest Payment Delay Model", fontsize=13, pad=12)
    plt.tight_layout()
    plt.savefig(summary_filename, dpi=dpi, bbox_inches="tight")
    plt.close()

    # 2. SHAP Bar Feature Importance Plot
    plt.figure(figsize=(10, 6))
    shap.summary_plot(shap_matrix, X_transformed, feature_names=fnames, plot_type="bar", show=False)
    plt.title("SHAP Global Feature Importance (Mean |SHAP|)", fontsize=13, pad=12)
    plt.tight_layout()
    plt.savefig(bar_filename, dpi=dpi, bbox_inches="tight")
    plt.close()

    return {
        "summary_plot": os.path.abspath(summary_filename),
        "feature_importance_plot": os.path.abspath(bar_filename),
    }
