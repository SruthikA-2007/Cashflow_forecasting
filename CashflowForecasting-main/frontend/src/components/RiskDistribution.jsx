import React from 'react';
import { formatCompactCurrency } from '../utils/formatters';

export const RiskDistribution = ({ distribution }) => {
  if (!distribution) return null;

  const { low, medium, high } = distribution;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* Multi-segment Progress Bar */}
      <div
        style={{
          display: 'flex',
          height: '10px',
          borderRadius: '9999px',
          overflow: 'hidden',
          backgroundColor: 'var(--bg-surface-elevated)',
          width: '100%',
        }}
      >
        <div
          style={{
            width: `${low.percentage}%`,
            backgroundColor: 'var(--risk-low)',
            transition: 'width 0.3s ease',
          }}
          title={`Low Risk: ${low.percentage}%`}
        />
        <div
          style={{
            width: `${medium.percentage}%`,
            backgroundColor: 'var(--risk-medium)',
            transition: 'width 0.3s ease',
          }}
          title={`Medium Risk: ${medium.percentage}%`}
        />
        <div
          style={{
            width: `${high.percentage}%`,
            backgroundColor: 'var(--risk-high)',
            transition: 'width 0.3s ease',
          }}
          title={`High Risk: ${high.percentage}%`}
        />
      </div>

      {/* Legend & Key figures */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.75rem' }}>
        <div
          style={{
            padding: '0.75rem',
            backgroundColor: 'var(--bg-surface-subtle)',
            borderRadius: '8px',
            border: '1px solid var(--border-subtle)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.75rem', color: 'var(--risk-low)' }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: 'var(--risk-low)' }} />
            Low Risk ({low.percentage}%)
          </div>
          <div style={{ fontSize: '1.05rem', fontWeight: 700, marginTop: '0.25rem' }}>
            {formatCompactCurrency(low.amount)}
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{low.count} invoices</div>
        </div>

        <div
          style={{
            padding: '0.75rem',
            backgroundColor: 'var(--bg-surface-subtle)',
            borderRadius: '8px',
            border: '1px solid var(--border-subtle)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.75rem', color: 'var(--risk-medium)' }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: 'var(--risk-medium)' }} />
            Medium Risk ({medium.percentage}%)
          </div>
          <div style={{ fontSize: '1.05rem', fontWeight: 700, marginTop: '0.25rem' }}>
            {formatCompactCurrency(medium.amount)}
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{medium.count} invoices</div>
        </div>

        <div
          style={{
            padding: '0.75rem',
            backgroundColor: 'var(--bg-surface-subtle)',
            borderRadius: '8px',
            border: '1px solid var(--border-subtle)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.75rem', color: 'var(--risk-high)' }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: 'var(--risk-high)' }} />
            High Risk ({high.percentage}%)
          </div>
          <div style={{ fontSize: '1.05rem', fontWeight: 700, marginTop: '0.25rem' }}>
            {formatCompactCurrency(high.amount)}
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{high.count} invoices</div>
        </div>
      </div>
    </div>
  );
};

export default RiskDistribution;
