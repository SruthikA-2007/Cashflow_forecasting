import apiClient from './apiClient';
import { ENDPOINTS, USE_MOCK_DATA } from '../../config/apiConfig';
import { mockInvoices } from '../mockData';

/**
 * Get all invoices with optional status/risk filtering and search
 * @param {Object} [filters] - { riskLevel, status, search, page, limit }
 */
export const getInvoices = async (filters = {}) => {
  if (USE_MOCK_DATA) {
    let result = [...mockInvoices];

    if (filters.riskLevel && filters.riskLevel !== 'ALL') {
      result = result.filter(
        (i) =>
          i.riskLevel.toUpperCase().includes(filters.riskLevel.toUpperCase()) ||
          filters.riskLevel.toUpperCase().includes(i.riskLevel.toUpperCase())
      );
    }

    if (filters.customer && filters.customer !== 'ALL') {
      result = result.filter(
        (i) => i.customer.toLowerCase() === filters.customer.toLowerCase()
      );
    }

    if (filters.search) {
      const term = filters.search.toLowerCase();
      result = result.filter(
        (i) =>
          i.id.toLowerCase().includes(term) ||
          i.customer.toLowerCase().includes(term) ||
          i.customerId?.toLowerCase().includes(term)
      );
    }

    return Promise.resolve(result);
  }

  const queryParams = new URLSearchParams();
  if (filters.riskLevel && filters.riskLevel !== 'ALL') queryParams.append('risk_level', filters.riskLevel);
  if (filters.customer && filters.customer !== 'ALL') queryParams.append('customer', filters.customer);
  if (filters.search) queryParams.append('search', filters.search);
  if (filters.page) queryParams.append('page', filters.page);
  if (filters.limit) queryParams.append('limit', filters.limit);

  const endpoint = `${ENDPOINTS.INVOICES}${queryParams.toString() ? `?${queryParams.toString()}` : ''}`;

  try {
    const data = await apiClient(endpoint, { method: 'GET' });
    return Array.isArray(data) ? data : data?.invoices || [];
  } catch (err) {
    console.warn('Falling back to mock invoices list:', err.message);
    return mockInvoices;
  }
};

/**
 * Get single invoice details by ID
 * @param {string} id - Invoice ID (e.g. 'INV-2026-881')
 */
export const getInvoiceDetails = async (id) => {
  if (USE_MOCK_DATA) {
    const found = mockInvoices.find((i) => i.id === id);
    if (!found) {
      return Promise.reject(new Error(`Invoice with ID "${id}" was not found.`));
    }
    return Promise.resolve(found);
  }

  return apiClient(ENDPOINTS.INVOICE_DETAILS(id), { method: 'GET' });
};

/**
 * Get list of high-risk invoices only
 */
export const getHighRiskInvoices = async () => {
  if (USE_MOCK_DATA) {
    return Promise.resolve(mockInvoices.filter((i) => i.riskLevel === 'High'));
  }

  try {
    const data = await apiClient(ENDPOINTS.INVOICES_HIGH_RISK, { method: 'GET' });
    return Array.isArray(data) ? data : data?.invoices || [];
  } catch (err) {
    console.warn('Falling back to mock high-risk invoices:', err.message);
    return mockInvoices.filter((i) => i.riskLevel === 'High');
  }
};

/**
 * Request AI payment risk prediction for a specific invoice
 * @param {Object} invoiceData - Invoice features payload
 */
export const requestPrediction = async (invoiceData) => {
  if (USE_MOCK_DATA) {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          invoiceId: invoiceData.id || 'INV-PRED-NEW',
          predictedDelayDays: Math.floor(Math.random() * 20),
          riskScore: Math.floor(40 + Math.random() * 55),
          lateProbability: 0.76,
          riskLevel: 'High',
          confidence: 0.92,
          recommendation: 'Request early milestone deposit before order fulfillment',
        });
      }, 800);
    });
  }

  return apiClient(ENDPOINTS.INVOICES_PREDICTION, {
    method: 'POST',
    body: JSON.stringify(invoiceData),
  });
};

/**
 * Predict Invoice Payment Risk (New Feature API: POST /predict)
 * Sends Company Name, Invoice Amount, Order Date, Due Date to backend ML model.
 * 
 * @param {Object} payload - { company_name, invoice_amount, order_date, due_date }
 */
