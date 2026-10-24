import React, { useState, useEffect, useRef } from 'react';
import {
  Calculator,
  Building2,
  DollarSign,
  Calendar,
  AlertCircle,
  CheckCircle2,
  Clock,
  Sparkles,
  ArrowRight,
  TrendingUp,
  TrendingDown,
  ShieldCheck,
  HelpCircle,
  BarChart3,
  Info,
  AlertTriangle,
  RotateCcw,
  Search,
  Landmark,
} from 'lucide-react';
import { predictInvoicePayment, getPredictionCompanies } from '../services/api/invoiceApi';
import { formatCurrency, formatDate } from '../utils/formatters';
import { useDataset } from '../context/DatasetContext';

const FEATURE_METADATA = {
  customer_avg_dayslate: {
    label: 'Customer Historical Delay',
    explainIncrease: "Customer average days late increased the model's late-payment prediction.",
    explainDecrease: "Customer prompt payment history decreased the model's late-payment prediction.",
  },
  disputed: {
    label: 'Invoice Dispute Status',
    explainIncrease: "Active invoice dispute increased the model's late-payment prediction.",
    explainDecrease: "Absence of an invoice dispute decreased the model's late-payment prediction.",
  },
  invoice_amount: {
    label: 'Invoice Transaction Amount',
    explainIncrease: "Higher invoice transaction amount increased the model's late-payment prediction.",
    explainDecrease: "Lower invoice transaction amount decreased the model's late-payment prediction.",
  },
  customer_dispute_rate: {
    label: 'Customer Dispute Frequency',
    explainIncrease: "Customer historical dispute rate increased the model's late-payment prediction.",
    explainDecrease: "Low customer historical dispute rate decreased the model's late-payment prediction.",
  },
  customer_risk_drift: {
    label: 'Payment Trend Drift',
    explainIncrease: "Recent shift in customer payment pattern increased the model's late-payment prediction.",
    explainDecrease: "Consistent payment pattern decreased the model's late-payment prediction.",
  },
  country_avg_dayslate: {
    label: 'Regional Payment Delay Baseline',
    explainIncrease: "Regional average settlement timeline increased the model's late-payment prediction.",
    explainDecrease: "Favorable regional payment baseline decreased the model's late-payment prediction.",
  },
  invoice_month: {
    label: 'Billing Month Seasonality',
    explainIncrease: "Seasonal billing month timing increased the model's late-payment prediction.",
    explainDecrease: "Favorable billing month timing decreased the model's late-payment prediction.",
  },
  invoice_weekday: {
    label: 'Invoice Day of Week',
    explainIncrease: "Day-of-week invoice timing increased the model's late-payment prediction.",
    explainDecrease: "Favorable day-of-week timing decreased the model's late-payment prediction.",
  },
  invoice_quarter: {
    label: 'Fiscal Quarter Timing',
    explainIncrease: "Fiscal quarter financial cycle timing increased the model's late-payment prediction.",
    explainDecrease: "Favorable quarterly timing decreased the model's late-payment prediction.",
  },
  payment_term_days: {
    label: 'Agreed Payment Terms',
    explainIncrease: "Longer payment credit terms increased the model's late-payment prediction.",
    explainDecrease: "Standard payment credit terms decreased the model's late-payment prediction.",
  },
  days_to_due: {
    label: 'Days Until Due Date',
    explainIncrease: "Payment due date window increased the model's late-payment prediction.",
    explainDecrease: "Payment due date window decreased the model's late-payment prediction.",
  },
  paperless_bill: {
    label: 'Paperless Billing Format',
    explainIncrease: "Billing format contributed toward the model's late-payment prediction.",
    explainDecrease: "Electronic billing format decreased the model's late-payment prediction.",
  },
};

const getFeatureLabel = (featureKey) => {
  if (FEATURE_METADATA[featureKey]) {
    return FEATURE_METADATA[featureKey].label;
  }
  if (typeof featureKey === 'string' && featureKey.startsWith('country_code_')) {
    return `Regional Code: ${featureKey.replace('country_code_', '')}`;
  }
  return typeof featureKey === 'string'
    ? featureKey.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    : String(featureKey);
};

const getFeatureExplanation = (featureKey, isRiskIncrease) => {
  const meta = FEATURE_METADATA[featureKey];
  if (meta) {
    return isRiskIncrease ? meta.explainIncrease : meta.explainDecrease;
  }
  const label = getFeatureLabel(featureKey);
  return isRiskIncrease
    ? `${label} increased the model's late-payment prediction.`
    : `${label} decreased the model's late-payment prediction.`;
};

