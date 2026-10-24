import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  Mail,
  ShieldCheck,
  AlertCircle,
  CheckCircle2,
  Clock,
  ArrowRight,
  RefreshCw,
  KeyRound,
} from 'lucide-react';

export const Login = () => {
  const { user, isAuthenticated, sendOtp, verifyOtp } = useAuth();
  const navigate = useNavigate();

  // Form State
  const [step, setStep] = useState('email'); // 'email' | 'otp'
  const [email, setEmail] = useState('');
  const [otpDigits, setOtpDigits] = useState(['', '', '', '', '', '']);

  // UI Status State
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [infoMessage, setInfoMessage] = useState('');
  const [cooldown, setCooldown] = useState(0);

  // Input refs for 6-digit OTP fields
  const otpInputsRef = useRef([]);

  // Active cooldown countdown timer
  useEffect(() => {
    let timer;
    if (cooldown > 0) {
      timer = setInterval(() => {
        setCooldown((prev) => (prev > 0 ? prev - 1 : 0));
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [cooldown]);

  // If already authenticated, redirect to dashboard
  if (isAuthenticated && user) {
    return <Navigate to="/" replace />;
  }

  // Handle Step 1: Send OTP to Email
  const handleSendOtp = async (e) => {
    if (e) e.preventDefault();
    setError('');
    setSuccessMessage('');
    setInfoMessage('');

    const trimmedEmail = email.trim().toLowerCase();
    if (!trimmedEmail) {
      setError('Please enter your email address.');
      return;
    }

    const emailRegex = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;
    if (!emailRegex.test(trimmedEmail)) {
      setError('Please enter a valid email address (e.g., name@gmail.com, user@outlook.com, or company email).');
      return;
    }

    setLoading(true);
    try {
      const response = await sendOtp(trimmedEmail);
      setSuccessMessage(
        response?.message || `A 6-digit verification code has been sent to ${trimmedEmail}. Code expires in 5 minutes.`
      );
      setCooldown(response?.cooldown_seconds || 60);
      setStep('otp');
      setOtpDigits(['', '', '', '', '', '']);

      // Focus first OTP input after transition
      setTimeout(() => {
        if (otpInputsRef.current[0]) {
          otpInputsRef.current[0].focus();
        }
      }, 100);
    } catch (err) {
      const msg = err.message || 'Failed to send OTP.';
      // Differentiate email delivery failure from rate limits or client errors
      if (err.status === 429) {
        setError(msg);
      } else if (err.status === 502 || msg.toLowerCase().includes('smtp') || msg.toLowerCase().includes('delivery')) {
        setError(`Email delivery failure: ${msg}`);
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  };

  // Handle Resend OTP
  const handleResendOtp = async () => {
    if (cooldown > 0 || loading) return;
    setError('');
    setSuccessMessage('');
    setLoading(true);

    try {
      const response = await sendOtp(email);
      setSuccessMessage(
        response?.message || `A new verification code has been sent to ${email}. Previous code is invalidated.`
      );
      setCooldown(response?.cooldown_seconds || 60);
      setOtpDigits(['', '', '', '', '', '']);
      if (otpInputsRef.current[0]) {
        otpInputsRef.current[0].focus();
      }
    } catch (err) {
      setError(err.message || 'Failed to resend verification code.');
    } finally {
      setLoading(false);
    }
  };

  // Handle OTP digit changes
  const handleOtpChange = (index, value) => {
    setError('');
    // Allow single numeric character
    if (value && !/^\d+$/.test(value)) return;

    const newDigits = [...otpDigits];
    newDigits[index] = value.slice(-1); // keep last typed char
    setOtpDigits(newDigits);

    // Auto advance to next box
    if (value && index < 5 && otpInputsRef.current[index + 1]) {
      otpInputsRef.current[index + 1].focus();
    }
  };

  // Handle Backspace and arrow navigation
  const handleKeyDown = (index, e) => {
    if (e.key === 'Backspace' && !otpDigits[index] && index > 0) {
      otpInputsRef.current[index - 1].focus();
    } else if (e.key === 'ArrowLeft' && index > 0) {
      otpInputsRef.current[index - 1].focus();
    } else if (e.key === 'ArrowRight' && index < 5) {
      otpInputsRef.current[index + 1].focus();
    }
  };

  // Handle pasting full 6-digit code
  const handlePaste = (e) => {
    e.preventDefault();
    const pastedData = e.clipboardData.getData('text').trim();
    if (/^\d{6}$/.test(pastedData)) {
      const digits = pastedData.split('');
      setOtpDigits(digits);
      if (otpInputsRef.current[5]) {
        otpInputsRef.current[5].focus();
      }
    }
  };

  // Handle Step 2: Verify OTP
  const handleVerifyOtp = async (e) => {
    if (e) e.preventDefault();
    setError('');

    const fullOtp = otpDigits.join('');
    if (fullOtp.length !== 6) {
      setError('Please enter all 6 digits of your verification code.');
      return;
    }

    setLoading(true);
    try {
      await verifyOtp(email, fullOtp);
      setSuccessMessage('Verification successful! Access granted. Redirecting to dashboard...');
      setTimeout(() => {
        navigate('/', { replace: true });
      }, 500);
    } catch (err) {
      const msg = err.message || 'Invalid or expired verification code.';
      setError(msg);
      // If code was invalid or expired, allow re-entry
      if (err.status === 400 || err.status === 429) {
        setOtpDigits(['', '', '', '', '', '']);
        if (otpInputsRef.current[0]) {
          otpInputsRef.current[0].focus();
        }
      }
    } finally {
      setLoading(false);
    }
  };

  // Switch back to Step 1: Change email
  const handleChangeEmail = () => {
    setStep('email');
    setError('');
    setSuccessMessage('');
    setOtpDigits(['', '', '', '', '', '']);
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-header">
          <div className="login-logo-badge">
            <ShieldCheck size={28} />
          </div>
          <h1 className="login-title">Cash Flow Early Warning</h1>
          <p className="login-subtitle">
            {step === 'email'
              ? 'Enter your email to receive a secure 6-digit OTP'
              : 'Enter the 6-digit code sent to your email'}
          </p>
        </div>

        {/* Clear Status Messages */}
        {error && (
          <div className="login-alert login-alert-error" role="alert">
            <AlertCircle size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
            <span>{error}</span>
          </div>
        )}

        {successMessage && (
          <div className="login-alert login-alert-success" role="status">
            <CheckCircle2 size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
            <span>{successMessage}</span>
          </div>
        )}

        {infoMessage && (
          <div className="login-alert login-alert-info">
            <Clock size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
            <span>{infoMessage}</span>
          </div>
        )}

        {/* STEP 1: Email Form */}
        {step === 'email' && (
          <form onSubmit={handleSendOtp} className="login-form">
            <div className="login-field">
              <label htmlFor="login-email">Email Address</label>
              <div className="login-input-wrapper">
                <Mail size={18} className="login-input-icon" />
                <input
                  id="login-email"
                  type="email"
                  className="login-input"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (error) setError('');
                  }}
                  placeholder="name@company.com or personal email"
                  required
                  autoFocus
                  disabled={loading}
                />
              </div>
              <span className="login-field-hint">
                Accepts any valid email address (Gmail, Outlook, company domains, etc.).
              </span>
            </div>

            <button
              type="submit"
              className="login-submit-btn"
              disabled={loading || !email.trim()}
            >
              {loading ? (
                <>
                  <RefreshCw size={18} className="animate-spin" />
                  <span>Sending Verification Code...</span>
                </>
              ) : (
                <>
                  <span>Send OTP</span>
                  <ArrowRight size={18} />
                </>
              )}
            </button>
          </form>
        )}

        {/* STEP 2: 6-Digit OTP Form */}
        {step === 'otp' && (
          <form onSubmit={handleVerifyOtp} className="login-form">
            <div className="login-active-email-badge">
              <div className="login-active-email-info">
                <span className="login-active-email-label">Verification Sent To</span>
                <span className="login-active-email-value">{email}</span>
              </div>
              <button
                type="button"
                onClick={handleChangeEmail}
                className="login-change-email-btn"
                disabled={loading}
              >
                Change Email
              </button>
            </div>

            <div className="login-field">
              <label htmlFor="otp-digit-0">Enter 6-Digit Passcode</label>
              <div
                className="otp-inputs-grid"
                onPaste={handlePaste}
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(6, 1fr)',
                  gap: '0.5rem',
                  width: '100%',
                  maxWidth: '100%',
                  boxSizing: 'border-box',
                }}
              >
                {otpDigits.map((digit, index) => (
                  <input
                    key={index}
                    id={`otp-digit-${index}`}
                    ref={(el) => (otpInputsRef.current[index] = el)}
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]*"
                    maxLength={1}
                    className="otp-digit-box"
                    style={{
                      width: '100%',
                      minWidth: 0,
                      maxWidth: '100%',
                      boxSizing: 'border-box',
                      textAlign: 'center',
                      padding: 0,
                    }}
                    value={digit}
                    onChange={(e) => handleOtpChange(index, e.target.value)}
                    onKeyDown={(e) => handleKeyDown(index, e)}
                    disabled={loading}
                    autoComplete="one-time-code"
                  />
                ))}
              </div>
              <span className="login-field-hint" style={{ textAlign: 'center' }}>
                Code expires in <strong>5 minutes</strong>. One-time use only.
              </span>
            </div>

            <button
              type="submit"
              className="login-submit-btn"
              disabled={loading || otpDigits.join('').length !== 6}
            >
              {loading ? (
                <>
                  <RefreshCw size={18} className="animate-spin" />
                  <span>Verifying Passcode...</span>
                </>
              ) : (
                <>
                  <KeyRound size={18} />
                  <span>Verify &amp; Access Dashboard</span>
                </>
              )}
            </button>

            <div className="login-otp-footer">
              <button
                type="button"
                onClick={handleResendOtp}
                className="resend-btn"
                disabled={cooldown > 0 || loading}
              >
                <RefreshCw size={14} />
                <span>Resend Code</span>
              </button>

              {cooldown > 0 && (
                <div className="cooldown-badge">
                  <Clock size={13} />
                  <span>Resend in {cooldown}s</span>
                </div>
              )}
            </div>
          </form>
        )}
      </div>
    </div>
  );
};

export default Login;
