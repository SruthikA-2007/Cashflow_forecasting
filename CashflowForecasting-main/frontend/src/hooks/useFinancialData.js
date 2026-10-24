import { useState, useMemo } from 'react';
import {
  mockKpis,
  mockCashFlowForecast,
  mockInvoices,
  mockCustomers,
  mockDatasets,
  mockRiskDistribution
} from '../services/mockData';

export const useFinancialData = () => {
  const [invoices, setInvoices] = useState(mockInvoices);
  const [customers, setCustomers] = useState(mockCustomers);
  const [datasets, setDatasets] = useState(mockDatasets);
  const [kpis] = useState(mockKpis);
  const [forecast] = useState(mockCashFlowForecast);
  const [riskDistribution] = useState(mockRiskDistribution);

  // Ingestion action simulation for Data Management page
  const addDataset = (newDataset) => {
    setDatasets((prev) => [newDataset, ...prev]);
  };

  return {
    kpis,
    forecast,
    invoices,
    customers,
    datasets,
    riskDistribution,
    addDataset,
  };
};
