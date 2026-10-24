/**
 * Dashboard Data Service - AI Cash Flow Early Warning System
 * Decoupled data provider containing realistic financial mock datasets.
 * Designed for immediate plug-and-play API replacement without touching UI components.
 */

export const mockDashboardData = {
  summaryCards: {
    totalInvoicesAnalysed: {
      value: 58,
      change: 12.0,
      changeText: 'vs. last cycle (52)',
      helperText: 'Across 8 active corporate client accounts',
    },
    highRiskInvoices: {
      value: 8,
      change: 14.3,
      changeText: '13.8% of portfolio',
      helperText: '$142,800 total capital at risk',
      isNegativeGood: true,
    },
    lowRiskInvoices: {
      value: 32,
      change: 6.7,
      changeText: '55.2% of portfolio',
      helperText: '$382,400 secure cash collections',
      isNegativeGood: false,
    },
    estimatedCashFlowDeviation: {
      amount: -48500,
      percentage: -7.1,
      changeText: 'Delayed liquidity buffer',
      helperText: 'Projected net delay of 14.5 days on at-risk capital',
    },
  },

  riskDistribution: {
    totalInvoices: 58,
    totalAmount: 684500,
    categories: [
      {
        key: 'low',
        name: 'Low-Risk Invoices',
        count: 32,
        percentage: 55,
        amount: 382400,
        color: 'var(--risk-low)',
        description: 'Expected settlement on time (< 5 days variance)',
      },
      {
        key: 'medium',
        name: 'Medium-Risk Invoices',
        count: 18,
        percentage: 31,
        amount: 159300,
        color: 'var(--risk-medium)',
        description: 'Moderate delay expected (5–15 days variance)',
      },
      {
        key: 'high',
        name: 'High-Risk Invoices',
        count: 8,
        percentage: 14,
        amount: 142800,
        color: 'var(--risk-high)',
        description: 'Severe delay probability (> 15 days or default risk)',
      },
    ],
  },

  topHighRiskInvoices: [
    {
      id: 'INV-2026-881',
      customerName: 'Apex Logistics Inc.',
      customerId: 'CUST-101',
      invoiceAmount: 48500,
      riskLevel: 'High Risk',
      riskScore: 88,
      expectedDelayDays: 17,
      cashFlowImpact: -48500,
      dueDate: '2026-08-28',
      predictedPaymentDate: '2026-09-14',
      impactSeverity: 'Critical',
      actionPrompt: 'Immediate follow-up required (payment history variance > 22 days)',
    },
    {
      id: 'INV-2026-879',
      customerName: 'Vanguard Industrial Parts',
      customerId: 'CUST-104',
      invoiceAmount: 34200,
      riskLevel: 'High Risk',
      riskScore: 78,
      expectedDelayDays: 13,
      cashFlowImpact: -34200,
      dueDate: '2026-08-26',
      predictedPaymentDate: '2026-09-08',
      impactSeverity: 'High',
      actionPrompt: 'Offer 1.5% discount for settlement within 5 business days',
    },
    {
      id: 'INV-2026-842',
      customerName: 'Quantum Softworks',
      customerId: 'CUST-106',
      invoiceAmount: 15200,
      riskLevel: 'High Risk',
      riskScore: 92,
      expectedDelayDays: 21,
      cashFlowImpact: -15200,
      dueDate: '2026-08-25',
      predictedPaymentDate: '2026-09-15',
      impactSeverity: 'Critical',
      actionPrompt: 'Overdue: Escalate to credit team for structured payment plan',
    },
    {
      id: 'INV-2026-865',
      customerName: 'Starlight Media Corp',
      customerId: 'CUST-107',
      invoiceAmount: 29800,
      riskLevel: 'High Risk',
      riskScore: 74,
      expectedDelayDays: 11,
      cashFlowImpact: -29800,
      dueDate: '2026-09-01',
      predictedPaymentDate: '2026-09-12',
      impactSeverity: 'Moderate',
      actionPrompt: 'Send automated invoice settlement reminder',
    },
    {
      id: 'INV-2026-831',
      customerName: 'Apex Logistics Inc.',
      customerId: 'CUST-101',
      invoiceAmount: 15100,
      riskLevel: 'High Risk',
      riskScore: 82,
      expectedDelayDays: 15,
      cashFlowImpact: -15100,
      dueDate: '2026-09-03',
      predictedPaymentDate: '2026-09-18',
      impactSeverity: 'High',
      actionPrompt: 'Hold additional pending shipments until accounts payable resolves',
    },
  ],
};

/**
 * Service function to retrieve dashboard metrics
 * In real production, this makes a fetch/axios call to FastAPI: GET /api/dashboard
 */
export const fetchDashboardData = async () => {
  // Simulates instant or fast resolution ready for API integration
  return Promise.resolve(mockDashboardData);
};
