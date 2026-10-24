import React from 'react';

/**
 * Reusable PageHeader component for financial analytics views
 * @param {string} title - Main page heading
 * @param {string} subtitle - Explanatory context for the view
 * @param {React.ReactNode} badge - Optional status or version pill
 * @param {React.ReactNode} actions - Optional button group or filter controls
 */
export const PageHeader = ({ title, subtitle, badge, actions, children }) => {
  return (
    <div className="page-header" style={{ marginBottom: '1.5rem' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <h2 className="page-title">{title}</h2>
          {badge && <div className="page-header-badge">{badge}</div>}
        </div>
        {subtitle && <p className="page-subtitle">{subtitle}</p>}
      </div>

      {(actions || children) && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          {actions}
          {children}
        </div>
      )}
    </div>
  );
};

export default PageHeader;
