import React from 'react';
import { ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react';

/**
 * Reusable SummaryCard component for financial KPIs and metrics
 * @param {string} title - KPI label
 * @param {string|number} value - Formatted value to display
 * @param {number} change - Percentage change value
 * @param {string} changeText - Context string (e.g. "vs last month")
 * @param {React.ComponentType} icon - Lucide icon component
 * @param {boolean} isNegativeGood - True if negative change is favorable (e.g. DSO decrease, risk decrease)
 * @param {string} helperText - Additional subtext
 * @param {boolean} loading - Displays loading skeleton
 */
export const SummaryCard = ({
  title,
  value,
  change,
  changeText,
  icon: Icon,
  isNegativeGood = false,
  helperText,
  loading = false,
}) => {
  if (loading) {
    return (
      <div className="stat-card" style={{ minHeight: '130px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
          <div className="skeleton" style={{ width: '40%', height: '14px' }} />
          <div className="skeleton" style={{ width: '32px', height: '32px', borderRadius: '8px' }} />
        </div>
        <div className="skeleton" style={{ width: '65%', height: '28px', marginBottom: '0.75rem' }} />
        <div className="skeleton" style={{ width: '50%', height: '12px' }} />
      </div>
    );
  }

  const isPositive = typeof change === 'number' && change > 0;
  const isNegative = typeof change === 'number' && change < 0;
  const isNeutral = typeof change === 'number' && change === 0;
  const hasChange = typeof change === 'number';

  let trendClass = 'neutral';
  if (isPositive) {
    trendClass = isNegativeGood ? 'negative' : 'positive';
  } else if (isNegative) {
    trendClass = isNegativeGood ? 'positive' : 'negative';
  }

  return (
    <div className="stat-card">
      <div className="stat-card-header">
        <span className="stat-label">{title}</span>
        {Icon && (
          <div className="stat-icon-wrapper">
            <Icon size={18} />
          </div>
        )}
      </div>

      <div className="stat-value">{value ?? '—'}</div>

      <div className="stat-footer">
        {hasChange && (
          <span className={`stat-trend ${trendClass}`}>
            {isPositive && <ArrowUpRight size={14} />}
            {isNegative && <ArrowDownRight size={14} />}
            {isNeutral && <Minus size={14} />}
            {Math.abs(change)}%
          </span>
        )}
        {changeText && <span className="stat-meta">{changeText}</span>}
        {helperText && !changeText && <span className="stat-meta">{helperText}</span>}
      </div>
    </div>
  );
};

export default SummaryCard;
