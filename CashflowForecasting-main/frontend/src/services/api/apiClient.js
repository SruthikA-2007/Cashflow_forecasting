import { API_BASE_URL, API_TIMEOUT_MS } from '../../config/apiConfig';

/**
 * Standardized API Error Class
 */
export class ApiError extends Error {
  constructor(message, status = 500, data = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

/**
 * Centralized fetch client with timeout and unified error handling
 */
export const apiClient = async (endpoint, options = {}) => {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`;

  const token = localStorage.getItem('fin_token');

  const headers = {
    ...(!options.isFormData && { 'Content-Type': 'application/json' }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), options.timeout || API_TIMEOUT_MS);

  try {
    const response = await fetch(url, {
      ...options,
      headers,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    // Handle Empty Response
    if (response.status === 204) {
      return null;
    }

    const contentType = response.headers.get('content-type');
    const isJson = contentType && contentType.includes('application/json');
    const data = isJson ? await response.json() : await response.text();

    if (!response.ok) {
      const errorMessage =
        (typeof data === 'object' && (data.detail || data.message || data.error)) ||
        response.statusText ||
        'API request failed';
      throw new ApiError(errorMessage, response.status, data);
    }

    return data;
  } catch (err) {
    clearTimeout(timeoutId);

    if (err.name === 'AbortError') {
      throw new ApiError('Request timed out. Please verify backend connectivity.', 408);
    }

    if (err instanceof ApiError) {
      throw err;
    }

    throw new ApiError(
      err.message || 'Network error: Failed to communicate with FastAPI backend',
      0
    );
  }
};

export default apiClient;