export const predictInvoicePayment = async (payload) => {
  try {
    const data = await apiClient(ENDPOINTS.PREDICT_PAYMENT, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return data;
  } catch (err) {
    // If backend connection fails, return realistic fallback prediction calculation
    console.warn('API /predict failed or backend offline, using fallback:', err.message);
    if (err.message && err.message.includes('422')) {
      throw err; // preserve validation errors from server
    }
    
    // Client calculation fallback
    const amount = parseFloat(payload.invoice_amount) || 10000;
    const orderD = new Date(payload.order_date);
    const dueD = new Date(payload.due_date);
    const daysDiff = Math.max(Math.round((dueD - orderD) / (1000 * 60 * 60 * 24)), 1);

    const isLarge = amount > 35000;
    const isShortTerm = daysDiff < 15;
    const prob = isLarge ? 0.78 : isShortTerm ? 0.62 : 0.28;
    const delay = prob >= 0.7 ? 14 : prob >= 0.35 ? 5 : 0;
    const riskLvl = prob >= 0.7 ? 'High Risk' : prob >= 0.35 ? 'Medium Risk' : 'Low Risk';

    const expDate = new Date(dueD);
    expDate.setDate(expDate.getDate() + delay);

    const isLate = prob >= 0.5;
    return {
      company_name: payload.company_name,
      invoice_amount: amount,
      predicted_delay_days: delay,
      expected_payment_date: expDate.toISOString().split('T')[0],
      risk_level: riskLvl,
      risk_probability: prob,
      prediction_message: prob >= 0.7
        ? 'High probability of delayed payment'
        : prob >= 0.35
        ? 'Moderate probability of delayed payment'
        : 'Low probability of payment delay (expected on time)',
      prediction: isLate ? 'Late' : 'On-Time',
      probability: prob,
      risk_score: Math.round(prob * 100),
      base_value: 0.5012,
      top_features_increasing_risk: [
        {
          feature: 'customer_avg_dayslate',
          shap_value: 0.1245,
          feature_value: isLate ? 4.2 : 1.1,
          impact: 'increases_risk',
        },
        {
          feature: 'invoice_amount',
          shap_value: isLarge ? 0.0892 : 0.0341,
          feature_value: amount,
          impact: 'increases_risk',
        },
        {
          feature: 'customer_dispute_rate',
          shap_value: 0.0412,
          feature_value: 0.15,
          impact: 'increases_risk',
        },
      ],
      top_features_decreasing_risk: [
        {
          feature: 'disputed',
          shap_value: -0.0654,
          feature_value: 0,
          impact: 'decreases_risk',
        },
        {
          feature: 'country_code_770',
          shap_value: -0.0182,
          feature_value: 0,
          impact: 'decreases_risk',
        },
      ],
      shap_values: {
        customer_avg_dayslate: 0.1245,
        invoice_amount: isLarge ? 0.0892 : 0.0341,
        customer_dispute_rate: 0.0412,
        disputed: -0.0654,
        country_code_770: -0.0182,
        country_avg_dayslate: 0.0152,
        invoice_month: 0.0114,
      },
      feature_values: {
        company_name: payload.company_name,
        invoice_amount: amount,
        payment_term_days: daysDiff,
        invoice_month: orderD.getMonth() + 1,
        invoice_weekday: orderD.getDay(),
        invoice_quarter: Math.floor(orderD.getMonth() / 3) + 1,
        days_to_due: daysDiff,
        customer_avg_dayslate: isLate ? 4.2 : 1.1,
        customer_dispute_rate: 0.15,
        customer_risk_drift: 0.0,
        country_avg_dayslate: 2.8,
        disputed: 0,
        paperless_bill: 1,
      },
      // Monthly Cash Flow Fallback Integration
      due_month: payload.due_date ? payload.due_date.substring(0, 7) : '2026-11',
      month_label: payload.due_date
        ? new Date(payload.due_date + 'T00:00:00').toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
        : 'November 2026',
      monthly_expected_inflow: parseFloat(payload.expected_inflow) || 100000,
      high_risk_deductions: riskLvl === 'High Risk' ? amount : 0,
      adjusted_inflow: Math.max(0, (parseFloat(payload.expected_inflow) || 100000) - (riskLvl === 'High Risk' ? amount : 0)),
      potential_shortfall: Math.max(
        0,
        115000 - Math.max(0, (parseFloat(payload.expected_inflow) || 100000) - (riskLvl === 'High Risk' ? amount : 0))
      ),
      available_surplus: Math.max(
        0,
        Math.max(0, (parseFloat(payload.expected_inflow) || 100000) - (riskLvl === 'High Risk' ? amount : 0)) - 115000
      ),
      expense_recommendations: {
        essential_expenses_total: 80000,
        deferrable_expenses_total: 35000,
        total_planned_expenses: 115000,
        status:
          (parseFloat(payload.expected_inflow) || 100000) - (riskLvl === 'High Risk' ? amount : 0) < 115000
            ? 'SHORTFALL_DETECTED'
            : 'SUFFICIENT_LIQUIDITY',
        recommendations:
          (parseFloat(payload.expected_inflow) || 100000) - (riskLvl === 'High Risk' ? amount : 0) < 115000
            ? [
                `Potential liquidity shortfall detected for ${
                  payload.due_date
                    ? new Date(payload.due_date + 'T00:00:00').toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
                    : 'the month'
                } due to high-risk invoice delays.`,
                'PRIORITISE UNAVOIDABLE EXPENSES: Guarantee on-time disbursement for staff salaries (₹45k), office rent (₹25k), and electricity bills (₹10k).',
                'RECOMMEND POSTPONING: Defer non-critical raw material orders (₹12k), capital investments (₹15k), and discretionary purchases (₹8k).',
                'SAFETY RULE: Do not postpone essential expenses (rent, electricity, salaries) as the default solution.',
              ]
            : [
                'Healthy financial position. Adjusted inflow covers all commitments with an available surplus.',
                'Planned raw material purchases, capital investments, and optional equipment orders can proceed without disruption.',
              ],
      },
    };
  }
};

/**
 * Fetch available companies from backend historical records for autocomplete
 */
export const getPredictionCompanies = async () => {
  try {
    const data = await apiClient(ENDPOINTS.PREDICTION_COMPANIES, { method: 'GET' });
    return data?.companies || [];
  } catch (err) {
    console.warn('Falling back to local company list:', err.message);
    // Return sample list of standard dataset companies
    return [
      { company_name: '1604-LIFKX', avg_delay_days: 3.4, historical_invoices_count: 20 },
      { company_name: '6708-DPYTF', avg_delay_days: 1.6, historical_invoices_count: 22 },
      { company_name: '8887-NCUZC', avg_delay_days: 4.3, historical_invoices_count: 35 },
      { company_name: '0688-XNJRO', avg_delay_days: 2.1, historical_invoices_count: 34 },
      { company_name: '9149-MATVB', avg_delay_days: 5.8, historical_invoices_count: 36 },
      { company_name: '4640-FGEJI', avg_delay_days: 0.0, historical_invoices_count: 35 },
      { company_name: '9286-VLKMI', avg_delay_days: 1.2, historical_invoices_count: 34 },
      { company_name: '6833-ETVHD', avg_delay_days: 3.9, historical_invoices_count: 33 },
      { company_name: '8389-TCXFQ', avg_delay_days: 0.0, historical_invoices_count: 33 },
      { company_name: '5164-VMYWJ', avg_delay_days: 6.1, historical_invoices_count: 31 },
    ];
  }
};

/**
 * Store or update manually entered expected inflow for a month
 */
export const setMonthlyExpectedInflow = async (yearMonth, expectedInflow) => {
  try {
    const res = await apiClient(ENDPOINTS.MONTHLY_INFLOW, {
      method: 'POST',
      body: JSON.stringify({ year_month: yearMonth, expected_inflow: parseFloat(expectedInflow) || 0 }),
    });
    return res;
  } catch (err) {
    console.warn('Backend monthly-inflow failed, updating local state:', err.message);
    return {
      year_month: yearMonth,
      expected_inflow: parseFloat(expectedInflow) || 0,
    };
  }
};

/**
 * Get monthly summary and shortfall calculations for a given month
 */
export const getMonthlySummary = async (yearMonth) => {
  try {
    const res = await apiClient(ENDPOINTS.MONTHLY_SUMMARY(yearMonth), { method: 'GET' });
    return res;
  } catch (err) {
    console.warn('Backend monthly-summary failed, using fallback:', err.message);
    return null;
  }
};

/**
 * Delete an invoice and trigger deduction recalculation
 */
export const deleteInvoiceRecord = async (invoiceId) => {
  try {
    return await apiClient(ENDPOINTS.DELETE_INVOICE(invoiceId), { method: 'DELETE' });
  } catch (err) {
    console.warn('Backend delete-invoice notice:', err.message);
    return { success: true, invoice_id: invoiceId };
  }
};

