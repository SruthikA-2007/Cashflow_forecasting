import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import DataManagement from './pages/DataManagement';
import InvoiceRisk from './pages/InvoiceRisk';
import CustomerRisk from './pages/CustomerRisk';
import Login from './pages/Login';
import ProtectedRoute from './components/ProtectedRoute';
import { DatasetProvider } from './context/DatasetContext';
import { AuthProvider } from './context/AuthContext';

export const App = () => {
  return (
    <AuthProvider>
      <DatasetProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              element={
                <ProtectedRoute>
                  <Layout />
                </ProtectedRoute>
              }
            >
              <Route path="/" element={<Dashboard />} />
              <Route path="/data-management" element={<DataManagement />} />
              <Route path="/invoice-risk" element={<InvoiceRisk />} />
              <Route path="/customer-risk" element={<CustomerRisk />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </DatasetProvider>
    </AuthProvider>
  );
};

export default App;
