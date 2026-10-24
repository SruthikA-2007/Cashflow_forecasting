/**
 * Authentication API Service
 * Handles email OTP dispatch, verification, profile retrieval, and logout.
 */

import { ENDPOINTS } from '../../config/apiConfig';
import apiClient from './apiClient';

export const authApi = {
  /**
   * Request a 6-digit OTP to be sent to the specified email address.
   * Accepts any valid email domain.
   */
  sendOtp: async (email) => {
    return apiClient(ENDPOINTS.AUTH_SEND_OTP, {
      method: 'POST',
      body: JSON.stringify({ email: email.trim().toLowerCase() }),
    });
  },

  /**
   * Verify the 6-digit OTP and obtain authenticated session token.
   */
  verifyOtp: async (email, otp) => {
    return apiClient(ENDPOINTS.AUTH_VERIFY_OTP, {
      method: 'POST',
      body: JSON.stringify({
        email: email.trim().toLowerCase(),
        otp: otp.trim(),
      }),
    });
  },

  /**
   * Revoke active session on the backend.
   */
  logout: async () => {
    try {
      return await apiClient(ENDPOINTS.AUTH_LOGOUT, {
        method: 'POST',
      });
    } catch (err) {
      // Even if network or token is already invalid, client logout proceeds
      console.warn('Backend logout notification warning:', err);
      return null;
    }
  },

  /**
   * Fetch profile for current authenticated session.
   */
  getMe: async () => {
    return apiClient(ENDPOINTS.AUTH_ME, {
      method: 'GET',
    });
  },

  /**
   * Check SMTP configuration status.
   */
  getSmtpStatus: async () => {
    return apiClient(ENDPOINTS.AUTH_SMTP_STATUS, {
      method: 'GET',
    });
  },
};

export default authApi;
