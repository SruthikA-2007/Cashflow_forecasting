import React, { useState, useRef } from 'react';
import { UploadCloud, FileSpreadsheet, Sparkles, CheckCircle, AlertCircle } from 'lucide-react';

/**
 * Reusable FileUploadArea component for financial dataset ingestion
 * @param {Function} onFileSelect - Callback when file is selected or dropped: (file: File) => void
 * @param {Function} onSampleSelect - Optional callback for loading sample financial data
 * @param {string} accept - Accepted extensions (e.g. ".csv,.xlsx,.json")
 * @param {string} title - Primary prompt title
 * @param {string} subtitle - Subtext with accepted formats and size limits
 * @param {boolean} isUploading - Whether an upload or parsing is currently in progress
 * @param {boolean} disabled - Disable interactions
 */
export const FileUploadArea = ({
  onFileSelect,
  onSampleSelect,
  accept = '.csv,.xlsx,.json',
  title = 'Click to upload or drag and drop financial dataset',
  subtitle = 'Supported formats: CSV, XLSX, JSON (Max 50MB). Automated schema validation will run upon upload.',
  isUploading = false,
  disabled = false,
  className = '',
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);

  const handleDragOver = (e) => {
    e.preventDefault();
    if (disabled || isUploading) return;
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (disabled || isUploading) return;
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      if (onFileSelect) {
        onFileSelect(e.dataTransfer.files[0]);
      }
    }
  };

  const handleInputChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      if (onFileSelect) {
        onFileSelect(e.target.files[0]);
      }
    }
  };

  const handleClick = () => {
    if (disabled || isUploading) return;
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  return (
    <div
      className={`upload-dropzone ${isDragging ? 'dragging' : ''} ${className}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={handleClick}
      style={{
        cursor: disabled || isUploading ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.6 : 1,
      }}
    >
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleInputChange}
        accept={accept}
        style={{ display: 'none' }}
        disabled={disabled || isUploading}
      />

      <div className="upload-icon-wrapper">
        <UploadCloud size={28} />
      </div>

      <h4 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: '0.35rem', color: 'var(--text-primary)' }}>
        {isUploading ? 'Validating schema and processing rows...' : title}
      </h4>

      {subtitle && (
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', maxWidth: '440px', lineHeight: 1.4 }}>
          {subtitle}
        </p>
      )}

      {onSampleSelect && (
        <div style={{ marginTop: '1.25rem' }}>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={disabled || isUploading}
            onClick={(e) => {
              e.stopPropagation();
              onSampleSelect();
            }}
          >
            <Sparkles size={14} /> Ingest Sample Dataset
          </button>
        </div>
      )}
    </div>
  );
};

export default FileUploadArea;
