import apiClient from './apiClient';
import { ENDPOINTS, USE_MOCK_DATA } from '../../config/apiConfig';

export const mockModelPerformance = {
  modelType: 'Random Forest Classifier & Regressor',
  version: 'v2.4.1',
  lastTrained: '2026-08-20 18:30 UTC',
  accuracy: 0.942,
  f1Score: 0.918,
  rocAuc: 0.965,
  meanAbsoluteErrorDays: 1.8,
  topFeatures: [
    { feature: 'Historical Payment Variance (Days)', importance: 0.34 },
    { feature: 'Customer Credit Utilization %', importance: 0.26 },
    { feature: 'Invoice Amount Ratio to Average', importance: 0.18 },
    { feature: 'Recent Overdue Invoices Count', importance: 0.14 },
    { feature: 'Customer Industry Default Index', importance: 0.08 },
  ],
  datasetRecordsTrained: 14250,
};

/**
 * Get current machine learning model performance and feature weights
 */
export const getModelPerformance = async () => {
  if (USE_MOCK_DATA) {
    return Promise.resolve(mockModelPerformance);
  }

  try {
    const data = await apiClient(ENDPOINTS.MODEL_PERFORMANCE, { method: 'GET' });
    return data || mockModelPerformance;
  } catch (err) {
    console.warn('Falling back to mock model performance:', err.message);
    return mockModelPerformance;
  }
};
