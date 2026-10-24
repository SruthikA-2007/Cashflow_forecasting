import React, { useState } from 'react';
import { formatCompactCurrency } from '../utils/formatters';

export const CashFlowChart = ({ data = [] }) => {
  const [hoveredPoint, setHoveredPoint] = useState(null);

  if (!data || data.length === 0) {
    return <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '2rem' }}>No forecast data available</div>;
  }

  // SVG canvas bounds
  const width = 800;
  const height = 260;
  const padding = { top: 20, right: 30, bottom: 40, left: 60 };

  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  // Find min and max values for scale
  const allValues = data.flatMap((d) => [
    d.actual,
    d.forecast,
    d.lowerBound,
    d.upperBound,
  ]).filter((v) => v !== null && v !== undefined);

  const minVal = Math.floor((Math.min(...allValues) * 0.95) / 10000) * 10000;
  const maxVal = Math.ceil((Math.max(...allValues) * 1.05) / 10000) * 10000;

  const getX = (index) => padding.left + (index / (data.length - 1)) * chartWidth;
  const getY = (val) => {
    if (val === null || val === undefined) return null;
    return padding.top + chartHeight - ((val - minVal) / (maxVal - minVal)) * chartHeight;
  };

  // Build actual line path
  const actualPoints = data
    .map((d, i) => (d.actual !== null ? `${getX(i)},${getY(d.actual)}` : null))
    .filter(Boolean);
  const actualPath = actualPoints.length > 0 ? `M ${actualPoints.join(' L ')}` : '';

  // Build forecast line path
  const forecastPoints = data
    .map((d, i) => (d.forecast !== null ? `${getX(i)},${getY(d.forecast)}` : null))
    .filter(Boolean);
  const forecastPath = forecastPoints.length > 0 ? `M ${forecastPoints.join(' L ')}` : '';

  // Build confidence interval polygon
  const confidenceData = data.filter((d) => d.lowerBound !== null && d.upperBound !== null);
  let confidencePath = '';
  if (confidenceData.length > 0) {
    const upperPoints = data
      .map((d, i) => (d.upperBound !== null ? `${getX(i)},${getY(d.upperBound)}` : null))
      .filter(Boolean);
    const lowerPoints = data
      .map((d, i) => (d.lowerBound !== null ? `${getX(i)},${getY(d.lowerBound)}` : null))
      .filter(Boolean)
      .reverse();
    if (upperPoints.length > 0 && lowerPoints.length > 0) {
      confidencePath = `M ${upperPoints.join(' L ')} L ${lowerPoints.join(' L ')} Z`;
    }
  }

  // Y-axis grid ticks (4 ticks)
  const yTicks = [0, 0.33, 0.66, 1].map((pct) => {
    const value = minVal + pct * (maxVal - minVal);
    const yPos = padding.top + chartHeight - pct * chartHeight;
    return { value, yPos };
  });

  return (
    <div style={{ width: '100%', position: 'relative' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '1.25rem', marginBottom: '0.75rem', fontSize: '0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <span style={{ width: '12px', height: '3px', backgroundColor: 'var(--text-primary)', borderRadius: '2px' }} />
          <span style={{ color: 'var(--text-secondary)' }}>Actual Balance</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <span style={{ width: '12px', height: '3px', backgroundColor: 'var(--primary)', borderStyle: 'dashed', borderRadius: '2px' }} />
          <span style={{ color: 'var(--text-secondary)' }}>Projected Forecast</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <span style={{ width: '10px', height: '10px', backgroundColor: 'var(--primary-light)', borderRadius: '2px' }} />
          <span style={{ color: 'var(--text-muted)' }}>95% Confidence Band</span>
        </div>
      </div>

      <div className="chart-container">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="svg-chart"
          preserveAspectRatio="none"
        >
          <defs>
            <linearGradient id="forecastGlow" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#7c3aed" stopOpacity="0.2" />
              <stop offset="100%" stopColor="#7c3aed" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Y-axis grid lines and labels */}
          {yTicks.map((tick, i) => (
            <g key={i}>
              <line
                x1={padding.left}
                y1={tick.yPos}
                x2={width - padding.right}
                y2={tick.yPos}
                stroke="var(--border-subtle)"
                strokeDasharray="3 3"
              />
              <text
                x={padding.left - 10}
                y={tick.yPos + 4}
                textAnchor="end"
                fontSize="10"
                fill="var(--text-muted)"
                fontFamily="var(--font-mono)"
              >
                {formatCompactCurrency(tick.value)}
              </text>
            </g>
          ))}

          {/* Confidence interval area */}
          {confidencePath && (
            <path
              d={confidencePath}
              fill="url(#forecastGlow)"
              opacity="0.5"
            />
          )}

          {/* Actual balance line */}
          {actualPath && (
            <path
              d={actualPath}
              fill="none"
              stroke="var(--text-primary)"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* Forecast balance line */}
          {forecastPath && (
            <path
              d={forecastPath}
              fill="none"
              stroke="var(--primary)"
              strokeWidth="2.5"
              strokeDasharray="5 5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* X-axis labels and points */}
          {data.map((d, i) => {
            const x = getX(i);
            const y = d.forecast !== null ? getY(d.forecast) : getY(d.actual);
            const isHovered = hoveredPoint === i;

            return (
              <g key={i}>
                <text
                  x={x}
                  y={height - padding.bottom + 18}
                  textAnchor="middle"
                  fontSize="10"
                  fill={isHovered ? 'var(--text-primary)' : 'var(--text-muted)'}
                  fontWeight={isHovered ? '600' : '400'}
                >
                  {d.month || d.date || `M${i + 1}`}
                </text>

                {/* Point dot */}
                {y !== null && (
                  <circle
                    cx={x}
                    cy={y}
                    r={isHovered ? 5 : 3.5}
                    fill={d.forecast !== null ? 'var(--primary)' : 'var(--text-primary)'}
                    stroke="var(--bg-surface)"
                    strokeWidth="2"
                    style={{ cursor: 'pointer', transition: 'r 0.15s ease' }}
                    onMouseEnter={() => setHoveredPoint(i)}
                    onMouseLeave={() => setHoveredPoint(null)}
                  />
                )}
              </g>
            );
          })}
        </svg>

        {/* Tooltip */}
        {hoveredPoint !== null && data[hoveredPoint] && (
          <div
            style={{
              position: 'absolute',
              left: `${(getX(hoveredPoint) / width) * 100}%`,
              top: '10px',
              transform: 'translateX(-50%)',
              backgroundColor: 'var(--bg-surface-elevated)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-sm)',
              padding: '0.4rem 0.6rem',
              fontSize: '0.75rem',
              boxShadow: 'var(--shadow-md)',
              pointerEvents: 'none',
              zIndex: 10,
              whiteSpace: 'nowrap',
            }}
          >
            <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
              {data[hoveredPoint].month || data[hoveredPoint].date}
            </div>
            {data[hoveredPoint].actual !== null && (
              <div style={{ color: 'var(--text-secondary)' }}>
                Actual: {formatCompactCurrency(data[hoveredPoint].actual)}
              </div>
            )}
            {data[hoveredPoint].forecast !== null && (
              <div style={{ color: 'var(--primary)' }}>
                Forecast: {formatCompactCurrency(data[hoveredPoint].forecast)}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default CashFlowChart;
