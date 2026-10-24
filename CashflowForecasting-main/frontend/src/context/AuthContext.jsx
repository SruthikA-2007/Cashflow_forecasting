import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import authApi from '../services/api/authApi';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(() => {
    try {
      return localStorage.getItem('fin_token') || null;
    } catch {
      return null;
    }
  });

  const [user, setUser] = useState(() => {
    try {
      const saved = localStorage.getItem('fin_user');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  const [authLoading, setAuthLoading] = useState(true);

  // Validate session token on mount
  useEffect(() => {
    const verifySession = async () => {
      const storedToken = localStorage.getItem('fin_token');
      if (!storedToken) {
        setAuthLoading(false);
        return;
      }

      try {
        const profile = await authApi.getMe();
        if (profile && profile.email) {
          const userData = { email: profile.email, id: profile.id || profile.email };
          setUser(userData);
          localStorage.setItem('fin_user', JSON.stringify(userData));
        }
      } catch (err) {
        // If 401 Unauthorized or expired token, clear session
        if (err.status === 401) {
          console.warn('Session expired or invalidated. Clearing local auth state.');
          localStorage.removeItem('fin_token');
          localStorage.removeItem('fin_user');
          setToken(null);
          setUser(null);
        }
      } finally {
        setAuthLoading(false);
      }
    };

    verifySession();
  }, []);

  /**
   * Request OTP to be sent to user's email.
   * Accepts any valid email address from any domain.
   */
  const sendOtp = async (email) => {
    const trimmed = (email || '').trim().toLowerCase();
    if (!trimmed) {
      throw new Error('Email address is required.');
    }

    const emailRegex = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;
    if (!emailRegex.test(trimmed)) {
      throw new Error('Please enter a valid email address.');
    }

    return await authApi.sendOtp(trimmed);
  };

  /**
   * Verify OTP code and establish authenticated session.
   */
  const verifyOtp = async (email, otp) => {
    const trimmedEmail = (email || '').trim().toLowerCase();
    const trimmedOtp = (otp || '').trim();

    if (!trimmedEmail) {
      throw new Error('Email address is required.');
    }
    if (!trimmedOtp || trimmedOtp.length !== 6) {
      throw new Error('Please enter the 6-digit verification code.');
    }

    const response = await authApi.verifyOtp(trimmedEmail, trimmedOtp);

    if (response && response.token) {
      const sessionUser = response.user || { email: trimmedEmail, id: trimmedEmail };
      localStorage.setItem('fin_token', response.token);
      localStorage.setItem('fin_user', JSON.stringify(sessionUser));
      setToken(response.token);
      setUser(sessionUser);
      return response;
    }

    throw new Error('Verification failed. No session token received.');
  };

  /**
   * Log out, revoke session on backend, and clear local state.
   */
  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch (err) {
      console.warn('Backend logout warning:', err);
    } finally {
      localStorage.removeItem('fin_token');
      localStorage.removeItem('fin_user');
      setToken(null);
      setUser(null);
    }
  }, []);

  const isAuthenticated = Boolean(user && token);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated,
        authLoading,
        sendOtp,
        verifyOtp,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export default AuthContext;
