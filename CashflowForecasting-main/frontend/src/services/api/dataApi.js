import apiClient from './apiClient';
import { ENDPOINTS, USE_MOCK_DATA } from '../../config/apiConfig';
import {
  mockDataSourceInfo,
  mockPreprocessingSummary,
  mockDatasetPreview,
} from '../dataManagementService';

/**
 * Upload an invoice CSV file
 * @param {File} file - CSV file to upload
 */
export const uploadCsv = async (file) => {
  if (USE_MOCK_DATA) {
    return new Promise((resolve, reject) => {
      setTimeout(() => {
        if (!file.name.toLowerCase().endsWith('.csv')) {
          reject(new Error('Invalid format: Only CSV files are supported.'));
          return;
        }
        resolve({
          success: true,
          fileName: file.name,
          uploadedRecords: 1250,
          message: `Successfully uploaded and validated "${file.name}"`,
        });
      }, 1000);
    });
  }

  const formData = new FormData();
  formData.append('file', file);

  return apiClient(ENDPOINTS.DATA_UPLOAD_CSV, {
    method: 'POST',
    body: formData,
    isFormData: true,
  });
};

/**
 * Get sample dataset preview rows
 */
export const getDatasetPreview = async () => {
  if (USE_MOCK_DATA) {
    return Promise.resolve(mockDatasetPreview || []);
  }

  try {
    const data = await apiClient(ENDPOINTS.DATA_PREVIEW, { method: 'GET' });
    return Array.isArray(data) ? data : data?.preview || [];
  } catch (err) {
    console.warn('Falling back to mock dataset preview due to API error:', err.message);
    return mockDatasetPreview;
  }
};

/**
 * Get preprocessing sanitation and deduplication summary
 */
export const getPreprocessingSummary = async () => {
  if (USE_MOCK_DATA) {
    return Promise.resolve(mockPreprocessingSummary);
  }

  try {
    return await apiClient(ENDPOINTS.DATA_PREPROCESSING_SUMMARY, { method: 'GET' });
  } catch (err) {
    console.warn('Falling back to mock preprocessing summary:', err.message);
    return mockPreprocessingSummary;
  }
};

/**
 * Get current database and source connection status
 */
export const getDataSourceStatus = async () => {
  if (USE_MOCK_DATA) {
    return Promise.resolve(mockDataSourceInfo);
  }

  try {
    return await apiClient(ENDPOINTS.DATA_SOURCE_STATUS, { method: 'GET' });
  } catch (err) {
    console.warn('Falling back to mock data source status:', err.message);
    return mockDataSourceInfo;
  }
};
