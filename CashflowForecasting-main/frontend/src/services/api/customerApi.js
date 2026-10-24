import apiClient from './apiClient';
import { ENDPOINTS, USE_MOCK_DATA } from '../../config/apiConfig';
import { mockCustomers } from '../mockData';

/**
 * Get customer credit and default risk rankings
 * @param {Object} [filters] - { riskLevel, search, page, limit }
 */
export const getCustomerRankings = async (filters = {}) => {
  if (USE_MOCK_DATA) {
    let result = [...mockCustomers];

    if (filters.riskLevel && filters.riskLevel !== 'ALL') {
      result = result.filter(
        (c) => c.riskLevel.toUpperCase() === filters.riskLevel.toUpperCase()
      );
    }

    if (filters.search) {
      const term = filters.search.toLowerCase();
      result = result.filter(
        (c) =>
          c.name.toLowerCase().includes(term) ||
          c.sector.toLowerCase().includes(term) ||
          c.id.toLowerCase().includes(term)
      );
    }

    return Promise.resolve(result);
  }

  const queryParams = new URLSearchParams();
  if (filters.riskLevel && filters.riskLevel !== 'ALL') queryParams.append('risk_level', filters.riskLevel);
  if (filters.search) queryParams.append('search', filters.search);

  const endpoint = `${ENDPOINTS.CUSTOMERS}${queryParams.toString() ? `?${queryParams.toString()}` : ''}`;

  try {
    const data = await apiClient(endpoint, { method: 'GET' });
    return Array.isArray(data) ? data : data?.customers || [];
  } catch (err) {
    console.warn('Falling back to mock customer rankings:', err.message);
    return mockCustomers;
  }
};

/**
 * Get detailed customer account profile by ID
 * @param {string} id - Customer ID (e.g. 'CUST-101')
 */
export const getCustomerDetails = async (id) => {
  if (USE_MOCK_DATA) {
    const customer = mockCustomers.find((c) => c.id === id);
    if (!customer) {
      return Promise.reject(new Error(`Customer account "${id}" was not found.`));
    }
    return Promise.resolve(customer);
  }

  return apiClient(ENDPOINTS.CUSTOMER_DETAILS(id), { method: 'GET' });
};
