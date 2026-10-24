import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Database,
  FileSpreadsheet,
  Users,
  Activity,
  ShieldCheck,
  LogOut,
} from 'lucide-react';
import { APP_NAME } from '../utils/constants';
import { useDataset } from '../context/DatasetContext';
import { useAuth } from '../context/AuthContext';

const icons = {
  LayoutDashboard,
  Database,
  FileSpreadsheet,
  Users,
};

export const Sidebar = ({ isOpen, onClose }) => {
  const { backendConnected } = useDataset();
  const { user, logout } = useAuth();

  const navItems = [
    {
      path: '/',
      label: 'Dashboard',
      icon: LayoutDashboard,
    },
    {
      path: '/data-management',
      label: 'Data Management',
      icon: Database,
    },
    {
      path: '/invoice-risk',
      label: 'Predict Invoice Payment Risk',
      icon: FileSpreadsheet,
    },
    {
      path: '/customer-risk',
      label: 'Customer Risk',
      icon: Users,
    },
  ];

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          onClick={onClose}
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0,0,0,0.6)',
            zIndex: 45,
          }}
        />
      )}

      <aside className={`app-sidebar ${isOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '8px',
              backgroundColor: 'var(--primary-subtle)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--primary)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <Activity size={18} />
          </div>
          <div className="sidebar-brand-text">
            <span className="sidebar-brand-title">{APP_NAME}</span>
            <span className="sidebar-brand-subtitle">Risk Management</span>
          </div>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-section-title">Navigation</div>

          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  `nav-item ${isActive ? 'active' : ''}`
                }
                onClick={onClose}
                end={item.path === '/'}
              >
                <Icon className="nav-icon" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          {user && (
            <div className="sidebar-user-card">
              <span className="sidebar-user-email" title={user.email}>{user.email}</span>
              <button
                onClick={logout}
                className="sidebar-logout-btn"
                title="Logout"
                aria-label="Logout"
              >
                <LogOut size={14} />
              </button>
            </div>
          )}
          <div className="system-status-indicator">
            <span className="status-dot" style={{ backgroundColor: backendConnected ? '#059669' : '#d97706' }} />
            <span>{backendConnected ? 'FastAPI Backend: Connected' : 'Risk Engine: Local Mode'}</span>
          </div>
        </div>
      </aside>
    </>
  );
};

export default Sidebar;
