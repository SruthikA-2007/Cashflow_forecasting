import React, { useState, useMemo } from 'react';
import {
  FileSpreadsheet,
  Search,
  X,
  AlertTriangle,
  TrendingDown,
  DollarSign,
  Info,
  Clock,
  ShieldCheck,
  CheckCircle,
  HelpCircle,
  ArrowUpRight,
  ArrowDownRight,
  UploadCloud,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  PageHeader,
  RiskBadge,
  DataTable,
  EmptyState,
  PredictInvoiceSection,
} from '../components';
import { useDataset } from '../context/DatasetContext';
import {
  formatCurrency,
  formatDate,
  formatDelayDays,
  formatPercent,
} from '../utils/formatters';

export const InvoiceRisk = () => {
  const { isDatasetLoaded, dataset } = useDataset();

  // Simple Filters
  const [searchInvoiceId, setSearchInvoiceId] = useState('');
  const [selectedCustomer, setSelectedCustomer] = useState('ALL');
  const [selectedRiskLevel, setSelectedRiskLevel] = useState('ALL');

  // Details Modal State
  const [activeInvoiceDetails, setActiveInvoiceDetails] = useState(null);

  const invoices = dataset?.invoices || [];

  // Distinct list of customers for the filter dropdown
  const customerList = useMemo(() => {
    const names = Array.from(new Set(invoices.map((i) => i.customer))).filter(Boolean);
    names.sort();
    return names;
  }, [invoices]);

  // Filtered invoices logic
  const filteredInvoices = useMemo(() => {
    return invoices.filter((inv) => {
      // 1. Search by Invoice ID
      if (searchInvoiceId.trim()) {
        const term = searchInvoiceId.trim().toLowerCase();
        if (!inv.id.toLowerCase().includes(term)) {
          return false;
        }
      }

      // 2. Filter by Customer
      if (selectedCustomer !== 'ALL') {
        if (inv.customer.toLowerCase() !== selectedCustomer.toLowerCase()) {
          return false;
        }
      }

      // 3. Filter by Risk Level
      if (selectedRiskLevel !== 'ALL') {
        const invRisk = (inv.riskLevel || '').toUpperCase();
        if (!invRisk.includes(selectedRiskLevel.toUpperCase())) {
          return false;
        }
      }

      return true;
    });
  }, [invoices, searchInvoiceId, selectedCustomer, selectedRiskLevel]);

  // Helper renderer for Factor Strength indicator
  const renderStrengthMeter = (strength) => {
    const normalized = (strength || 'Moderate').toLowerCase();
    const count = normalized === 'high' ? 3 : normalized === 'moderate' || normalized === 'medium' ? 2 : 1;

    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
        <div style={{ display: 'flex', gap: '2px' }}>
          {[1, 2, 3].map((bar) => (
            <span
              key={bar}
              style={{
                width: '6px',
                height: '12px',
                borderRadius: '1px',
                backgroundColor:
                  bar <= count
                    ? normalized === 'high'
                      ? 'var(--risk-high)'
                      : normalized.includes('mod') || normalized.includes('med')
                      ? 'var(--risk-medium)'
                      : 'var(--primary)'
                    : 'var(--border-light)',
              }}
            />
          ))}
        </div>
        <span
          style={{
            fontSize: '0.75rem',
            fontWeight: 600,
            color:
              normalized === 'high'
                ? 'var(--risk-high)'
                : normalized.includes('mod') || normalized.includes('med')
                ? 'var(--risk-medium)'
                : 'var(--text-secondary)',
          }}
        >
          {strength}
        </span>
      </div>
    );
  };

  // Table Column Definitions
  const columns = [
    {
      header: 'Invoice ID',
      accessor: 'id',
      render: (row) => (
        <span className="mono-cell" style={{ fontWeight: 600, color: 'var(--primary)' }}>
          {row.id}
        </span>
      ),
    },
    {
      header: 'Customer Name',
      accessor: 'customer',
      render: (row) => (
        <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
          {row.customer}
        </span>
      ),
    },
    {
      header: 'Invoice Amount',
      accessor: 'amount',
      render: (row) => (
        <span style={{ fontWeight: 600 }}>{formatCurrency(row.amount)}</span>
      ),
    },
    {
      header: 'Predicted Payment Status',
      accessor: 'predictedPaymentStatus',
      render: (row) => {
        const status = row.predictedPaymentStatus || (row.predictedDelayDays > 5 ? 'Delayed' : 'On Time');
        const isLate = row.predictedDelayDays > 5;
        const isModerate = row.predictedDelayDays > 0 && row.predictedDelayDays <= 5;

        let badgeBg = 'rgba(16, 185, 129, 0.12)';
        let badgeColor = 'var(--risk-low)';
        let badgeBorder = '1px solid rgba(16, 185, 129, 0.3)';

        if (isLate) {
          badgeBg = 'rgba(239, 68, 68, 0.12)';
          badgeColor = 'var(--risk-high)';
          badgeBorder = '1px solid rgba(239, 68, 68, 0.3)';
        } else if (isModerate) {
          badgeBg = 'rgba(245, 158, 11, 0.12)';
          badgeColor = 'var(--risk-medium)';
          badgeBorder = '1px solid rgba(245, 158, 11, 0.3)';
        }

        return (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              padding: '0.2rem 0.6rem',
              borderRadius: '9999px',
              fontSize: '0.75rem',
              fontWeight: 600,
              backgroundColor: badgeBg,
              color: badgeColor,
              border: badgeBorder,
            }}
          >
            {status}
          </span>
        );
      },
    },
    {
      header: 'Late Payment Probability',
      accessor: 'lateProbability',
      render: (row) => {
        const probPct = Math.round((row.lateProbability || 0) * 100);
        const isHigh = probPct >= 70;
        const isMedium = probPct >= 40 && probPct < 70;

        return (
          <span
            className="mono-cell"
            style={{
              fontWeight: 600,
              color: isHigh ? 'var(--risk-high)' : isMedium ? 'var(--risk-medium)' : 'var(--risk-low)',
            }}
          >
            {probPct}%
            {row.isHeuristicScore && (
              <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginLeft: '3px' }} title="Heuristic estimate — not the trained ML model">~est</span>
            )}
          </span>
        );
      },
    },
    {
      header: 'Risk Level',
      accessor: 'riskLevel',
      render: (row) => <RiskBadge level={row.riskLevel} score={row.riskScore} />,
    },
    {
      header: 'Expected Delay Days',
      accessor: 'predictedDelayDays',
      render: (row) => {
        const isLate = row.predictedDelayDays > 0;
        return (
          <span
            style={{
              fontWeight: 600,
              color: isLate ? 'var(--risk-high)' : 'var(--risk-low)',
            }}
          >
            {formatDelayDays(row.predictedDelayDays)}
          </span>
        );
      },
    },
  ];

  return (
    <div className="page-content">
      {/* Page Header */}
      <PageHeader
        title="Invoice Payment Risk"
        subtitle="Machine learning predictions for payment delay probabilities and financial liquidity risks"
        actions={
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <Link to="/data-management" className="btn btn-primary btn-sm">
              <UploadCloud size={14} /> {isDatasetLoaded ? 'Update Dataset' : 'Upload Dataset'}
            </Link>
          </div>
        }
      />

      {/* New Invoice Prediction Input Section */}
      <PredictInvoiceSection />

      {/* Main Invoices Risk Card */}
      <div className="card">
        <div className="card-header">
          <div>
            <h3 className="card-title">
              <FileSpreadsheet size={18} color="var(--primary)" />
              Invoices Risk Ledger
            </h3>

            <p className="card-subtitle">
              Click any invoice to view detailed prediction metrics, financial impact, and AI explanations
            </p>
          </div>
          {isDatasetLoaded && (
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Showing <strong>{filteredInvoices.length}</strong> of <strong>{invoices.length}</strong> invoices
            </span>
          )}
        </div>

        {/* Heuristic Score Notice Banner */}
        {isDatasetLoaded && (
          <div
            style={{
              margin: '0 1.5rem 0',
              padding: '0.65rem 1rem',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'rgba(245, 158, 11, 0.08)',
              border: '1px solid rgba(245, 158, 11, 0.3)',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '0.6rem',
              fontSize: '0.78rem',
              color: 'var(--text-secondary)',
              lineHeight: 1.5,
            }}
          >
            <Info size={15} style={{ color: '#f59e0b', flexShrink: 0, marginTop: '1px' }} />
            <span>
              <strong style={{ color: '#f59e0b' }}>Heuristic Estimates:</strong> Risk scores in this ledger are
              calculated client-side from the CSV data (payment status, amount, customer name) — they are{' '}
              <strong>not</strong> from the trained ML model. For accurate ML-based predictions, use the{' '}
              <strong>"Predict Invoice Payment Risk"</strong> form above and enter the invoice details.
              The ML model uses the company's historical payment behaviour from the training dataset.
            </span>
          </div>
        )}

          <EmptyState
            title="No invoice records available"
            description="Upload an invoice CSV dataset in Data Management to compute and inspect payment risk predictions."
            action={
              <Link to="/data-management" className="btn btn-primary btn-sm">
                <UploadCloud size={14} /> Go to Data Management
              </Link>
            }
          />
        ) : (
          <>
            {/* 3 Simple Filters Only */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.85rem',
                flexWrap: 'wrap',
                marginBottom: '1.25rem',
                padding: '0.85rem 1rem',
                backgroundColor: 'var(--bg-surface-subtle)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              {/* 1. Search by Invoice ID */}
              <div className="search-input-wrapper" style={{ minWidth: '220px', maxWidth: '300px' }}>
                <Search className="search-icon" />
                <input
                  type="text"
                  className="search-input"
                  placeholder="Search by Invoice ID..."
                  value={searchInvoiceId}
                  onChange={(e) => setSearchInvoiceId(e.target.value)}
                />
              </div>

              {/* 2. Filter by Customer */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Customer:</label>
                <select
                  className="filter-select"
                  value={selectedCustomer}
                  onChange={(e) => setSelectedCustomer(e.target.value)}
                  style={{ minWidth: '180px' }}
                >
                  <option value="ALL">All Customers</option>
                  {customerList.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
              </div>

              {/* 3. Filter by Risk Level */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Risk Level:</label>
                <select
                  className="filter-select"
                  value={selectedRiskLevel}
                  onChange={(e) => setSelectedRiskLevel(e.target.value)}
                  style={{ minWidth: '140px' }}
                >
                  <option value="ALL">All Risk Levels</option>
                  <option value="HIGH">High Risk</option>
                  <option value="MEDIUM">Medium Risk</option>
                  <option value="LOW">Low Risk</option>
                </select>
              </div>

              {/* Reset Filters button if any active */}
              {(searchInvoiceId || selectedCustomer !== 'ALL' || selectedRiskLevel !== 'ALL') && (
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => {
                    setSearchInvoiceId('');
                    setSelectedCustomer('ALL');
                    setSelectedRiskLevel('ALL');
                  }}
                  style={{ marginLeft: 'auto', fontSize: '0.78rem' }}
                >
                  Reset Filters
                </button>
              )}
            </div>

            {/* Clean Invoices Table */}
            <DataTable
              columns={columns}
              data={filteredInvoices}
              emptyTitle="No matching invoices found"
              emptyMessage="No invoices match the specified Invoice ID, Customer, or Risk Level filter."
              onRowClick={(row) => setActiveInvoiceDetails(row)}
              renderActions={(row) => (
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    setActiveInvoiceDetails(row);
                  }}
                >
                  View Details
                </button>
              )}
            />
          </>
        )}
      </div>

      {/* Invoice Details Modal / Panel */}
      {activeInvoiceDetails && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(5px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
            padding: '1.25rem',
          }}
          onClick={() => setActiveInvoiceDetails(null)}
        >
          <div
            className="card"
            style={{
              maxWidth: '740px',
              width: '100%',
              maxHeight: '90vh',
              overflowY: 'auto',
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-light)',
              boxShadow: 'var(--shadow-lg)',
              animation: 'fadeIn 0.15s ease-out',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                paddingBottom: '1rem',
                borderBottom: '1px solid var(--border-subtle)',
                marginBottom: '1.25rem',
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                  <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                    {activeInvoiceDetails.id}
                  </h3>
                  <RiskBadge
                    level={activeInvoiceDetails.riskLevel}
                    score={activeInvoiceDetails.riskScore}
                  />
                </div>
                <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                  Debtor: <strong>{activeInvoiceDetails.customer}</strong>
                </p>
              </div>

              <button
                type="button"
                onClick={() => setActiveInvoiceDetails(null)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                  padding: '0.4rem',
                  borderRadius: 'var(--radius-sm)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
                aria-label="Close modal"
              >
                <X size={20} />
              </button>
            </div>

            {/* Modal Content Sections */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.4rem' }}>
              {/* 1. Invoice Information */}
              <div>
                <h4
                  style={{
                    fontSize: '0.8rem',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    color: 'var(--primary)',
                    marginBottom: '0.6rem',
                  }}
                >
                  Invoice Information
                </h4>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                    gap: '0.75rem',
                    padding: '1rem',
                    backgroundColor: 'var(--bg-surface-subtle)',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  <div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Invoice ID</div>
                    <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.15rem' }} className="mono-cell">
                      {activeInvoiceDetails.id}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Customer Name</div>
                    <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.15rem' }}>
                      {activeInvoiceDetails.customer}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Invoice Amount</div>
                    <div style={{ fontWeight: 700, color: 'var(--text-primary)', marginTop: '0.15rem' }}>
                      {formatCurrency(activeInvoiceDetails.amount)}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Invoice Date</div>
                    <div style={{ color: 'var(--text-secondary)', marginTop: '0.15rem' }}>
                      {formatDate(activeInvoiceDetails.invoiceDate || '2026-08-01')}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Due Date</div>
                    <div style={{ color: 'var(--text-secondary)', marginTop: '0.15rem' }}>
                      {formatDate(activeInvoiceDetails.dueDate)}
                    </div>
                  </div>
                </div>
              </div>

              {/* 2. Prediction Information */}
              <div>
                <h4
                  style={{
                    fontSize: '0.8rem',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    color: 'var(--primary)',
                    marginBottom: '0.6rem',
                  }}
                >
                  Prediction Information
                </h4>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(135px, 1fr))',
                    gap: '0.75rem',
                    padding: '1rem',
                    backgroundColor: 'var(--bg-surface-subtle)',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  <div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Predicted Status</div>
                    <div style={{ fontWeight: 600, marginTop: '0.15rem', color: activeInvoiceDetails.predictedDelayDays > 5 ? 'var(--risk-high)' : 'var(--risk-low)' }}>
                      {activeInvoiceDetails.predictedPaymentStatus || (activeInvoiceDetails.predictedDelayDays > 5 ? 'Delayed' : 'On Time')}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Late Probability</div>
                    <div style={{ fontWeight: 700, marginTop: '0.15rem' }} className="mono-cell">
                      {formatPercent(activeInvoiceDetails.lateProbability * 100, 0)}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Risk Level</div>
                    <div style={{ marginTop: '0.15rem' }}>
                      <RiskBadge level={activeInvoiceDetails.riskLevel} score={activeInvoiceDetails.riskScore} />
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Expected Delay</div>
                    <div style={{ fontWeight: 600, marginTop: '0.15rem', color: activeInvoiceDetails.predictedDelayDays > 0 ? 'var(--risk-high)' : 'var(--risk-low)' }}>
                      {formatDelayDays(activeInvoiceDetails.predictedDelayDays)}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Estimated Payment Date</div>
                    <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.15rem' }}>
                      {formatDate(activeInvoiceDetails.predictedPaymentDate)}
                    </div>
                  </div>
                </div>
              </div>

              {/* 3. Section: "Why was this invoice predicted as risky?" */}
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.6rem' }}>
                  <h4
                    style={{
                      fontSize: '0.82rem',
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em',
                      color: 'var(--primary)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.45rem',
                    }}
                  >
                    <HelpCircle size={15} />
                    Why was this invoice predicted as risky?
                  </h4>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                    AI Explanation Factors
                  </span>
                </div>

                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.6rem',
                  }}
                >
                  {(activeInvoiceDetails.riskFactors || []).map((factor, idx) => {
                    const isRiskIncrease =
                      factor.influenceDirection.toLowerCase().includes('increase') ||
                      factor.influenceDirection.toLowerCase().includes('high');

                    return (
                      <div
                        key={idx}
                        style={{
                          padding: '0.85rem 1rem',
                          backgroundColor: 'var(--bg-surface-subtle)',
                          borderRadius: 'var(--radius-md)',
                          border: '1px solid var(--border-subtle)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          gap: '1rem',
                          flexWrap: 'wrap',
                        }}
                      >
                        {/* Feature Name & Business Context */}
                        <div style={{ flexGrow: 1, minWidth: '220px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <span style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '0.875rem' }}>
                              {factor.featureName}
                            </span>
                          </div>
                          {factor.detail && (
                            <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: '0.2rem', lineHeight: 1.35 }}>
                              {factor.detail}
                            </p>
                          )}
                        </div>

                        {/* Factor Direction & Strength */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexShrink: 0 }}>
                          {/* Influence Direction Pill */}
                          <span
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '0.3rem',
                              padding: '0.25rem 0.6rem',
                              borderRadius: '9999px',
                              fontSize: '0.72rem',
                              fontWeight: 600,
                              backgroundColor: isRiskIncrease ? 'rgba(239, 68, 68, 0.12)' : 'rgba(16, 185, 129, 0.12)',
                              color: isRiskIncrease ? 'var(--risk-high)' : 'var(--risk-low)',
                              border: `1px solid ${isRiskIncrease ? 'rgba(239, 68, 68, 0.3)' : 'rgba(16, 185, 129, 0.3)'}`,
                            }}
                          >
                            {isRiskIncrease ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}
                            {factor.influenceDirection}
                          </span>

                          {/* Influence Strength Meter */}
                          <div style={{ minWidth: '85px' }}>
                            <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '2px' }}>
                              Strength
                            </div>
                            {renderStrengthMeter(factor.influenceStrength)}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* 4. Financial Impact */}
              <div>
                <h4
                  style={{
                    fontSize: '0.8rem',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    color: 'var(--risk-high)',
                    marginBottom: '0.6rem',
                  }}
                >
                  Financial Impact
                </h4>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                    gap: '0.75rem',
                    padding: '1rem',
                    backgroundColor: 'rgba(239, 68, 68, 0.08)',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid rgba(239, 68, 68, 0.25)',
                  }}
                >
                  <div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                      Invoice Amount at Risk
                    </div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--risk-high)', marginTop: '0.2rem' }}>
                      {formatCurrency(activeInvoiceDetails.amountAtRisk ?? activeInvoiceDetails.amount)}
                    </div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                      {activeInvoiceDetails.predictedDelayDays > 5 ? 'High exposure' : 'Protected buffer'}
                    </div>
                  </div>

                  <div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                      Estimated Cash Flow Deviation
                    </div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--risk-high)', marginTop: '0.2rem' }} className="mono-cell">
                      {formatCurrency(activeInvoiceDetails.cashFlowDeviation ?? -activeInvoiceDetails.amount)}
                    </div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                      {activeInvoiceDetails.predictedDelayDays > 0 ? `${activeInvoiceDetails.predictedDelayDays} days collection lag` : 'Zero delay impact'}
                    </div>
                  </div>
                </div>
              </div>

              {/* Recommended Action Prompt */}
              {activeInvoiceDetails.recommendedAction && (
                <div
                  style={{
                    padding: '0.85rem 1rem',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'var(--bg-surface-subtle)',
                    borderLeft: '3px solid var(--primary)',
                    fontSize: '0.82rem',
                    color: 'var(--text-secondary)',
                  }}
                >
                  <strong style={{ color: 'var(--text-primary)' }}>Prescriptive Recommendation:</strong>{' '}
                  {activeInvoiceDetails.recommendedAction}
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'flex-end',
                marginTop: '1.5rem',
                paddingTop: '1rem',
                borderTop: '1px solid var(--border-subtle)',
              }}
            >
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setActiveInvoiceDetails(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default InvoiceRisk;
