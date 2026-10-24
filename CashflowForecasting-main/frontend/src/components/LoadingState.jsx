import React from 'react';
import { Loader2 } from 'lucide-react';

/**
 * Reusable LoadingState component for financial views, tables, and cards
 * @param {string} message - Optional text to display
 * @param {'spinner'|'skeleton'|'table'} type - Visual representation
 * @param {number} rows - Number of skeleton rows if type is 'table' or 'skeleton'
 * @param {string} height - Minimum container height
 */
export const LoadingState = ({
  message = 'Loading data...',
  type = 'spinner',
  rows = 4,
  height = '200px',
  className = '',
}) => {
  if (type === 'table') {
    return (
      <div className={`table-loading-container ${className}`} style={{ padding: '1.5rem', width: '100%' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
          {Array.from({ length: rows }).map((_, i) => (
            <div
              key={i}
              className="skeleton-row"
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(80px, 1fr))',
                gap: '1rem',
                padding: '0.75rem',
                borderRadius: '6px',
                backgroundColor: 'var(--bg-surface-subtle)',
              }}
            >
              <div className="skeleton" style={{ height: '16px', width: '70%' }} />
              <div className="skeleton" style={{ height: '16px', width: '85%' }} />
              <div className="skeleton" style={{ height: '16px', width: '50%' }} />
              <div className="skeleton" style={{ height: '16px', width: '60%' }} />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (type === 'skeleton') {
    return (
      <div className={`skeleton-container ${className}`} style={{ padding: '1rem', width: '100%', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="skeleton" style={{ height: '24px', width: `${90 - i * 10}%` }} />
        ))}
      </div>
    );
  }

  return (
    <div
      className={`loading-state-wrapper ${className}`}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: height,
        padding: '2rem',
        gap: '0.85rem',
        color: 'var(--text-secondary)',
      }}
      role="status"
    >
      <Loader2
        size={28}
        className="animate-spin"
        style={{ color: 'var(--primary)', animation: 'spin 1s linear infinite' }}
      />
      {message && <span style={{ fontSize: '0.875rem', fontWeight: 500 }}>{message}</span>}
    </div>
  );
};

export default LoadingState;
