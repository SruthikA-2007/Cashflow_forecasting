import React, { useState } from 'react';
import { Menu, LogOut } from 'lucide-react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import { APP_NAME } from '../utils/constants';
import { useAuth } from '../context/AuthContext';

export const Layout = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { user, logout } = useAuth();

  return (
    <div className="app-container">
      {/* Left Sidebar */}
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Main Content */}
      <div className="app-main">
        <header className="app-header">
          <div className="header-title-container">
            <button
              className="mobile-menu-btn"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              aria-label="Toggle Navigation"
            >
              <Menu size={20} />
            </button>
            <h1 className="header-title">{APP_NAME}</h1>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span className="header-badge">Financial Intelligence</span>
            {user && (
              <div className="header-user-section">
                <span className="user-email-badge">{user.email}</span>
                <button
                  onClick={logout}
                  className="header-logout-btn"
                  title="Logout"
                  aria-label="Logout"
                >
                  <LogOut size={15} />
                  <span>Logout</span>
                </button>
              </div>
            )}
          </div>
        </header>

        <main className="page-content">{children || <Outlet />}</main>
      </div>
    </div>
  );
};

export default Layout;
