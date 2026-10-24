/**
 * Centralized API & Environment Configuration
 * Reads configuration from Vite environment variables with sensible defaults.
 */

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

// Toggle between mock data provider and live FastAPI endpoints
export const USE_MOCK_DATA =
  import.meta.env.VITE_USE_MOCK_DATA === 'true' ||
  import.meta.env.VITE_USE_MOCK_DATA === undefined;

export const API_TIMEOUT_MS = 15000;

export const ENDPOINTS = {
  HEALTH: '/health',

  // Authentication Endpoints
  AUTH_SEND_OTP: '/api/auth/send-otp',
  AUTH_VERIFY_OTP: '/api/auth/verify-otp',
  AUTH_LOGOUT: '/api/auth/logout',
  AUTH_ME: '/api/auth/me',
  AUTH_SMTP_STATUS: '/api/auth/smtp-status',
  
  // Data Endpoints
  DATA_UPLOAD_CSV: '/api/datasets/upload',
  DATA_PREVIEW: '/api/datasets/preview',
  DATA_PREPROCESSING_SUMMARY: '/api/datasets/summary',
  DATA_SOURCE_STATUS: '/api/datasets/status',

  // Dashboard Endpoints
  DASHBOARD_SUMMARY: '/api/dashboard/summary',
  DASHBOARD_RISK_DISTRIBUTION: '/api/dashboard/risk-distribution',
  DASHBOARD_TOP_RISK: '/api/dashboard/top-risk',

  // Invoices Endpoints
  INVOICES: '/api/invoices',
  INVOICE_DETAILS: (id) => `/api/invoices/${id}`,
  INVOICES_HIGH_RISK: '/api/invoices/high-risk',
  INVOICES_PREDICTION: '/api/predictions/predict',
  PREDICT_PAYMENT: '/predict',
  PREDICTION_COMPANIES: '/predictions/companies',

  // Customers Endpoints
  CUSTOMERS: '/api/customers',
  CUSTOMER_DETAILS: (id) => `/api/customers/${id}`,

  // Model Endpoints
  MODEL_PERFORMANCE: '/api/model/performance',

  // Monthly Cash Flow & Shortfall Endpoints
  MONTHLY_INFLOW: '/api/predictions/monthly-inflow',
  MONTHLY_SUMMARY: (yearMonth) => `/api/predictions/monthly-summary/${yearMonth}`,
  DELETE_INVOICE: (id) => `/api/predictions/invoices/${id}`,
};

