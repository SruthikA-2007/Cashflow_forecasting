/**
 * Data Management Service - AI Cash Flow Early Warning System
 * Decoupled data provider for data sources, preprocessing summaries, and dataset preview rows.
 * Ready for FastAPI backend API integration (e.g., POST /api/datasets/upload, GET /api/datasets/preview).
 */

export const mockDataSourceInfo = {
  currentSource: 'Supabase PostgreSQL (receivables_ledger_master)',
  dbStatus: 'Connected',
  dbLatency: '24ms',
  availableRecordsCount: 14250,
  lastSyncTimestamp: '2026-08-23 21:45 UTC',
};

export const mockPreprocessingSummary = {
  totalRecords: 14250,
  recordsAfterCleaning: 14180,
  duplicateRecordsRemoved: 45,
  missingValuesHandled: 25,
  cleaningEfficiency: '99.5%',
};

export const mockDatasetPreview = [
  {
    id: 'INV-2026-1001',
    customer: 'Apex Logistics Inc.',
    amount: 48500,
    invoiceDate: '2026-07-28',
    dueDate: '2026-08-28',
    paymentStatus: 'Pending',
  },
  {
    id: 'INV-2026-1002',
    customer: 'Vanguard Industrial Parts',
    amount: 34200,
    invoiceDate: '2026-07-26',
    dueDate: '2026-08-26',
    paymentStatus: 'Pending',
  },
  {
    id: 'INV-2026-1003',
    customer: 'Starlight Media Corp',
    amount: 29800,
    invoiceDate: '2026-08-01',
    dueDate: '2026-09-01',
    paymentStatus: 'Pending',
  },
  {
    id: 'INV-2026-1004',
    customer: 'Cascade Retail Group',
    amount: 19400,
    invoiceDate: '2026-07-30',
    dueDate: '2026-08-30',
    paymentStatus: 'Settled',
  },
  {
    id: 'INV-2026-1005',
    customer: 'Helios Energy Systems',
    amount: 82000,
    invoiceDate: '2026-08-05',
    dueDate: '2026-09-05',
    paymentStatus: 'Settled',
  },
  {
    id: 'INV-2026-1006',
    customer: 'Nexus BioHealth',
    amount: 63500,
    invoiceDate: '2026-08-10',
    dueDate: '2026-09-10',
    paymentStatus: 'Pending',
  },
  {
    id: 'INV-2026-1007',
    customer: 'Quantum Softworks',
    amount: 15200,
    invoiceDate: '2026-07-25',
    dueDate: '2026-08-25',
    paymentStatus: 'Overdue',
  },
  {
    id: 'INV-2026-1008',
    customer: 'Summit Infrastructure',
    amount: 54000,
    invoiceDate: '2026-08-12',
    dueDate: '2026-09-12',
    paymentStatus: 'Pending',
  },
];

/**
 * Fetch current data source and ingestion state
 */
export const fetchDataSourceInfo = async () => {
  return Promise.resolve(mockDataSourceInfo);
};

/**
 * Fetch dataset preview rows and preprocessing statistics
 */
export const fetchDatasetPreviewData = async () => {
  return Promise.resolve({
    summary: mockPreprocessingSummary,
    preview: mockDatasetPreview,
  });
};

/**
 * Simulate uploading a CSV file to the backend
 * @param {File} file - The selected CSV file
 */
export const uploadInvoiceCsv = async (file) => {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (!file.name.toLowerCase().endsWith('.csv')) {
        reject(new Error('Invalid format: Only CSV (.csv) files are supported for import.'));
        return;
      }
      resolve({
        success: true,
        fileName: file.name,
        uploadedRecords: 1250,
        message: `Successfully processed and ingested "${file.name}" into invoice database.`,
      });
    }, 1200);
  });
};
