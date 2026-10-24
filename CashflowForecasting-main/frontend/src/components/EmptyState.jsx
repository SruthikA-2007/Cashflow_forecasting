import React from 'react';
import { FolderOpen } from 'lucide-react';

/**
 * Reusable EmptyState component for tables, lists, and view containers
 * @param {string} title - Main headline
 * @param {string} description - Secondary message or instructions
 * @param {React.ComponentType} icon - Optional Lucide icon
 * @param {React.ReactNode} action - Optional action button/link
 * @param {string} height - Container minimum height
 */
export const EmptyState = ({
  title = 'No records found',
  description = 'There is currently no data to display for the selected criteria.',
  icon: Icon = FolderOpen,
  action,
  height = '220px',
  className = '',
}) => {
  return (
    <div
      className={`empty-state-container ${className}`}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: height,
        padding: '2.5rem 1.5rem',
        textAlign: 'center',
        color: 'var(--text-secondary)',
      }}
    >
      <div
        style={{
          width: '48px',
          height: '48px',
          borderRadius: '50%',
          backgroundColor: 'var(--bg-surface-elevated)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--text-muted)',
          marginBottom: '0.85rem',
        }}
      >
        <Icon size={24} />
      </div>

      <h4 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.25rem' }}>
        {title}
      </h4>

      {description && (
        <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', maxWidth: '360px', lineHeight: 1.4, marginBottom: action ? '1rem' : 0 }}>
          {description}
        </p>
      )}

      {action && <div>{action}</div>}
    </div>
  );
};

export default EmptyState;
