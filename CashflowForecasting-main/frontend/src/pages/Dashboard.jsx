import React from 'react';
import {
  FileSpreadsheet,
  AlertTriangle,
  ShieldCheck,
  TrendingDown,
  ArrowRight,
  DollarSign,
  UploadCloud,
  Sparkles,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  PageHeader,
  SummaryCard,
  RiskBadge,
  DataTable,
  EmptyState,
} from '../components';
import { useDataset } from '../context/DatasetContext';
import {
  formatCurrency,
  formatCompactCurrency,
  formatDelayDays,
} from '../utils/formatters';

export const Dashboard = () => {
  const { isDatasetLoaded, dataset } = useDataset();

  const summary = dataset?.summaryCards;
  const riskDist = dataset?.riskDistribution;
  const topInvoices = dataset?.topHighRiskInvoices || [];

  // Define columns for Top High-Risk Invoices Table
  const tableColumns = [
    {
      header: 'Invoice ID',
      accessor: 'id',
      render: (row) => (
        <span className="mono-cell" style={{ fontWeight: 600 }}>
          {row.id}
        </span>
      ),
    },
    {
      header: 'Customer Name',
      accessor: 'customerName',
      render: (row) => (
        <div>
          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
            {row.customerName}
          </span>
          {row.customerId && (
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'block' }}>
              {row.customerId}
            </span>
          )}
        </div>
      ),
    },
    {
      header: 'Invoice Amount',
      accessor: 'invoiceAmount',
      render: (row) => (
        <span style={{ fontWeight: 600 }}>
          {formatCurrency(row.invoiceAmount)}
        </span>
      ),
    },
    {
      header: 'Risk Level',
      accessor: 'riskLevel',
      render: (row) => <RiskBadge level={row.riskLevel} score={row.riskScore} />,
    },
    {
      header: 'Expected Delay Days',
      accessor: 'expectedDelayDays',
      render: (row) => (
        <span style={{ color: 'var(--risk-high)', fontWeight: 600 }}>
          {formatDelayDays(row.expectedDelayDays)}
        </span>
      ),
    },
    {
      header: 'Estimated Cash Flow Impact',
      accessor: 'cashFlowImpact',
      render: (row) => (
        <span
          style={{
            color: row.cashFlowImpact < 0 ? 'var(--risk-high)' : 'var(--text-primary)',
            fontWeight: 700,
            fontFamily: 'var(--font-mono)',
          }}
        >
          {formatCurrency(row.cashFlowImpact)}
        </span>
      ),
    },
  ];

  return (
    <div className="page-content">
      {/* Page Header */}
      <PageHeader
        title="Cash Flow Early Warning Dashboard"
        subtitle="Real-time payment risk detection, monthly liquidity tracking, and working capital optimization"
        actions={
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <Link to="/invoice-risk" className="btn btn-primary btn-sm">
              <Sparkles size={14} /> Predict Invoice Payment
            </Link>
            <Link to="/data-management" className="btn btn-secondary btn-sm">
              <UploadCloud size={14} /> {isDatasetLoaded ? 'Manage Dataset' : 'Upload Dataset'}
            </Link>
          </div>
        }
      />

      {/* 1. Four Summary Cards at the Top */}
      <div className="stats-grid">
        <SummaryCard
          title="Total Invoices Analysed"
          value={isDatasetLoaded ? summary?.totalInvoicesAnalysed?.value?.toLocaleString() : '0'}
          change={isDatasetLoaded ? summary?.totalInvoicesAnalysed?.change : undefined}
          changeText={isDatasetLoaded ? summary?.totalInvoicesAnalysed?.changeText : 'Awaiting CSV dataset upload'}
          helperText={isDatasetLoaded ? summary?.totalInvoicesAnalysed?.helperText : 'No data ingested yet'}
          icon={FileSpreadsheet}
        />

        <SummaryCard
          title="High-Risk Invoices"
          value={isDatasetLoaded ? summary?.highRiskInvoices?.value?.toLocaleString() : '0'}
          change={isDatasetLoaded ? summary?.highRiskInvoices?.change : undefined}
          changeText={isDatasetLoaded ? summary?.highRiskInvoices?.changeText : '0% of portfolio'}
          helperText={isDatasetLoaded ? summary?.highRiskInvoices?.helperText : '₹0 capital at risk'}
          icon={AlertTriangle}
          isNegativeGood={true}
        />

        <SummaryCard
          title="Low-Risk Invoices"
          value={isDatasetLoaded ? summary?.lowRiskInvoices?.value?.toLocaleString() : '0'}
          change={isDatasetLoaded ? summary?.lowRiskInvoices?.change : undefined}
          changeText={isDatasetLoaded ? summary?.lowRiskInvoices?.changeText : '0% of portfolio'}
          helperText={isDatasetLoaded ? summary?.lowRiskInvoices?.helperText : '₹0 secure cash'}
          icon={ShieldCheck}
          isNegativeGood={false}
        />

        <SummaryCard
          title="Estimated Cash Flow Deviation"
          value={isDatasetLoaded ? formatCurrency(summary?.estimatedCashFlowDeviation?.amount || 0) : '₹0'}
          change={isDatasetLoaded ? summary?.estimatedCashFlowDeviation?.percentage : undefined}
          changeText={isDatasetLoaded ? summary?.estimatedCashFlowDeviation?.changeText : 'No deviation calculated'}
          helperText={isDatasetLoaded ? summary?.estimatedCashFlowDeviation?.helperText : 'Upload dataset to compute deviation'}
          icon={TrendingDown}
          isNegativeGood={false}
        />
      </div>

      {/* 2. Payment Risk Distribution Section */}
      <div className="card">
        <div className="card-header">
          <div>
            <h3 className="card-title">
              <DollarSign size={18} color="var(--primary)" />
              Payment Risk Distribution
            </h3>
            <p className="card-subtitle">
              Portfolio breakdown across Low, Medium, and High payment risk categories
            </p>
          </div>
          {isDatasetLoaded && riskDist && (
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Total Analysed: <strong>{riskDist.totalInvoices} invoices</strong> ({formatCurrency(riskDist.totalAmount)})
            </span>
          )}
        </div>

        {!isDatasetLoaded ? (
          <EmptyState
            title="No dataset loaded"
            description="Upload an invoice CSV dataset in Data Management to compute the payment risk distribution."
            action={
              <Link to="/data-management" className="btn btn-primary btn-sm">
                <UploadCloud size={14} /> Go to Data Management
              </Link>
            }
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {/* Multi-segment distribution visual bar */}
            <div
              style={{
                display: 'flex',
                height: '10px',
                borderRadius: '9999px',
                overflow: 'hidden',
                backgroundColor: 'var(--bg-surface-elevated)',
                width: '100%',
              }}
            >
              {riskDist?.categories?.map((cat) => (
                <div
                  key={cat.key}
                  style={{
                    width: `${cat.percentage}%`,
                    backgroundColor: cat.color,
                    transition: 'width 0.3s ease',
                  }}
                  title={`${cat.name}: ${cat.count} invoices (${cat.percentage}%)`}
                />
              ))}
            </div>

            {/* Risk Category Summary Grid */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                gap: '1rem',
              }}
            >
              {riskDist?.categories?.map((cat) => (
                <div
                  key={cat.key}
                  style={{
                    padding: '1rem',
                    backgroundColor: 'var(--bg-surface-subtle)',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.45rem',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      color: cat.color,
                    }}
                  >
                    <span
                      style={{
                        width: '8px',
                        height: '8px',
                        borderRadius: '50%',
                        backgroundColor: cat.color,
                      }}
                    />
                    {cat.name}
                  </div>

                  <div
                    style={{
                      fontSize: '1.4rem',
                      fontWeight: 700,
                      marginTop: '0.35rem',
                      color: 'var(--text-primary)',
                    }}
                  >
                    {cat.count} <span style={{ fontSize: '0.85rem', fontWeight: 500, color: 'var(--text-secondary)' }}>Invoices</span>
                  </div>

                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      fontSize: '0.75rem',
                      color: 'var(--text-muted)',
                      marginTop: '0.35rem',
                    }}
                  >
                    <span>{formatCompactCurrency(cat.amount)}</span>
                    <span style={{ fontWeight: 600 }}>{cat.percentage}% of portfolio</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 3. Top High-Risk Invoices Table Section */}
      <div className="card">
        <div className="card-header">
          <div>
            <h3 className="card-title">
              <AlertTriangle size={18} color="var(--risk-high)" />
              Top High-Risk Invoices
            </h3>
            <p className="card-subtitle">
              Invoices requiring immediate attention due to projected settlement delays and negative cash flow impact
            </p>
          </div>
          {isDatasetLoaded && topInvoices.length > 0 && (
            <Link
              to="/invoice-risk"
              style={{
                fontSize: '0.8rem',
                color: 'var(--primary)',
                textDecoration: 'none',
                display: 'flex',
                alignItems: 'center',
                gap: '0.25rem',
                fontWeight: 500,
              }}
            >
              View All Invoices <ArrowRight size={14} />
            </Link>
          )}
        </div>

        {!isDatasetLoaded ? (
          <EmptyState
            title="No high-risk invoices available"
            description="Upload an invoice CSV dataset in Data Management to identify high-risk accounts."
            action={
              <Link to="/data-management" className="btn btn-primary btn-sm">
                <UploadCloud size={14} /> Go to Data Management
              </Link>
            }
          />
        ) : (
          <DataTable
            columns={tableColumns}
            data={topInvoices}
            emptyTitle="No high-risk invoices detected"
            emptyDescription="All accounts currently reflect favorable payment behavior."
          />
        )}
      </div>
    </div>
  );
};

export default Dashboard;
