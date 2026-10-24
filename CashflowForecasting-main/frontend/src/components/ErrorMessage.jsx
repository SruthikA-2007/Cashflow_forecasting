import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

/**
 * Reusable ErrorMessage component for financial analytics
 * @param {string} title - Error title
 * @param {string} message - Error details or guidance
 * @param {Function} onRetry - Optional retry callback
 * @param {'card'|'banner'|'inline'} variant - Layout style
 */
export const ErrorMessage = ({
  title = 'An error occurred',
  message = 'Unable to load financial analytics data. Please try again.',
  onRetry,
  variant = 'card',
  className = '',
}) => {
  if (variant === 'inline') {
    return (
      <div
        className={`error-inline ${className}`}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          color: 'var(--risk-high)',
          fontSize: '0.82rem',
          padding: '0.5rem 0',
        }}
        role="alert"
      >
        <AlertCircle size={16} style={{ flexShrink: 0 }} />
        <span>{message || title}</span>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--primary)',
              cursor: 'pointer',
              textDecoration: 'underline',
              fontSize: '0.8rem',
              marginLeft: 'auto',
            }}
          >
            Retry
          </button>
        )}
      </div>
    );
  }

  return (
    <div
      className={`alert-card high ${className}`}
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '0.85rem',
        padding: '1.25rem',
        borderRadius: 'var(--radius-md)',
        backgroundColor: 'var(--risk-high-bg)',
        borderLeft: '4px solid var(--risk-high)',
      }}
      role="alert"
    >
      <AlertCircle size={20} style={{ color: 'var(--risk-high)', flexShrink: 0, marginTop: '2px' }} />
      <div style={{ flexGrow: 1 }}>
        <h4 style={{ fontSize: '0.92rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.2rem' }}>
          {title}
        </h4>
        {message && (
          <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
            {message}
          </p>
        )}
        {onRetry && (
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={onRetry}
            style={{ marginTop: '0.75rem', gap: '0.35rem', fontSize: '0.78rem' }}
          >
            <RefreshCw size={13} /> Retry
          </button>
        )}
      </div>
    </div>
  );
};

export default ErrorMessage;
