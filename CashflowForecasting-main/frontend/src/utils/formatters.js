/**
 * Format currency numbers with locale formatting and optional decimals
 */
export const formatCurrency = (amount, decimals = 0) => {
  if (amount === undefined || amount === null || isNaN(amount)) return '₹0';
  const num = Number(amount);
  const isNeg = num < 0;
  const absNum = Math.abs(num);
  try {
    const formatted = new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: decimals,
      minimumFractionDigits: decimals,
    }).format(absNum);
    return isNeg ? `-${formatted}` : formatted;
  } catch {
    return `${isNeg ? '-' : ''}₹${absNum.toLocaleString('en-IN')}`;
  }
};

/**
 * Format compact currency for charts and high-level KPI cards (e.g. ₹1.2L, ₹45K)
 */
export const formatCompactCurrency = (amount) => {
  if (amount === undefined || amount === null || isNaN(amount)) return '₹0';
  const num = Number(amount);
  const isNeg = num < 0;
  const absNum = Math.abs(num);
  let res = '';
  if (absNum >= 10_000_000) {
    res = `₹${(absNum / 10_000_000).toFixed(1)} Cr`;
  } else if (absNum >= 100_000) {
    res = `₹${(absNum / 100_000).toFixed(1)} L`;
  } else if (absNum >= 1_000) {
    res = `₹${(absNum / 1_000).toFixed(0)}K`;
  } else {
    res = `₹${absNum.toFixed(0)}`;
  }
  return isNeg ? `-${res}` : res;
};

/**
 * Format percentage values
 */
export const formatPercent = (value, decimals = 1) => {
  if (value === undefined || value === null || isNaN(value)) return '0%';
  return `${Number(value).toFixed(decimals)}%`;
};

/**
 * Format date string into readable format (e.g. Oct 24, 2026)
 */
export const formatDate = (dateString) => {
  if (!dateString) return '—';
  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return dateString;
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    }).format(date);
  } catch {
    return dateString;
  }
};

/**
 * Format relative days (e.g. "+5 days", "-2 days", "On Time")
 */
export const formatDelayDays = (days) => {
  if (days === undefined || days === null) return '0 days';
  const num = Number(days);
  if (num === 0) return 'On Time';
  if (num > 0) return `+${num} days late`;
  return `${Math.abs(num)} days early`;
};

/**
 * Calculate risk level based on risk score (0 to 100)
 */
export const getRiskLevel = (score) => {
  if (score >= 75) return 'High';
  if (score >= 45) return 'Medium';
  return 'Low';
};
