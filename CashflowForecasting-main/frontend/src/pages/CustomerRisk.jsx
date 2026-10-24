import React, { useState, useEffect } from 'react';
import {
  Users,
  TrendingUp,
  TrendingDown,
  Minus,
  Building,
  UploadCloud,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  PageHeader,
  FilterBar,
  RiskBadge,
  DataTable,
  EmptyState,
} from '../components';
import { useDataset } from '../context/DatasetContext';
import {
  formatCurrency,
  formatPercent,
  formatDate,
} from '../utils/formatters';

export const CustomerRisk = () => {
  const { isDatasetLoaded, dataset } = useDataset();

  const [searchTerm, setSearchTerm] = useState('');
  const [selectedRiskFilter, setSelectedRiskFilter] = useState('ALL');
  const [selectedCustomer, setSelectedCustomer] = useState(null);

  const customers = dataset?.customers || [];

  // Select initial customer on dataset change
  useEffect(() => {
    if (customers.length > 0 && !selectedCustomer) {
      setSelectedCustomer(customers[0]);
    } else if (customers.length === 0) {
      setSelectedCustomer(null);
    }
  }, [customers]);

  const highRiskCount = customers.filter((c) => c.riskLevel === 'High Risk').length;
  const mediumRiskCount = customers.filter((c) => c.riskLevel === 'Medium Risk').length;
  const lowRiskCount = customers.filter((c) => c.riskLevel === 'Low Risk').length;

  const filterOptions = [
    { key: 'ALL', label: 'All Accounts', count: customers.length },
    { key: 'HIGH', label: 'High Risk', count: highRiskCount, color: 'var(--risk-high)' },
    { key: 'MEDIUM', label: 'Medium Risk', count: mediumRiskCount, color: 'var(--risk-medium)', textColor: '#000' },
    { key: 'LOW', label: 'Low Risk', count: lowRiskCount, color: 'var(--risk-low)', textColor: '#000' },
  ];

  const filteredCustomers = customers.filter((customer) => {
    const matchesFilter =
      selectedRiskFilter === 'ALL' || customer.riskLevel.toUpperCase().includes(selectedRiskFilter);
    if (!matchesFilter) return false;

    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    return (
      customer.name.toLowerCase().includes(term) ||
      customer.sector?.toLowerCase().includes(term) ||
      customer.id.toLowerCase().includes(term)
    );
  });

  const columns = [
    {
      header: 'Customer ID',
      accessor: 'id',
      render: (row) => <span className="mono-cell" style={{ fontWeight: 600 }}>{row.id}</span>,
    },
    {
      header: 'Customer Name',
      accessor: 'name',
      render: (row) => (
        <div>
          <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{row.name}</div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{row.sector}</div>
        </div>
      ),
    },
    {
      header: 'Total Exposure',
      accessor: 'totalOutstanding',
      render: (row) => (
        <span style={{ fontWeight: 600 }}>{formatCurrency(row.totalOutstanding)}</span>
      ),
    },
    {
      header: 'Active Invoices',
      accessor: 'activeInvoicesCount',
      align: 'center',
      render: (row) => (
        <span className="mono-cell">{row.activeInvoicesCount}</span>
      ),
    },
    {
      header: 'Hist. DSO',
      accessor: 'historicalDSO',
      render: (row) => (
        <span style={{ color: 'var(--text-secondary)' }}>{row.historicalDSO} days</span>
      ),
    },
    {
      header: 'On-Time Rate',
      accessor: 'onTimePaymentRate',
      render: (row) => {
        const isGood = row.onTimePaymentRate >= 80;
        return (
          <span
            style={{
              fontWeight: 600,
              color: isGood ? 'var(--risk-low)' : 'var(--risk-high)',
            }}
          >
            {formatPercent(row.onTimePaymentRate, 1)}
          </span>
        );
      },
    },
    {
      header: 'Credit Trend',
      accessor: 'trend',
      render: (row) => {
        if (row.trend === 'improving') {
          return (
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.2rem', color: 'var(--risk-low)', fontSize: '0.8rem' }}>
              <TrendingUp size={14} /> Improving
            </span>
          );
        }
        if (row.trend === 'deteriorating') {
          return (
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.2rem', color: 'var(--risk-high)', fontSize: '0.8rem' }}>
              <TrendingDown size={14} /> Deteriorating
            </span>
          );
        }
        return (
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.2rem', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
            <Minus size={14} /> Stable
          </span>
        );
      },
    },
    {
      header: 'Risk Tier',
      accessor: 'riskLevel',
      render: (row) => <RiskBadge level={row.riskLevel} score={row.riskScore} />,
    },
  ];

  return (
    <div className="page-content">
      {/* Page Header */}
      <PageHeader
        title="Customer Credit & Default Risk"
        subtitle="Portfolio credit risk profiling and behavioral payment consistency scoring"
        actions={
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <Link to="/data-management" className="btn btn-primary btn-sm">
              <UploadCloud size={14} /> {isDatasetLoaded ? 'Update Dataset' : 'Upload Dataset'}
            </Link>
          </div>
        }
      />

      {/* Main Customers Table Card */}
      <div className="card">
        <div className="card-header">
          <div>
            <h3 className="card-title">
              <Users size={18} color="var(--primary)" />
              Customer Accounts Exposure
            </h3>
            <p className="card-subtitle">
              Click on an account to inspect credit line utilization and payment history
            </p>
          </div>
          {isDatasetLoaded && (
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Showing <strong>{filteredCustomers.length}</strong> of <strong>{customers.length}</strong> accounts
            </span>
          )}
        </div>

        {!isDatasetLoaded ? (
          <EmptyState
            title="No customer profiles available"
            description="Upload an invoice CSV dataset in Data Management to generate customer portfolio risk profiles."
            action={
              <Link to="/data-management" className="btn btn-primary btn-sm">
                <UploadCloud size={14} /> Go to Data Management
              </Link>
            }
          />
        ) : (
          <>
            {/* FilterBar Component */}
            <FilterBar
              searchValue={searchTerm}
              onSearchChange={setSearchTerm}
              searchPlaceholder="Search customer by name, ID or sector..."
              filterOptions={filterOptions}
              activeFilter={selectedRiskFilter}
              onFilterChange={setSelectedRiskFilter}
              summaryText={`Showing ${filteredCustomers.length} of ${customers.length} accounts`}
            />

            {/* Reusable DataTable Component */}
            <DataTable
              columns={columns}
              data={filteredCustomers}
              emptyTitle="No customer accounts match filter"
              emptyMessage="Try adjusting your search criteria or risk filter."
              renderActions={(row) => (
                <button
                  type="button"
                  className={`btn btn-sm ${selectedCustomer?.id === row.id ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setSelectedCustomer(row)}
                >
                  {selectedCustomer?.id === row.id ? 'Inspecting' : 'Inspect'}
                </button>
              )}
            />
          </>
        )}
      </div>

      {/* Selected Customer Drilldown */}
      {isDatasetLoaded && selectedCustomer && (
        <div className="card">
          <div className="card-header">
            <div>
              <h3 className="card-title">
                <Building size={18} color="var(--primary)" />
                Account Profile: {selectedCustomer.name}
              </h3>
              <p className="card-subtitle">
                Sector: {selectedCustomer.sector} • Last Payment: {formatDate(selectedCustomer.lastPaymentDate)}
              </p>
            </div>
            <RiskBadge level={selectedCustomer.riskLevel} score={selectedCustomer.riskScore} />
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: '1rem',
              marginTop: '0.75rem',
            }}
          >
            {/* Credit Limit & Utilization */}
            <div
              style={{
                padding: '1rem',
                backgroundColor: 'var(--bg-surface-subtle)',
                borderRadius: '8px',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                <span>Credit Line</span>
                <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{formatCurrency(selectedCustomer.creditLimit)}</span>
              </div>
              <div style={{ marginTop: '0.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginBottom: '0.3rem' }}>
                  <span>Utilization</span>
                  <span style={{ fontWeight: 600 }}>{selectedCustomer.utilizationRate}%</span>
                </div>
                <div className="progress-bar-container">
                  <div
                    className="progress-bar-fill"
                    style={{
                      width: `${selectedCustomer.utilizationRate}%`,
                      backgroundColor: selectedCustomer.utilizationRate > 75 ? 'var(--risk-high)' : 'var(--primary)',
                    }}
                  />
                </div>
              </div>
            </div>

            {/* Historical DSO */}
            <div
              style={{
                padding: '1rem',
                backgroundColor: 'var(--bg-surface-subtle)',
                borderRadius: '8px',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
                Historical DSO
              </div>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, marginTop: '0.25rem' }}>
                {selectedCustomer.historicalDSO} Days
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                Average days to settle
              </div>
            </div>

            {/* Default Probability Indicator */}
            <div
              style={{
                padding: '1rem',
                backgroundColor: 'var(--bg-surface-subtle)',
                borderRadius: '8px',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
                On-Time Settlement Rate
              </div>
              <div
                style={{
                  fontSize: '1.25rem',
                  fontWeight: 700,
                  marginTop: '0.25rem',
                  color: selectedCustomer.onTimePaymentRate >= 80 ? 'var(--risk-low)' : 'var(--risk-high)',
                }}
              >
                {selectedCustomer.onTimePaymentRate}%
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                Payment reliability score
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CustomerRisk;
