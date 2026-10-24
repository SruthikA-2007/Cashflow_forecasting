import React, { useState, useRef } from 'react';
import {
  Database,
  Upload,
  CheckCircle,
  FileSpreadsheet,
  Layers,
  Server,
  FileCheck,
  RotateCw,
  X,
  Trash2,
} from 'lucide-react';
import {
  PageHeader,
  DataTable,
  ErrorMessage,
  EmptyState,
} from '../components';
import { useDataset } from '../context/DatasetContext';
import { formatCurrency, formatDate } from '../utils/formatters';

export const DataManagement = () => {
  const { isDatasetLoaded, dataset, ingestCsvFile, clearDataset } = useDataset();

  // CSV Import States
  const [selectedFile, setSelectedFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState(null);
  const [uploadError, setUploadError] = useState(null);
  const fileInputRef = useRef(null);

  // Handle File Input Change
  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      setUploadSuccess(null);
      setUploadError(null);
    }
  };

  // Trigger Dynamic Upload & Parsing
  const handleUploadSubmit = async () => {
    if (!selectedFile) {
      setUploadError('Please select a CSV file first.');
      return;
    }

    if (!selectedFile.name.toLowerCase().endsWith('.csv')) {
      setUploadError('Invalid file type: Please upload a valid .csv file.');
      return;
    }

    setIsUploading(true);
    setUploadSuccess(null);
    setUploadError(null);

    try {
      const processed = await ingestCsvFile(selectedFile);
      setUploadSuccess(`Successfully parsed and ingested "${selectedFile.name}" with ${processed.invoices.length} invoice records.`);
      setIsUploading(false);
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (err) {
      setUploadError(err.message || 'Failed to parse CSV dataset.');
      setIsUploading(false);
    }
  };

  const clearSelectedFile = () => {
    setSelectedFile(null);
    setUploadError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const sourceInfo = dataset?.dataSourceInfo || {
    currentSource: 'No Dataset Ingested',
    dbStatus: 'Awaiting CSV Upload',
    dbLatency: '—',
    availableRecordsCount: 0,
    lastSyncTimestamp: 'Not synced',
  };

  const preprocessingSummary = dataset?.preprocessingSummary || {
    totalRecords: 0,
    recordsAfterCleaning: 0,
    duplicateRecordsRemoved: 0,
    missingValuesHandled: 0,
    cleaningEfficiency: '0%',
  };

  const previewRows = dataset?.previewRows || [];

  // Define Preview Columns
  const previewColumns = [
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
      header: 'Customer',
      accessor: 'customer',
      render: (row) => (
        <span style={{ fontWeight: 500, color: 'var(--text-primary)' }}>
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
      header: 'Invoice Date',
      accessor: 'invoiceDate',
      render: (row) => (
        <span style={{ color: 'var(--text-secondary)' }}>
          {formatDate(row.invoiceDate)}
        </span>
      ),
    },
    {
      header: 'Due Date',
      accessor: 'dueDate',
      render: (row) => (
        <span style={{ color: 'var(--text-secondary)' }}>
          {formatDate(row.dueDate)}
        </span>
      ),
    },
    {
      header: 'Payment Status',
      accessor: 'paymentStatus',
      render: (row) => {
        let badgeStyle = {
          backgroundColor: 'rgba(16, 185, 129, 0.12)',
          color: 'var(--risk-low)',
          border: '1px solid rgba(16, 185, 129, 0.3)',
        };

        if (row.paymentStatus === 'Pending') {
          badgeStyle = {
            backgroundColor: 'rgba(245, 158, 11, 0.12)',
            color: 'var(--risk-medium)',
            border: '1px solid rgba(245, 158, 11, 0.3)',
          };
        } else if (row.paymentStatus === 'Overdue' || row.paymentStatus === 'Delayed' || row.paymentStatus === 'Critical Delay') {
          badgeStyle = {
            backgroundColor: 'rgba(239, 68, 68, 0.12)',
            color: 'var(--risk-high)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
          };
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
              ...badgeStyle,
            }}
          >
            {row.paymentStatus}
          </span>
        );
      },
    },
  ];

  return (
    <div className="page-content">
      {/* Header */}
      <PageHeader
        title="Data Management"
        subtitle="Upload invoice datasets to compute cash flow forecasts, payment risk levels, and customer profiles"
        badge={isDatasetLoaded ? `Active: ${dataset.fileName}` : 'No Dataset Uploaded'}
        actions={
          isDatasetLoaded && (
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => {
                clearDataset();
                setUploadSuccess(null);
              }}
              style={{ color: 'var(--risk-high)', borderColor: 'var(--border-light)' }}
            >
              <Trash2 size={14} /> Clear Dataset
            </button>
          )
        }
      />

      {/* 1. Data Source Information Section */}
      <div className="card">
        <div className="card-header">
          <div>
            <h3 className="card-title">
              <Server size={18} color="var(--primary)" />
              Data Source Information
            </h3>
            <p className="card-subtitle">
              Current database storage engine and live connectivity status
            </p>
          </div>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            gap: '1.25rem',
          }}
        >
          {/* Current Data Source */}
          <div
            style={{
              padding: '1.15rem',
              backgroundColor: 'var(--bg-surface-subtle)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: 600,
                textTransform: 'uppercase',
                color: 'var(--text-muted)',
                letterSpacing: '0.04em',
              }}
            >
              Current Data Source
            </span>
            <div
              style={{
                fontSize: '0.95rem',
                fontWeight: 600,
                color: 'var(--text-primary)',
                marginTop: '0.35rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
              }}
            >
              <Database size={16} color="var(--primary)" />
              {sourceInfo.currentSource}
            </div>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.25rem', display: 'block' }}>
              Synced: {sourceInfo.lastSyncTimestamp}
            </span>
          </div>

          {/* Database Connection Status */}
          <div
            style={{
              padding: '1.15rem',
              backgroundColor: 'var(--bg-surface-subtle)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: 600,
                textTransform: 'uppercase',
                color: 'var(--text-muted)',
                letterSpacing: '0.04em',
              }}
            >
              Database Connection Status
            </span>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                marginTop: '0.35rem',
              }}
            >
              <span
                style={{
                  width: '10px',
                  height: '10px',
                  borderRadius: '50%',
                  backgroundColor: isDatasetLoaded ? 'var(--risk-low)' : 'var(--risk-medium)',
                  boxShadow: isDatasetLoaded ? '0 0 8px rgba(16, 185, 129, 0.6)' : 'none',
                }}
              />
              <span style={{ fontSize: '1.1rem', fontWeight: 700, color: isDatasetLoaded ? 'var(--risk-low)' : 'var(--text-secondary)' }}>
                {sourceInfo.dbStatus}
              </span>
            </div>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.25rem', display: 'block' }}>
              PostgreSQL Schema Ready
            </span>
          </div>

          {/* Number of Available Invoice Records */}
          <div
            style={{
              padding: '1.15rem',
              backgroundColor: 'var(--bg-surface-subtle)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: 600,
                textTransform: 'uppercase',
                color: 'var(--text-muted)',
                letterSpacing: '0.04em',
              }}
            >
              Available Invoice Records
            </span>
            <div
              style={{
                fontSize: '1.5rem',
                fontWeight: 700,
                color: 'var(--text-primary)',
                marginTop: '0.2rem',
              }}
            >
              {sourceInfo.availableRecordsCount.toLocaleString()}
            </div>
            <span
              style={{
                fontSize: '0.72rem',
                color: isDatasetLoaded ? 'var(--risk-low)' : 'var(--text-muted)',
                display: 'block',
                marginTop: '0.2rem',
              }}
            >
              {isDatasetLoaded ? '✓ Ingested & Calculated' : 'Upload CSV to populate'}
            </span>
          </div>
        </div>
      </div>

      {/* 2. CSV Data Import Section */}
      <div className="card">
        <div className="card-header">
          <div>
            <h3 className="card-title">
              <Upload size={18} color="var(--primary)" />
              CSV Data Import
            </h3>
            <p className="card-subtitle">
              Upload an invoice CSV dataset. Once uploaded, results will populate across all pages.
            </p>
          </div>
        </div>

        {/* Upload Controls Box */}
        <div
          style={{
            padding: '2rem 1.5rem',
            borderRadius: 'var(--radius-lg)',
            backgroundColor: 'var(--bg-surface-subtle)',
            border: '2px dashed var(--border-light)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            textAlign: 'center',
            gap: '1rem',
          }}
        >
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept=".csv"
            style={{ display: 'none' }}
          />

          <div
            style={{
              width: '52px',
              height: '52px',
              borderRadius: '50%',
              backgroundColor: 'var(--bg-surface-elevated)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--primary)',
            }}
          >
            <FileSpreadsheet size={26} />
          </div>

          <div>
            <h4 style={{ fontSize: '1.05rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.25rem' }}>
              Select an invoice CSV file to upload
            </h4>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', maxWidth: '440px' }}>
              Supported format: .CSV with columns such as Invoice ID, Customer, Amount, Invoice Date, Due Date, Status.
            </p>
          </div>

          {/* Selected File Badge */}
          {selectedFile && (
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.45rem 0.9rem',
                borderRadius: '6px',
                backgroundColor: 'var(--bg-surface-elevated)',
                border: '1px solid var(--border-light)',
                fontSize: '0.85rem',
                color: 'var(--text-primary)',
              }}
            >
              <FileCheck size={16} color="var(--primary)" />
              <strong>{selectedFile.name}</strong>
              <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                ({(selectedFile.size / 1024).toFixed(1)} KB)
              </span>
              <button
                type="button"
                onClick={clearSelectedFile}
                disabled={isUploading}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                  padding: '2px',
                  display: 'flex',
                  alignItems: 'center',
                }}
                title="Remove file"
              >
                <X size={14} />
              </button>
            </div>
          )}

          {/* Action Buttons */}
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', justifyContent: 'center' }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
            >
              Browse CSV File
            </button>

            <button
              type="button"
              className="btn btn-primary"
              onClick={handleUploadSubmit}
              disabled={isUploading || !selectedFile}
              style={{ minWidth: '130px' }}
            >
              {isUploading ? (
                <>
                  <RotateCw size={15} className="animate-spin" /> Processing...
                </>
              ) : (
                <>
                  <Upload size={15} /> Upload CSV
                </>
              )}
            </button>
          </div>
        </div>

        {/* Success State */}
        {uploadSuccess && (
          <div
            style={{
              marginTop: '1rem',
              padding: '0.85rem 1.15rem',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'rgba(16, 185, 129, 0.12)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              color: 'var(--risk-low)',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              fontSize: '0.85rem',
            }}
          >
            <CheckCircle size={18} style={{ flexShrink: 0 }} />
            <span>{uploadSuccess}</span>
          </div>
        )}

        {/* Error State */}
        {uploadError && (
          <div style={{ marginTop: '1rem' }}>
            <ErrorMessage
              title="CSV Import Error"
              message={uploadError}
              onRetry={() => fileInputRef.current?.click()}
            />
          </div>
        )}
      </div>

      {/* 3. Small Preprocessing Summary Area */}
      <div className="card">
        <div className="card-header">
          <div>
            <h3 className="card-title">
              <Layers size={18} color="var(--primary)" />
              Preprocessing Summary
            </h3>
            <p className="card-subtitle">
              Automated data sanitation, deduplication, and missing value handling
            </p>
          </div>
          {isDatasetLoaded && (
            <span
              style={{
                fontSize: '0.75rem',
                padding: '0.2rem 0.55rem',
                borderRadius: '9999px',
                backgroundColor: 'rgba(16, 185, 129, 0.12)',
                color: 'var(--risk-low)',
                fontWeight: 600,
              }}
            >
              Efficiency: {preprocessingSummary.cleaningEfficiency}
            </span>
          )}
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '1rem',
          }}
        >
          {/* Total Records */}
          <div
            style={{
              padding: '1rem',
              backgroundColor: 'var(--bg-surface-subtle)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Total Records
            </div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '0.25rem' }}>
              {preprocessingSummary.totalRecords.toLocaleString()}
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
              Raw input volume
            </div>
          </div>

          {/* Records After Cleaning */}
          <div
            style={{
              padding: '1rem',
              backgroundColor: 'var(--bg-surface-subtle)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Records After Cleaning
            </div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, color: isDatasetLoaded ? 'var(--risk-low)' : 'var(--text-primary)', marginTop: '0.25rem' }}>
              {preprocessingSummary.recordsAfterCleaning.toLocaleString()}
            </div>
            <div style={{ fontSize: '0.72rem', color: isDatasetLoaded ? 'var(--risk-low)' : 'var(--text-muted)', marginTop: '0.2rem' }}>
              {isDatasetLoaded ? 'Cleaned dataset ready for ML' : 'No records processed'}
            </div>
          </div>

          {/* Duplicate Records Removed */}
          <div
            style={{
              padding: '1rem',
              backgroundColor: 'var(--bg-surface-subtle)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Duplicate Records Removed
            </div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '0.25rem' }}>
              {preprocessingSummary.duplicateRecordsRemoved}
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
              Identical invoice hashes filtered
            </div>
          </div>

          {/* Missing Values Handled */}
          <div
            style={{
              padding: '1rem',
              backgroundColor: 'var(--bg-surface-subtle)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Missing Values Handled
            </div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, color: isDatasetLoaded ? 'var(--primary)' : 'var(--text-primary)', marginTop: '0.25rem' }}>
              {preprocessingSummary.missingValuesHandled}
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
              Imputed or standardized
            </div>
          </div>
        </div>
      </div>

      {/* 4. Dataset Preview Table Section */}
      <div className="card">
        <div className="card-header">
          <div>
            <h3 className="card-title">
              <FileSpreadsheet size={18} color="var(--primary)" />
              Dataset Preview
            </h3>
            <p className="card-subtitle">
              Sample invoice entries demonstrating schema layout and normalized fields
            </p>
          </div>
          {isDatasetLoaded && (
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Showing sample <strong>{previewRows.length}</strong> records
            </span>
          )}
        </div>

        {!isDatasetLoaded ? (
          <EmptyState
            title="No dataset preview available"
            description="Select and upload an invoice CSV file above to preview normalized dataset records."
          />
        ) : (
          <DataTable
            columns={previewColumns}
            data={previewRows}
            pagination={false}
            emptyTitle="No preview records"
            emptyMessage="Upload a CSV dataset to see structured row samples."
          />
        )}
      </div>
    </div>
  );
};

export default DataManagement;
