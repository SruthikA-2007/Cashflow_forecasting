import React from 'react';

/**
 * Reusable RiskBadge component for financial risk tiers
 * Specifically supports:
 * - Low Risk
 * - Medium Risk
 * - High Risk
 *
 * @param {'Low'|'Medium'|'High'|'Low Risk'|'Medium Risk'|'High Risk'|string} level - Risk tier
 * @param {number} [score] - Optional 0-100 risk score
 * @param {'sm'|'md'|'lg'} [size='sm'] - Badge size
 * @param {boolean} [showDot=true] - Whether to render status indicator dot
 */
export const RiskBadge = ({
  level = 'Low',
  score,
  size = 'sm',
  showDot = true,
  className = '',
}) => {
  const normalized = String(level || 'Low').trim().toLowerCase();

  let riskTier = 'low';
  let displayLabel = 'Low Risk';

  if (normalized.includes('high') || normalized.includes('critical')) {
    riskTier = 'high';
    displayLabel = 'High Risk';
  } else if (normalized.includes('medium') || normalized.includes('mod') || normalized.includes('med')) {
    riskTier = 'medium';
    displayLabel = 'Medium Risk';
  } else {
    riskTier = 'low';
    displayLabel = 'Low Risk';
  }

  const badgeClass = `risk-badge badge-${riskTier} badge-size-${size} ${className}`.trim();

  return (
    <span className={badgeClass} role="status" aria-label={`${displayLabel}${score !== undefined ? ` score ${score}` : ''}`}>
      {showDot && <span className="badge-dot" aria-hidden="true" />}
      <span className="badge-text">{displayLabel}</span>
      {score !== undefined && score !== null && (
        <span className="badge-score" style={{ opacity: 0.85, fontWeight: 500, marginLeft: '3px' }}>
          ({score})
        </span>
      )}
    </span>
  );
};

export default RiskBadge;
