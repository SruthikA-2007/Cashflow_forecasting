import apiClient from './apiClient';
import { ENDPOINTS, USE_MOCK_DATA } from '../../config/apiConfig';
import { mockDashboardData } from '../dashboardService';

/**
 * Get the 4 summary KPI card values for the dashboard
 */
export const getDashboardSummary = async () => {
  if (USE_MOCK_DATA) {
    return Promise.resolve(mockDashboardData.summaryCards);
  }

  try {
    const res = await apiClient(ENDPOINTS.DASHBOARD_SUMMARY, { method: 'GET' });
    return res || mockDashboardData.summaryCards;
  } catch (err) {
    console.warn('Falling back to mock dashboard summary:', err.message);
    return mockDashboardData.summaryCards;
  }
};

/**
 * Get payment risk distribution metrics (Low, Medium, High counts and sums)
 */
export const getRiskDistribution = async () => {
  if (USE_MOCK_DATA) {
    return Promise.resolve(mockDashboardData.riskDistribution);
  }

  try {
    const res = await apiClient(ENDPOINTS.DASHBOARD_RISK_DISTRIBUTION, { method: 'GET' });
    return res || mockDashboardData.riskDistribution;
  } catch (err) {
    console.warn('Falling back to mock risk distribution:', err.message);
    return mockDashboardData.riskDistribution;
  }
};

/**
 * Get top high-risk priority invoices for the dashboard table
 */
export const getTopHighRiskInvoices = async () => {
  if (USE_MOCK_DATA) {
    return Promise.resolve(mockDashboardData.topHighRiskInvoices || []);
  }

  try {
    const res = await apiClient(ENDPOINTS.DASHBOARD_TOP_RISK, { method: 'GET' });
    return Array.isArray(res) ? res : res?.invoices || mockDashboardData.topHighRiskInvoices;
  } catch (err) {
    console.warn('Falling back to mock top high-risk invoices:', err.message);
    return mockDashboardData.topHighRiskInvoices;
  }
};