export const PredictInvoiceSection = ({ onPredictionSuccess }) => {
  // Today's date and default +30 days due date in YYYY-MM-DD
  const todayStr = new Date().toISOString().split('T')[0];
  const defaultDueStr = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

  const { monthlyInflows, setMonthlyInflow, getMonthlyInflow, addPredictedInvoice } = useDataset();

  // Due Month calculation helpers
  const getDueMonthKey = (dStr) => {
    if (!dStr) return '2026-11';
    return String(dStr).substring(0, 7);
  };

  const getDueMonthName = (dStr) => {
    if (!dStr) return 'November 2026';
    try {
      const d = new Date(dStr + 'T00:00:00');
      return !isNaN(d.getTime())
        ? d.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
        : String(dStr).substring(0, 7);
    } catch {
      return String(dStr).substring(0, 7);
    }
  };

  // Form input state
  const [companyName, setCompanyName] = useState('');
  const [invoiceAmount, setInvoiceAmount] = useState('');
  const [orderDate, setOrderDate] = useState(todayStr);
  const [dueDate, setDueDate] = useState(defaultDueStr);

  const currentDueMonthKey = getDueMonthKey(dueDate);
  const currentDueMonthName = getDueMonthName(dueDate);

  // Expected Inflow for the month state (pre-filled from stored month value if available)
  const [expectedInflow, setExpectedInflow] = useState(() => {
    const stored = getMonthlyInflow ? getMonthlyInflow(getDueMonthKey(defaultDueStr)) : 0;
    return stored > 0 ? String(stored) : '100000';
  });
  const [inflowManuallyEdited, setInflowManuallyEdited] = useState(false);

  // Whenever due date changes, use the expected inflow associated with that other month
  useEffect(() => {
    const key = getDueMonthKey(dueDate);
    const stored = getMonthlyInflow ? getMonthlyInflow(key) : 0;
    if (stored > 0) {
      setExpectedInflow(String(stored));
      setInflowManuallyEdited(false);
    } else if (!inflowManuallyEdited) {
      setExpectedInflow('100000');
    }
  }, [dueDate, monthlyInflows]);

  // Available companies for searchable dropdown / autocomplete
  const [availableCompanies, setAvailableCompanies] = useState([]);
  const [filteredCompanies, setFilteredCompanies] = useState([]);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);

  // Interaction & loading states
  const [loading, setLoading] = useState(false);
  const [formErrors, setFormErrors] = useState({});
  const [serverError, setServerError] = useState('');
  const [predictionResult, setPredictionResult] = useState(null);

  // Fetch available companies on mount
  useEffect(() => {
    let isMounted = true;
    getPredictionCompanies()
      .then((companies) => {
        if (isMounted && Array.isArray(companies)) {
          setAvailableCompanies(companies);
        }
      })
      .catch((err) => {
        console.warn('Failed to load companies list:', err);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // Filter companies when typing in company name
  useEffect(() => {
    if (!companyName.trim()) {
      setFilteredCompanies(availableCompanies.slice(0, 8));
    } else {
      const q = companyName.trim().toLowerCase();
      const matched = availableCompanies.filter((c) =>
        c.company_name.toLowerCase().includes(q)
      );
      setFilteredCompanies(matched.slice(0, 8));
    }
  }, [companyName, availableCompanies]);

  // Click outside to close dropdown
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setIsDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Form Validation
  const validateForm = () => {
    const errors = {};
    if (!companyName || !companyName.trim()) {
      errors.companyName = 'Company name is required.';
    }

    const amountNum = parseFloat(invoiceAmount);
    if (!invoiceAmount || isNaN(amountNum)) {
      errors.invoiceAmount = 'Invoice amount is required and must be a valid number.';
    } else if (amountNum <= 0) {
      errors.invoiceAmount = 'Invoice amount must be greater than zero.';
    }

    if (!orderDate) {
      errors.orderDate = 'Order date is required.';
    }

    if (!dueDate) {
      errors.dueDate = 'Due date is required.';
    } else if (orderDate && new Date(dueDate) < new Date(orderDate)) {
      errors.dueDate = 'Due date cannot be earlier than the order date.';
    }

    const inflowNum = parseFloat(expectedInflow);
    if (expectedInflow !== '' && (isNaN(inflowNum) || inflowNum < 0)) {
      errors.expectedInflow = 'Expected inflow must be a valid non-negative amount.';
    }

    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  // Submit Handler
  const handlePredict = async (e) => {
    if (e) e.preventDefault();
    setServerError('');

    if (!validateForm()) {
      return;
    }

    setLoading(true);

    try {
      const invoiceId = 'INV-' + Date.now();
      const inflowVal = parseFloat(expectedInflow) >= 0 ? parseFloat(expectedInflow) : 100000;
      const payload = {
        company_name: companyName.trim(),
        invoice_amount: parseFloat(invoiceAmount),
        order_date: orderDate,
        due_date: dueDate,
        expected_inflow: inflowVal,
        invoice_id: invoiceId,
      };

      const result = await predictInvoicePayment(payload);
      setPredictionResult(result);
      setFormErrors({});

      // Store expected inflow for this specific due date month
      if (setMonthlyInflow) {
        setMonthlyInflow(currentDueMonthKey, inflowVal);
      }

      // Record invoice into dataset context
      if (addPredictedInvoice) {
        addPredictedInvoice({
          id: invoiceId,
          invoice_id: invoiceId,
          customer: companyName.trim(),
          customerName: companyName.trim(),
          amount: parseFloat(invoiceAmount),
          invoice_amount: parseFloat(invoiceAmount),
          order_date: orderDate,
          invoiceDate: orderDate,
          due_date: dueDate,
          dueDate: dueDate,
          due_month: currentDueMonthKey,
          risk_level: result.risk_level,
          riskLevel: result.risk_level,
          risk_score: result.risk_score,
          riskScore: result.risk_score,
          risk_probability: result.risk_probability,
          predictedDelayDays: result.predicted_delay_days,
          predicted_delay_days: result.predicted_delay_days,
          expected_payment_date: result.expected_payment_date,
          shap_values: result.shap_values,
          shap_explanation: {
            shap_values: result.shap_values,
            top_increasing: result.top_features_increasing_risk,
            top_decreasing: result.top_features_decreasing_risk,
          },
        });
      }

      if (onPredictionSuccess) {
        onPredictionSuccess(result);
      }
    } catch (err) {
      const detail = err?.data?.detail || err?.message || 'Failed to generate prediction. Please check inputs.';
      setServerError(detail);
    } finally {
      setLoading(false);
    }
  };

  // Quick select company handler
  const handleSelectCompany = (comp) => {
    setCompanyName(comp.company_name);
    setIsDropdownOpen(false);
    if (formErrors.companyName) {
      setFormErrors((prev) => ({ ...prev, companyName: null }));
    }
  };

  // Reset form handler
  const handleReset = () => {
    setCompanyName('');
    setInvoiceAmount('');
    setOrderDate(todayStr);
    setDueDate(defaultDueStr);
    const stored = getMonthlyInflow ? getMonthlyInflow(getDueMonthKey(defaultDueStr)) : 0;
    setExpectedInflow(stored > 0 ? String(stored) : '100000');
    setInflowManuallyEdited(false);
    setFormErrors({});
    setServerError('');
    setPredictionResult(null);
  };

  // Format probability as clean %
  const probPercent = predictionResult
    ? Math.round((predictionResult.risk_probability || 0) * 100)
    : 0;

  // Determine risk card accent colors
  // Normalize risk level string to handle any casing from the backend
  const riskLevelNorm = (predictionResult?.risk_level || '').toLowerCase();
  const isHighRisk = riskLevelNorm.includes('high');
  const isMediumRisk = riskLevelNorm.includes('medium');
  const isLowRisk = !isHighRisk && !isMediumRisk;
  const riskColor = isHighRisk
    ? 'var(--risk-high, #ef4444)'
    : isMediumRisk
    ? 'var(--risk-medium, #f59e0b)'
    : 'var(--risk-low, #10b981)';
  const riskBg = isHighRisk
    ? 'rgba(239, 68, 68, 0.1)'
    : isMediumRisk
    ? 'rgba(245, 158, 11, 0.1)'
    : 'rgba(16, 185, 129, 0.1)';
  const riskBorder = isHighRisk
    ? 'rgba(239, 68, 68, 0.3)'
    : isMediumRisk
    ? 'rgba(245, 158, 11, 0.3)'
    : 'rgba(16, 185, 129, 0.3)';

  // Extract SHAP explainability data from predictionResult
  const increasingFactors = predictionResult?.top_features_increasing_risk || [];
  const decreasingFactors = predictionResult?.top_features_decreasing_risk || [];

  // Build sorted list for SHAP feature importance bar chart
  const shapValuesMap = predictionResult?.shap_values || {};
  const shapBarItems = Object.entries(shapValuesMap)
    .map(([feature, val]) => ({ feature, shap_value: Number(val) }))
    .filter((item) => Math.abs(item.shap_value) > 0.0001)
    .sort((a, b) => Math.abs(b.shap_value) - Math.abs(a.shap_value))
    .slice(0, 10);

  const maxShapAbs = Math.max(
    ...(shapBarItems.length > 0 ? shapBarItems.map((item) => Math.abs(item.shap_value)) : [0.05]),
    0.05
  );

  return (
    <div
      className="card predict-invoice-section"
      style={{
        marginBottom: '1.75rem',
        border: '1px solid var(--border-subtle)',
        boxShadow: 'var(--shadow-card)',
        background: 'var(--bg-surface)',
        borderRadius: 'var(--radius-lg, 0.75rem)',
        overflow: 'hidden',
      }}
    >
      {/* Section Header */}
      <div
        className="card-header"
        style={{
          borderBottom: '1px solid var(--border-subtle)',
          padding: '1.15rem 1.5rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '0.75rem',
          background: 'linear-gradient(90deg, rgba(124, 58, 237, 0.05) 0%, transparent 100%)',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                background: 'var(--primary-subtle)',
                color: 'var(--primary)',
                border: '1px solid var(--border-subtle)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Calculator size={18} />
            </div>
            <h3
              className="card-title"
              style={{
                fontSize: '1.15rem',
                fontWeight: 700,
                color: 'var(--text-primary)',
                margin: 0,
              }}
            >
              Predict Invoice Payment Risk
            </h3>
          </div>
          <p
            className="card-subtitle"
            style={{
              fontSize: '0.82rem',
              color: 'var(--text-secondary)',
              marginTop: '0.25rem',
            }}
          >
            Enter invoice details to predict payment delays, risk level, and cash collection date using historical risk models.
          </p>
        </div>

        {availableCompanies.length > 0 && (
          <div
            style={{
              fontSize: '0.75rem',
              color: 'var(--text-secondary)',
              backgroundColor: 'var(--bg-surface-subtle)',
              padding: '0.35rem 0.75rem',
              borderRadius: '9999px',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <strong style={{ color: 'var(--primary)' }}>{availableCompanies.length}</strong> Historical Companies Indexed
          </div>
        )}
      </div>

      {/* Card Body with Grid Layout */}
      <div style={{ padding: '1.5rem' }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: predictionResult ? 'repeat(auto-fit, minmax(320px, 1fr))' : '1fr',
            gap: '1.5rem',
            alignItems: 'start',
          }}
        >
          {/* Form Side */}
          <form onSubmit={handlePredict}>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                gap: '1.1rem',
              }}
            >
              {/* 1. Company Name Field */}
              <div style={{ position: 'relative' }} ref={dropdownRef}>
                <label
                  style={{
                    display: 'block',
                    fontSize: '0.82rem',
                    fontWeight: 600,
                    color: 'var(--text-primary, #f8fafc)',
                    marginBottom: '0.4rem',
                  }}
                >
                  Company Name <span style={{ color: 'var(--risk-high, #ef4444)' }}>*</span>
                </label>
                <div style={{ position: 'relative' }}>
                  <div
                    style={{
                      position: 'absolute',
                      left: '0.75rem',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      color: 'var(--text-muted, #64748b)',
                      pointerEvents: 'none',
                      display: 'flex',
                    }}
                  >
                    <Building2 size={16} />
                  </div>
                  <input
                    type="text"
                    className="filter-select"
                    id="predict-company-name-input"
                    placeholder="Search or enter company name..."
                    value={companyName}
                    onChange={(e) => {
                      setCompanyName(e.target.value);
                      setIsDropdownOpen(true);
                      if (formErrors.companyName) {
                        setFormErrors((prev) => ({ ...prev, companyName: null }));
                      }
                    }}
                    onFocus={() => setIsDropdownOpen(true)}
                    style={{
                      width: '100%',
                      paddingLeft: '2.3rem',
                      height: '42px',
                      borderRadius: 'var(--radius-md, 0.5rem)',
                      border: formErrors.companyName
                        ? '1px solid var(--risk-high, #ef4444)'
                        : '1px solid var(--border-light, #334155)',
                      backgroundColor: 'var(--bg-surface-subtle, #0f172a)',
                      color: 'var(--text-primary, #f8fafc)',
                      fontSize: '0.875rem',
                    }}
                  />
                </div>

                {/* Company Autocomplete Dropdown */}
                {isDropdownOpen && filteredCompanies.length > 0 && (
                  <div
                    style={{
                      position: 'absolute',
                      top: '100%',
                      left: 0,
                      right: 0,
                      zIndex: 50,
                      marginTop: '4px',
                      backgroundColor: 'var(--bg-surface, #1e293b)',
                      border: '1px solid var(--border-light, #334155)',
                      borderRadius: 'var(--radius-md, 0.5rem)',
                      boxShadow: 'var(--shadow-lg, 0 10px 15px -3px rgba(0, 0, 0, 0.3))',
                      maxHeight: '220px',
                      overflowY: 'auto',
                    }}
                  >
                    <div
                      style={{
                        padding: '0.4rem 0.75rem',
                        fontSize: '0.7rem',
                        textTransform: 'uppercase',
                        color: 'var(--text-muted, #64748b)',
                        borderBottom: '1px solid var(--border-subtle, #334155)',
                      }}
                    >
                      Available Historical Companies
                    </div>
                    {filteredCompanies.map((comp) => (
                      <div
                        key={comp.company_name}
                        onClick={() => handleSelectCompany(comp)}
                        style={{
                          padding: '0.6rem 0.75rem',
                          cursor: 'pointer',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          fontSize: '0.82rem',
                          color: 'var(--text-primary, #f8fafc)',
                          borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                          transition: 'background 0.15s ease',
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = 'var(--bg-surface-subtle, #0f172a)';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = 'transparent';
                        }}
                      >
                        <span style={{ fontWeight: 600 }}>{comp.company_name}</span>
                        <span
                          style={{
                            fontSize: '0.72rem',
                            color: comp.avg_delay_days > 3 ? 'var(--risk-high, #ef4444)' : 'var(--risk-low, #10b981)',
                          }}
                        >
                          Avg delay: {comp.avg_delay_days}d ({comp.historical_invoices_count || 1} inv)
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                {formErrors.companyName && (
                  <p style={{ color: 'var(--risk-high, #ef4444)', fontSize: '0.75rem', marginTop: '0.3rem' }}>
                    {formErrors.companyName}
                  </p>
                )}
              </div>

              {/* 2. Invoice Amount Field */}
              <div>
                <label
                  style={{
                    display: 'block',
                    fontSize: '0.82rem',
                    fontWeight: 600,
                    color: 'var(--text-primary, #f8fafc)',
                    marginBottom: '0.4rem',
                  }}
                >
                  Invoice Amount ($) <span style={{ color: 'var(--risk-high, #ef4444)' }}>*</span>
                </label>
                <div style={{ position: 'relative' }}>
                  <div
                    style={{
                      position: 'absolute',
                      left: '0.75rem',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      color: 'var(--text-muted, #64748b)',
                      pointerEvents: 'none',
                      display: 'flex',
                    }}
                  >
                    <DollarSign size={16} />
                  </div>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    className="filter-select"
                    id="predict-invoice-amount-input"
                    placeholder="e.g. 50000"
                    value={invoiceAmount}
                    onChange={(e) => {
                      setInvoiceAmount(e.target.value);
                      if (formErrors.invoiceAmount) {
                        setFormErrors((prev) => ({ ...prev, invoiceAmount: null }));
                      }
                    }}
                    style={{
                      width: '100%',
                      paddingLeft: '2.3rem',
                      height: '42px',
                      borderRadius: 'var(--radius-md, 0.5rem)',
                      border: formErrors.invoiceAmount
                        ? '1px solid var(--risk-high, #ef4444)'
                        : '1px solid var(--border-light, #334155)',
                      backgroundColor: 'var(--bg-surface-subtle, #0f172a)',
                      color: 'var(--text-primary, #f8fafc)',
                      fontSize: '0.875rem',
                      fontWeight: 600,
                    }}
                  />
                </div>
                {formErrors.invoiceAmount && (
                  <p style={{ color: 'var(--risk-high, #ef4444)', fontSize: '0.75rem', marginTop: '0.3rem' }}>
                    {formErrors.invoiceAmount}
                  </p>
                )}
              </div>

              {/* 3. Order Date Field */}
              <div>
                <label
                  style={{
                    display: 'block',
                    fontSize: '0.82rem',
                    fontWeight: 600,
                    color: 'var(--text-primary, #f8fafc)',
                    marginBottom: '0.4rem',
                  }}
                >
                  Order Date <span style={{ color: 'var(--risk-high, #ef4444)' }}>*</span>
                </label>
                <div style={{ position: 'relative' }}>
                  <div
                    style={{
                      position: 'absolute',
                      left: '0.75rem',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      color: 'var(--text-muted, #64748b)',
                      pointerEvents: 'none',
                      display: 'flex',
                    }}
                  >
                    <Calendar size={16} />
                  </div>
                  <input
                    type="date"
                    className="filter-select"
                    id="predict-order-date-input"
                    value={orderDate}
                    onChange={(e) => {
                      setOrderDate(e.target.value);
                      if (formErrors.orderDate) {
                        setFormErrors((prev) => ({ ...prev, orderDate: null }));
                      }
                    }}
                    style={{
                      width: '100%',
                      paddingLeft: '2.3rem',
                      height: '42px',
                      borderRadius: 'var(--radius-md, 0.5rem)',
                      border: formErrors.orderDate
                        ? '1px solid var(--risk-high, #ef4444)'
                        : '1px solid var(--border-light, #334155)',
                      backgroundColor: 'var(--bg-surface-subtle, #0f172a)',
                      color: 'var(--text-primary, #f8fafc)',
                      fontSize: '0.875rem',
                    }}
                  />
                </div>
                {formErrors.orderDate && (
                  <p style={{ color: 'var(--risk-high, #ef4444)', fontSize: '0.75rem', marginTop: '0.3rem' }}>
                    {formErrors.orderDate}
                  </p>
                )}
              </div>

              {/* 4. Due Date Field */}
              <div>
                <label
                  style={{
                    display: 'block',
                    fontSize: '0.82rem',
                    fontWeight: 600,
                    color: 'var(--text-primary, #f8fafc)',
                    marginBottom: '0.4rem',
                  }}
                >
                  Due Date <span style={{ color: 'var(--risk-high, #ef4444)' }}>*</span>
                </label>
                <div style={{ position: 'relative' }}>
                  <div
                    style={{
                      position: 'absolute',
                      left: '0.75rem',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      color: 'var(--text-muted, #64748b)',
                      pointerEvents: 'none',
                      display: 'flex',
                    }}
                  >
                    <Calendar size={16} />
                  </div>
                  <input
                    type="date"
                    className="filter-select"
                    id="predict-due-date-input"
                    value={dueDate}
                    min={orderDate || undefined}
                    onChange={(e) => {
                      setDueDate(e.target.value);
                      if (formErrors.dueDate) {
                        setFormErrors((prev) => ({ ...prev, dueDate: null }));
                      }
                    }}
                    style={{
                      width: '100%',
                      paddingLeft: '2.3rem',
                      height: '42px',
                      borderRadius: 'var(--radius-md, 0.5rem)',
                      border: formErrors.dueDate
                        ? '1px solid var(--risk-high, #ef4444)'
                        : '1px solid var(--border-light, #334155)',
                      backgroundColor: 'var(--bg-surface-subtle, #0f172a)',
                      color: 'var(--text-primary, #f8fafc)',
                      fontSize: '0.875rem',
                    }}
                  />
                </div>
                {formErrors.dueDate && (
                  <p style={{ color: 'var(--risk-high, #ef4444)', fontSize: '0.75rem', marginTop: '0.3rem' }}>
                    {formErrors.dueDate}
                  </p>
                )}
              </div>

              {/* 5. Expected Inflow for the Month Field */}
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                  <label
                    style={{
                      display: 'block',
                      fontSize: '0.82rem',
                      fontWeight: 600,
                      color: 'var(--text-primary, #f8fafc)',
                      margin: 0,
                    }}
                  >
                    Expected Inflow for Month (₹) <span style={{ color: 'var(--risk-high, #ef4444)' }}>*</span>
                  </label>
                  <span
                    style={{
                      fontSize: '0.7rem',
                      padding: '0.15rem 0.5rem',
                      borderRadius: '9999px',
                      backgroundColor: 'rgba(59, 130, 246, 0.15)',
                      color: '#60a5fa',
                      fontWeight: 600,
                    }}
                  >
                    Due: {currentDueMonthName}
                  </span>
                </div>
                <div style={{ position: 'relative' }}>
                  <div
                    style={{
                      position: 'absolute',
                      left: '0.75rem',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      color: 'var(--text-muted, #64748b)',
                      pointerEvents: 'none',
                      display: 'flex',
                      fontWeight: 700,
                      fontSize: '0.95rem',
                    }}
                  >
                    ₹
                  </div>
                  <input
                    type="number"
                    step="1"
                    min="0"
                    className="filter-select"
                    id="predict-expected-inflow-input"
                    placeholder="e.g. 100000"
                    value={expectedInflow}
                    onChange={(e) => {
                      setExpectedInflow(e.target.value);
                      setInflowManuallyEdited(true);
                      if (formErrors.expectedInflow) {
                        setFormErrors((prev) => ({ ...prev, expectedInflow: null }));
                      }
                    }}
                    style={{
                      width: '100%',
                      paddingLeft: '2.3rem',
                      height: '42px',
                      borderRadius: 'var(--radius-md, 0.5rem)',
                      border: formErrors.expectedInflow
                        ? '1px solid var(--risk-high, #ef4444)'
                        : '1px solid var(--border-light, #334155)',
                      backgroundColor: 'var(--bg-surface-subtle, #0f172a)',
                      color: 'var(--text-primary, #f8fafc)',
                      fontSize: '0.875rem',
                      fontWeight: 600,
                    }}
                  />
                </div>
                {formErrors.expectedInflow && (
                  <p style={{ color: 'var(--risk-high, #ef4444)', fontSize: '0.75rem', marginTop: '0.3rem' }}>
                    {formErrors.expectedInflow}
                  </p>
                )}
                <p style={{ fontSize: '0.7rem', color: 'var(--text-muted, #94a3b8)', marginTop: '0.3rem' }}>
                  Manually entered monthly inflow for {currentDueMonthName}. Not summed from invoices.
                </p>
              </div>
            </div>

            {/* Quick Suggestions for Company Selection */}
            {availableCompanies.length > 0 && (
              <div
                style={{
                  marginTop: '0.85rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  flexWrap: 'wrap',
                }}
              >
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted, #64748b)' }}>
                  Quick select:
                </span>
                {availableCompanies.slice(0, 5).map((c) => (
                  <button
                    key={c.company_name}
                    type="button"
                    onClick={() => handleSelectCompany(c)}
                    style={{
                      background: 'rgba(255, 255, 255, 0.05)',
                      border: '1px solid var(--border-subtle, #334155)',
                      color: 'var(--text-secondary, #94a3b8)',
                      padding: '0.15rem 0.5rem',
                      borderRadius: '4px',
                      fontSize: '0.72rem',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = 'var(--primary, #3b82f6)';
                      e.currentTarget.style.color = 'var(--text-primary, #f8fafc)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = 'var(--border-subtle, #334155)';
                      e.currentTarget.style.color = 'var(--text-secondary, #94a3b8)';
                    }}
                  >
                    {c.company_name}
                  </button>
                ))}
              </div>
            )}

            {/* Server Error Alert Banner */}
            {serverError && (
              <div
                style={{
                  marginTop: '1.1rem',
                  padding: '0.85rem 1rem',
                  borderRadius: 'var(--radius-md, 0.5rem)',
                  backgroundColor: 'rgba(239, 68, 68, 0.12)',
                  border: '1px solid rgba(239, 68, 68, 0.3)',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '0.65rem',
                  color: 'var(--risk-high, #ef4444)',
                  fontSize: '0.82rem',
                  lineHeight: 1.4,
                }}
              >
                <AlertCircle size={17} style={{ flexShrink: 0, marginTop: '2px' }} />
                <div>
                  <strong style={{ display: 'block', marginBottom: '0.15rem' }}>Prediction Error</strong>
                  {serverError}
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div
              style={{
                marginTop: '1.25rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                flexWrap: 'wrap',
              }}
            >
              <button
                type="submit"
                className="btn btn-primary"
                id="predict-payment-submit-btn"
                disabled={loading}
                style={{
                  minWidth: '180px',
                  height: '42px',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.5rem',
                  fontWeight: 600,
                  fontSize: '0.875rem',
                  background: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)',
                  boxShadow: '0 4px 12px rgba(59, 130, 246, 0.3)',
                }}
              >
                {loading ? (
                  <>
                    <div
                      style={{
                        width: '16px',
                        height: '16px',
                        border: '2px solid rgba(255, 255, 255, 0.3)',
                        borderTopColor: '#fff',
                        borderRadius: '50%',
                        animation: 'spin 0.8s linear infinite',
                      }}
                    />
                    Calculating Prediction...
                  </>
                ) : (
                  <>
                    <Sparkles size={16} />
                    Predict Payment
                  </>
                )}
              </button>

              {(companyName || invoiceAmount || predictionResult || serverError) && (
                <button
                  type="button"
                  onClick={handleReset}
                  className="btn btn-secondary"
                  style={{
                    height: '42px',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.4rem',
                    fontSize: '0.82rem',
                  }}
                >
                  <RotateCcw size={14} />
                  Reset Form
                </button>
              )}
            </div>
          </form>

          {/* Prediction Result Card */}
          {predictionResult && (
            <div
              id="prediction-result-card"
              style={{
                borderRadius: 'var(--radius-lg, 0.75rem)',
                backgroundColor: riskBg,
                border: `1.5px solid ${riskBorder}`,
                padding: '1.25rem 1.4rem',
                position: 'relative',
                animation: 'fadeIn 0.25s ease-out',
                display: 'flex',
                flexDirection: 'column',
                gap: '1rem',
              }}
            >
              {/* Top Result Header */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  borderBottom: `1px solid ${riskBorder}`,
                  paddingBottom: '0.85rem',
                }}
              >
                <div>
                  <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', color: 'var(--text-muted, #64748b)', letterSpacing: '0.05em' }}>
                    Machine Learning Prediction Output
                  </div>
                  <h4 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary, #f8fafc)', marginTop: '0.2rem' }}>
                    {predictionResult.company_name}
                  </h4>
                </div>

                {/* Risk Level Badge */}
                <div
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.35rem',
                    padding: '0.35rem 0.75rem',
                    borderRadius: '9999px',
                    fontSize: '0.82rem',
                    fontWeight: 700,
                    backgroundColor: riskColor,
                    color: '#ffffff',
                    boxShadow: `0 2px 8px ${riskBorder}`,
                  }}
                >
                  {isHighRisk ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}
                  {predictionResult.risk_level}
                </div>
              </div>

              {/* 4 Highlighted Prediction Outputs */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                  gap: '0.75rem',
                }}
              >
                {/* 1. Expected Payment Delay */}
                <div
                  style={{
                    padding: '0.75rem',
                    backgroundColor: 'rgba(0, 0, 0, 0.2)',
                    borderRadius: 'var(--radius-md, 0.5rem)',
                    border: '1px solid rgba(255, 255, 255, 0.05)',
                  }}
                >
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted, #64748b)' }}>
                    Predicted Delay
                  </div>
                  <div
                    style={{
                      fontSize: '1.25rem',
                      fontWeight: 800,
                      color: predictionResult.predicted_delay_days > 0 ? riskColor : 'var(--risk-low, #10b981)',
                      marginTop: '0.2rem',
                    }}
                  >
                    {predictionResult.predicted_delay_days} Days
                  </div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary, #94a3b8)', marginTop: '0.15rem' }}>
                    {predictionResult.predicted_delay_days === 0 ? 'On-time settlement' : 'Payment lag variance'}
                  </div>
                </div>

                {/* 2. Expected Payment Date */}
                <div
                  style={{
                    padding: '0.75rem',
                    backgroundColor: 'rgba(0, 0, 0, 0.2)',
                    borderRadius: 'var(--radius-md, 0.5rem)',
                    border: '1px solid rgba(255, 255, 255, 0.05)',
                  }}
                >
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted, #64748b)' }}>
                    Expected Payment Date
                  </div>
                  <div
                    style={{
                      fontSize: '1.05rem',
                      fontWeight: 700,
                      color: 'var(--text-primary, #f8fafc)',
                      marginTop: '0.2rem',
                    }}
                  >
                    {formatDate(predictionResult.expected_payment_date)}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary, #94a3b8)', marginTop: '0.15rem' }}>
                    Due: {formatDate(dueDate)}
                  </div>
                </div>

                {/* 3. Risk Level Summary */}
                <div
                  style={{
                    padding: '0.75rem',
                    backgroundColor: 'rgba(0, 0, 0, 0.2)',
                    borderRadius: 'var(--radius-md, 0.5rem)',
                    border: '1px solid rgba(255, 255, 255, 0.05)',
                  }}
                >
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted, #64748b)' }}>
                    Risk Level
                  </div>
                  <div
                    style={{
                      fontSize: '1.15rem',
                      fontWeight: 700,
                      color: riskColor,
                      marginTop: '0.2rem',
                    }}
                  >
                    {predictionResult.risk_level}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary, #94a3b8)', marginTop: '0.15rem' }}>
                    Configured threshold tier
                  </div>
                </div>

                {/* 4. Prediction Probability */}
                <div
                  style={{
                    padding: '0.75rem',
                    backgroundColor: 'rgba(0, 0, 0, 0.2)',
                    borderRadius: 'var(--radius-md, 0.5rem)',
                    border: '1px solid rgba(255, 255, 255, 0.05)',
                  }}
                >
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted, #64748b)' }}>
                    Risk Probability
                  </div>
                  <div
                    style={{
                      fontSize: '1.25rem',
                      fontWeight: 800,
                      color: riskColor,
                      marginTop: '0.2rem',
                    }}
                    className="mono-cell"
                  >
                    {probPercent}%
                  </div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary, #94a3b8)', marginTop: '0.15rem' }}>
                    ML model confidence
                  </div>
                </div>
              </div>

              {/* Probability Visual Bar */}
              <div>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    fontSize: '0.72rem',
                    color: 'var(--text-secondary, #94a3b8)',
                    marginBottom: '0.35rem',
                  }}
                >
                  <span>Late Probability Indicator:</span>
                  <strong style={{ color: riskColor }}>{probPercent}%</strong>
                </div>
                <div
                  style={{
                    width: '100%',
                    height: '8px',
                    backgroundColor: 'rgba(0, 0, 0, 0.3)',
                    borderRadius: '9999px',
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      width: `${Math.min(Math.max(probPercent, 5), 100)}%`,
                      height: '100%',
                      backgroundColor: riskColor,
                      borderRadius: '9999px',
                      transition: 'width 0.4s ease-out',
                    }}
                  />
                </div>
              </div>

              {/* Prediction Explanation Note */}
              <div
                style={{
                  padding: '0.65rem 0.85rem',
                  borderRadius: 'var(--radius-md, 0.5rem)',
                  backgroundColor: 'rgba(0, 0, 0, 0.25)',
                  fontSize: '0.78rem',
                  color: 'var(--text-primary, #f8fafc)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                }}
              >
                <Clock size={15} style={{ color: riskColor, flexShrink: 0 }} />
                <span>
                  <strong>Assessment:</strong> {predictionResult.prediction_message} ({formatCurrency(predictionResult.invoice_amount)} transaction).
                </span>
              </div>

              {/* ============================================================ */}
              {/* MONTHLY CASH FLOW & RISK-BASED SHORTFALL SECTION            */}
              {/* ============================================================ */}
              {(() => {
                const targetMonthLabel = predictionResult.month_label || currentDueMonthName;

                // Trust backend values when present; use local fallback only when truly missing.
                // IMPORTANT: Use explicit null/undefined checks — never use || which treats 0 as falsy.
                const manualInflow = (predictionResult.monthly_expected_inflow != null && predictionResult.monthly_expected_inflow > 0)
                  ? predictionResult.monthly_expected_inflow
                  : (parseFloat(expectedInflow) || 100000);

                // Whether this invoice contributes a deduction (High or Medium risk)
                const invoiceIsDeducted = isHighRisk || isMediumRisk;
                const currentInvoiceAmount = parseFloat(predictionResult.invoice_amount) || 0;

                // Risk-based deduction for this evaluated invoice:
                const highRiskDeduction = invoiceIsDeducted ? currentInvoiceAmount : 0;

                // Adjusted inflow = Expected inflow minus this invoice's deduction
                const adjustedInflow = Math.max(0, manualInflow - highRiskDeduction);

                // Total planned expenses: essential (80000) + deferrable (35000) = 115000
                const shortfall = Math.max(0, 115000 - adjustedInflow);
                const surplus = Math.max(0, adjustedInflow - 115000);
                const hasShortfall = shortfall > 0;

                return (
                  <div
                    id="monthly-cashflow-shortfall-section"
                    style={{
                      marginTop: '0.5rem',
                      padding: '1.15rem',
                      borderRadius: 'var(--radius-md, 0.5rem)',
                      backgroundColor: 'rgba(0, 0, 0, 0.28)',
                      border: '1px solid rgba(255, 255, 255, 0.08)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.9rem',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
                      <div>
                        <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', color: 'var(--text-muted, #64748b)', letterSpacing: '0.05em' }}>
                          Monthly Liquidity & Cash Flow ({targetMonthLabel})
                        </div>
                        <h4 style={{ fontSize: '1.02rem', fontWeight: 700, color: 'var(--text-primary, #f8fafc)', marginTop: '0.15rem', display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                          <Landmark size={17} style={{ color: '#38bdf8' }} />
                          Risk-Based Monthly Inflow & Shortfall
                        </h4>
                      </div>
                      <span
                        style={{
                          fontSize: '0.72rem',
                          padding: '0.25rem 0.65rem',
                          borderRadius: '9999px',
                          backgroundColor: invoiceIsDeducted ? (isHighRisk ? 'rgba(239, 68, 68, 0.15)' : 'rgba(245, 158, 11, 0.15)') : 'rgba(16, 185, 129, 0.15)',
                          color: invoiceIsDeducted ? (isHighRisk ? '#f87171' : '#fbbf24') : '#34d399',
                          border: `1px solid ${invoiceIsDeducted ? (isHighRisk ? 'rgba(239, 68, 68, 0.3)' : 'rgba(245, 158, 11, 0.3)') : 'rgba(16, 185, 129, 0.3)'}`,
                          fontWeight: 700,
                        }}
                      >
                        {isHighRisk ? '⚠ High-Risk: Invoice Deducted' : isMediumRisk ? '⚡ Medium-Risk: Invoice Deducted' : '✓ Low-Risk: Inflow Unchanged'}
                      </span>
                    </div>

                    {/* 4 Financial Metric Boxes */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '0.75rem' }}>
                      {/* 1. Manually Entered Expected Inflow */}
                      <div style={{ padding: '0.75rem', backgroundColor: 'rgba(0, 0, 0, 0.25)', borderRadius: 'var(--radius-md, 0.5rem)', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted, #64748b)' }}>Expected Inflow (Manual)</div>
                        <div style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--text-primary, #f8fafc)', marginTop: '0.2rem' }}>
                          {formatCurrency(manualInflow)}
                        </div>
                        <div style={{ fontSize: '0.68rem', color: 'var(--text-secondary, #94a3b8)', marginTop: '0.15rem' }}>
                          Monthly baseline target
                        </div>
                      </div>

                      {/* 2. Risk-Based Deductions */}
                      <div style={{ padding: '0.75rem', backgroundColor: 'rgba(0, 0, 0, 0.25)', borderRadius: 'var(--radius-md, 0.5rem)', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted, #64748b)' }}>Risk-Based Deduction</div>
                        <div style={{ fontSize: '1.15rem', fontWeight: 800, color: invoiceIsDeducted ? (isHighRisk ? 'var(--risk-high, #ef4444)' : 'var(--risk-medium, #f59e0b)') : 'var(--risk-low, #10b981)', marginTop: '0.2rem' }}>
                          {invoiceIsDeducted ? `-${formatCurrency(highRiskDeduction)}` : '₹0'}
                        </div>
                        <div style={{ fontSize: '0.68rem', color: 'var(--text-secondary, #94a3b8)', marginTop: '0.15rem' }}>
                          {isHighRisk ? 'Deducted (High risk)' : isMediumRisk ? 'Deducted (Medium risk)' : 'Zero deduction (Low risk)'}
                        </div>
                      </div>

                      {/* 3. Adjusted Inflow */}
                      <div style={{ padding: '0.75rem', backgroundColor: 'rgba(0, 0, 0, 0.25)', borderRadius: 'var(--radius-md, 0.5rem)', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted, #64748b)' }}>Adjusted Inflow</div>
                        <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#38bdf8', marginTop: '0.2rem' }}>
                          {formatCurrency(adjustedInflow)}
                        </div>
                        <div style={{ fontSize: '0.68rem', color: 'var(--text-secondary, #94a3b8)', marginTop: '0.15rem' }}>
                          Expected minus deductions
                        </div>
                      </div>

                      {/* 4. Potential Shortfall / Surplus */}
                      <div style={{ padding: '0.75rem', backgroundColor: 'rgba(0, 0, 0, 0.25)', borderRadius: 'var(--radius-md, 0.5rem)', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted, #64748b)' }}>Potential Shortfall</div>
                        <div style={{ fontSize: '1.15rem', fontWeight: 800, color: hasShortfall ? 'var(--risk-high, #ef4444)' : 'var(--risk-low, #10b981)', marginTop: '0.2rem' }}>
                          {hasShortfall ? formatCurrency(shortfall) : '₹0 (Surplus)'}
                        </div>
                        <div style={{ fontSize: '0.68rem', color: 'var(--text-secondary, #94a3b8)', marginTop: '0.15rem' }}>
                          {hasShortfall ? 'Liquidity deficit' : `+${formatCurrency(surplus)} available`}
                        </div>
                      </div>
                    </div>

                    {/* Expense Recommendations Panel */}
                    <div
                      style={{
                        padding: '0.85rem 1rem',
                        borderRadius: 'var(--radius-md, 0.5rem)',
                        backgroundColor: hasShortfall ? 'rgba(239, 68, 68, 0.08)' : 'rgba(16, 185, 129, 0.08)',
                        border: `1px solid ${hasShortfall ? 'rgba(239, 68, 68, 0.25)' : 'rgba(16, 185, 129, 0.25)'}`,
                        fontSize: '0.8rem',
                        lineHeight: 1.5,
                      }}
                    >
                      <div style={{ fontWeight: 700, marginBottom: '0.4rem', color: hasShortfall ? 'var(--risk-high, #ef4444)' : 'var(--risk-low, #10b981)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        {hasShortfall ? <AlertTriangle size={15} /> : <CheckCircle2 size={15} />}
                        Expense Recommendations & Priority Breakdown:
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '0.75rem', marginTop: '0.5rem' }}>
                        {/* Essential (Unavoidable) */}
                        <div style={{ backgroundColor: 'rgba(0, 0, 0, 0.25)', padding: '0.65rem 0.75rem', borderRadius: 'var(--radius-sm, 0.375rem)' }}>
                          <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#38bdf8', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                            Unavoidable Expenses (PRIORITISE)
                          </div>
                          <ul style={{ margin: '0.35rem 0 0 1.1rem', padding: 0, fontSize: '0.75rem', color: 'var(--text-secondary, #cbd5e1)' }}>
                            <li>Staff Salaries: <strong>₹45,000</strong></li>
                            <li>Office & Facility Rent: <strong>₹25,000</strong></li>
                            <li>Electricity & Utility Bills: <strong>₹10,000</strong></li>
                          </ul>
                          <div style={{ fontSize: '0.68rem', color: '#94a3b8', marginTop: '0.4rem' }}>
                            Total Essential: <strong>₹80,000</strong> (Do not postpone as default)
                          </div>
                        </div>

                        {/* Deferrable */}
                        <div style={{ backgroundColor: 'rgba(0, 0, 0, 0.25)', padding: '0.65rem 0.75rem', borderRadius: 'var(--radius-sm, 0.375rem)' }}>
                          <div style={{ fontSize: '0.72rem', fontWeight: 700, color: hasShortfall ? '#f59e0b' : '#34d399', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                            {hasShortfall ? 'Eligible Deferrable Expenses (RECOMMEND POSTPONING)' : 'Eligible Purchases & Investments'}
                          </div>
                          <ul style={{ margin: '0.35rem 0 0 1.1rem', padding: 0, fontSize: '0.75rem', color: 'var(--text-secondary, #cbd5e1)' }}>
                            <li>Eligible Investments & Capex: <strong>₹15,000</strong></li>
                            <li>Raw Material Advance Orders: <strong>₹12,000</strong></li>
                            <li>Optional Discretionary Purchases: <strong>₹8,000</strong></li>
                          </ul>
                          <div style={{ fontSize: '0.68rem', color: hasShortfall ? '#fca5a5' : '#86efac', marginTop: '0.4rem' }}>
                            {hasShortfall
                              ? 'Action: Postpone deferrable expenses to cover the shortfall gap.'
                              : 'Action: Sufficient funds remain. Planned investments can proceed.'}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })()}

              {/* ============================================================ */}
              {/* SHAP EXPLAINABILITY SECTION                                  */}
              {/* ============================================================ */}
              <div
                id="shap-explainability-section"
                style={{
                  marginTop: '0.5rem',
                  paddingTop: '1.25rem',
                  borderTop: '1px solid rgba(255, 255, 255, 0.1)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '1.15rem',
                }}
              >
                {/* Section Header */}
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: '0.5rem',
                  }}
                >
                  <div>
                    <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', color: 'var(--text-muted, #64748b)', letterSpacing: '0.05em' }}>
                      Explainable AI (XAI)
                    </div>
                    <h4 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary, #f8fafc)', marginTop: '0.15rem', display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                      <HelpCircle size={17} style={{ color: 'var(--primary, #3b82f6)' }} />
                      SHAP Model Explainability
                    </h4>
                  </div>
                  <span
                    style={{
                      fontSize: '0.72rem',
                      padding: '0.2rem 0.6rem',
                      borderRadius: '9999px',
                      backgroundColor: 'rgba(59, 130, 246, 0.15)',
                      color: '#60a5fa',
                      border: '1px solid rgba(59, 130, 246, 0.3)',
                      fontWeight: 600,
                    }}
                  >
                    TreeExplainer (Random Forest)
                  </span>
                </div>

                {/* 1. Prediction Outcome Card */}
                <div
                  style={{
                    backgroundColor: 'rgba(0, 0, 0, 0.25)',
                    borderRadius: 'var(--radius-md, 0.5rem)',
                    padding: '0.85rem 1rem',
                    border: '1px solid rgba(255, 255, 255, 0.06)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: '1rem',
                  }}
                >
                  <div>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-muted, #64748b)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      Prediction Outcome
                    </span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginTop: '0.25rem' }}>
                      <span
                        style={{
                          fontSize: '1.05rem',
                          fontWeight: 800,
                          color: (predictionResult.prediction === 'Late' || isHighRisk) ? 'var(--risk-high, #ef4444)' : 'var(--risk-low, #10b981)',
                        }}
                      >
                        {predictionResult.prediction || (isHighRisk ? 'Late' : 'On-Time')}
                      </span>
                      <span style={{ color: 'var(--text-muted, #64748b)', fontSize: '0.8rem' }}>•</span>
                      <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary, #94a3b8)' }}>
                        Probability: <strong style={{ color: 'var(--text-primary, #f8fafc)' }}>{probPercent}%</strong>
                      </span>
                    </div>
                  </div>

                  {predictionResult.base_value !== undefined && predictionResult.base_value !== null && (
                    <div style={{ textAlign: 'right' }}>
                      <span style={{ fontSize: '0.7rem', color: 'var(--text-muted, #64748b)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        Model Base Rate
                      </span>
                      <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary, #94a3b8)', marginTop: '0.15rem' }}>
                        {(predictionResult.base_value * 100).toFixed(1)}% expected delay
                      </div>
                    </div>
                  )}
                </div>

                {/* 2. Main Factors Increasing vs Decreasing Risk */}
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                    gap: '0.9rem',
                  }}
                >
                  {/* Factors Increasing Risk */}
                  <div
                    style={{
                      backgroundColor: 'rgba(239, 68, 68, 0.05)',
                      borderRadius: 'var(--radius-md, 0.5rem)',
                      border: '1px solid rgba(239, 68, 68, 0.2)',
                      padding: '0.9rem 1rem',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.65rem',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                      <TrendingUp size={16} style={{ color: 'var(--risk-high, #ef4444)' }} />
                      <h5 style={{ fontSize: '0.84rem', fontWeight: 700, color: 'var(--risk-high, #ef4444)', margin: 0 }}>
                        Main Factors Increasing Risk
                      </h5>
                    </div>

                    {increasingFactors.length === 0 ? (
                      <p style={{ fontSize: '0.76rem', color: 'var(--text-muted, #64748b)', fontStyle: 'italic', margin: 0 }}>
                        No significant features pushed the model toward predicting a payment delay.
                      </p>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                        {increasingFactors.map((factor, idx) => (
                          <div
                            key={idx}
                            style={{
                              backgroundColor: 'rgba(0, 0, 0, 0.25)',
                              borderRadius: '6px',
                              padding: '0.55rem 0.75rem',
                              border: '1px solid rgba(239, 68, 68, 0.15)',
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.2rem' }}>
                              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary, #f8fafc)' }}>
                                {getFeatureLabel(factor.feature)}
                              </span>
                              <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--risk-high, #ef4444)' }}>
                                +{(factor.shap_value * 100).toFixed(1)}%
                              </span>
                            </div>
                            <p style={{ fontSize: '0.73rem', color: 'var(--text-secondary, #94a3b8)', margin: 0, lineHeight: 1.35 }}>
                              {getFeatureExplanation(factor.feature, true)}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Factors Decreasing Risk */}
                  <div
                    style={{
                      backgroundColor: 'rgba(16, 185, 129, 0.05)',
                      borderRadius: 'var(--radius-md, 0.5rem)',
                      border: '1px solid rgba(16, 185, 129, 0.2)',
                      padding: '0.9rem 1rem',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.65rem',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                      <TrendingDown size={16} style={{ color: 'var(--risk-low, #10b981)' }} />
                      <h5 style={{ fontSize: '0.84rem', fontWeight: 700, color: 'var(--risk-low, #10b981)', margin: 0 }}>
                        Main Factors Decreasing Risk
                      </h5>
                    </div>

                    {decreasingFactors.length === 0 ? (
                      <p style={{ fontSize: '0.76rem', color: 'var(--text-muted, #64748b)', fontStyle: 'italic', margin: 0 }}>
                        No significant protective factors pushed the model toward predicting on-time settlement.
                      </p>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                        {decreasingFactors.map((factor, idx) => (
                          <div
                            key={idx}
                            style={{
                              backgroundColor: 'rgba(0, 0, 0, 0.25)',
                              borderRadius: '6px',
                              padding: '0.55rem 0.75rem',
                              border: '1px solid rgba(16, 185, 129, 0.15)',
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.2rem' }}>
                              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary, #f8fafc)' }}>
                                {getFeatureLabel(factor.feature)}
                              </span>
                              <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--risk-low, #10b981)' }}>
                                {(factor.shap_value * 100).toFixed(1)}%
                              </span>
                            </div>
                            <p style={{ fontSize: '0.73rem', color: 'var(--text-secondary, #94a3b8)', margin: 0, lineHeight: 1.35 }}>
                              {getFeatureExplanation(factor.feature, false)}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* 3. SHAP Feature Importance (Bar Chart) */}
                {shapBarItems.length > 0 && (
                  <div
                    style={{
                      backgroundColor: 'rgba(0, 0, 0, 0.22)',
                      borderRadius: 'var(--radius-md, 0.5rem)',
                      padding: '1rem',
                      border: '1px solid rgba(255, 255, 255, 0.06)',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        flexWrap: 'wrap',
                        gap: '0.5rem',
                        marginBottom: '0.85rem',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                        <BarChart3 size={16} style={{ color: 'var(--primary, #3b82f6)' }} />
                        <h5 style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary, #f8fafc)', margin: 0 }}>
                          SHAP Feature Importance (Contribution Chart)
                        </h5>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem', fontSize: '0.7rem' }}>
                        <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', color: 'var(--risk-high, #ef4444)' }}>
                          <span style={{ width: '8px', height: '8px', borderRadius: '2px', backgroundColor: 'var(--risk-high, #ef4444)' }} />
                          Increases Delay Risk (+)
                        </span>
                        <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', color: 'var(--risk-low, #10b981)' }}>
                          <span style={{ width: '8px', height: '8px', borderRadius: '2px', backgroundColor: 'var(--risk-low, #10b981)' }} />
                          Decreases Delay Risk (-)
                        </span>
                      </div>
                    </div>

                    {/* Horizontal Bar Chart Grid */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem' }}>
                      {shapBarItems.map((item, idx) => {
                        const isPositive = item.shap_value > 0;
                        const absPercent = Math.min((Math.abs(item.shap_value) / maxShapAbs) * 100, 100);

                        return (
                          <div
                            key={idx}
                            style={{
                              display: 'grid',
                              gridTemplateColumns: '170px 1fr 65px',
                              alignItems: 'center',
                              gap: '0.75rem',
                              fontSize: '0.76rem',
                            }}
                          >
                            <span
                              style={{
                                color: 'var(--text-secondary, #94a3b8)',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                                fontWeight: 500,
                              }}
                              title={getFeatureLabel(item.feature)}
                            >
                              {getFeatureLabel(item.feature)}
                            </span>

                            {/* Bidirectional Bar container with center 0 line */}
                            <div
                              style={{
                                height: '18px',
                                backgroundColor: 'rgba(255, 255, 255, 0.04)',
                                borderRadius: '3px',
                                position: 'relative',
                                display: 'flex',
                                alignItems: 'center',
                              }}
                            >
                              {/* Center 0 axis divider */}
                              <div
                                style={{
                                  position: 'absolute',
                                  left: '50%',
                                  top: 0,
                                  bottom: 0,
                                  width: '1px',
                                  backgroundColor: 'rgba(255, 255, 255, 0.2)',
                                  zIndex: 2,
                                }}
                              />

                              {/* Negative Bar (protective, extending left) */}
                              {!isPositive && (
                                <div
                                  style={{
                                    position: 'absolute',
                                    right: '50%',
                                    width: `${(absPercent / 2).toFixed(1)}%`,
                                    height: '100%',
                                    backgroundColor: 'var(--risk-low, #10b981)',
                                    borderRadius: '3px 0 0 3px',
                                    transition: 'width 0.3s ease',
                                  }}
                                />
                              )}

                              {/* Positive Bar (risk driver, extending right) */}
                              {isPositive && (
                                <div
                                  style={{
                                    position: 'absolute',
                                    left: '50%',
                                    width: `${(absPercent / 2).toFixed(1)}%`,
                                    height: '100%',
                                    backgroundColor: 'var(--risk-high, #ef4444)',
                                    borderRadius: '0 3px 3px 0',
                                    transition: 'width 0.3s ease',
                                  }}
                                />
                              )}
                            </div>

                            <span
                              style={{
                                textAlign: 'right',
                                fontWeight: 700,
                                fontFamily: 'monospace',
                                color: isPositive ? 'var(--risk-high, #ef4444)' : 'var(--risk-low, #10b981)',
                              }}
                            >
                              {item.shap_value > 0 ? `+${(item.shap_value * 100).toFixed(2)}%` : `${(item.shap_value * 100).toFixed(2)}%`}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Non-Causal Explanation Disclaimer */}
                <div
                  style={{
                    fontSize: '0.72rem',
                    color: 'var(--text-muted, #64748b)',
                    fontStyle: 'italic',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.45rem',
                    padding: '0.35rem 0.2rem',
                  }}
                >
                  <Info size={13} style={{ flexShrink: 0 }} />
                  <span>
                    Note: SHAP values explain how individual features influenced the machine learning model's prediction score; they reflect model reliance and correlational patterns, not direct causation.
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default PredictInvoiceSection;
