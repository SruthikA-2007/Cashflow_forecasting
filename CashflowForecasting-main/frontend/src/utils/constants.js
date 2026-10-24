export const APP_NAME = 'Cash Flow Early Warning System';

export const NAV_ITEMS = [
  {
    path: '/',
    label: 'Dashboard',
    icon: 'LayoutDashboard',
    description: 'Executive overview & cash liquidity'
  },
  {
    path: '/data-management',
    label: 'Data Management',
    icon: 'Database',
    description: 'Dataset ingestion & schema validation'
  },
  {
    path: '/invoice-risk',
    label: 'Predict Invoice Payment Risk',
    icon: 'FileSpreadsheet',
    description: 'Payment delay forecasts & risk flags'
  },
  {
    path: '/customer-risk',
    label: 'Customer Risk',
    icon: 'Users',
    description: 'Creditworthiness & default exposure'
  }
];

export const RISK_LEVELS = {
  LOW: {
    key: 'low',
    label: 'Low Risk',
    badgeClass: 'badge-low',
    bgLight: 'rgba(16, 185, 129, 0.1)',
    color: '#10b981',
    description: 'Expected to pay on schedule (< 5 days variance)'
  },
  MEDIUM: {
    key: 'medium',
    label: 'Medium Risk',
    badgeClass: 'badge-medium',
    bgLight: 'rgba(245, 158, 11, 0.1)',
    color: '#f59e0b',
    description: 'Moderate delay probability (5–15 days variance)'
  },
  HIGH: {
    key: 'high',
    label: 'High Risk',
    badgeClass: 'badge-high',
    bgLight: 'rgba(239, 68, 68, 0.1)',
    color: '#ef4444',
    description: 'Critical delay probability (> 15 days or default risk)'
  }
};
