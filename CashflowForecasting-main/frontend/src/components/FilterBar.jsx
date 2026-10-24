import React from 'react';
import { Search } from 'lucide-react';

/**
 * Reusable FilterBar component for financial tables and listings
 * @param {string} searchValue - Current search query
 * @param {Function} onSearchChange - Callback for search input: (term: string) => void
 * @param {string} searchPlaceholder - Placeholder text
 * @param {Array<{ key: string, label: string, count?: number, color?: string }>} filterOptions - Filter pill options
 * @param {string} activeFilter - Key of the active filter
 * @param {Function} onFilterChange - Callback when filter pill changes: (key: string) => void
 * @param {React.ReactNode} children - Additional custom controls (e.g. dropdowns, export buttons)
 * @param {string} summaryText - Optional counter text (e.g. "Showing 8 of 14 records")
 */
export const FilterBar = ({
  searchValue,
  onSearchChange,
  searchPlaceholder = 'Search records...',
  filterOptions = [],
  activeFilter,
  onFilterChange,
  children,
  summaryText,
  className = '',
}) => {
  return (
    <div className={`filter-bar ${className}`} style={{ marginBottom: '1rem' }}>
      {/* Search Input */}
      {onSearchChange && (
        <div className="search-input-wrapper">
          <Search className="search-icon" />
          <input
            type="text"
            className="search-input"
            placeholder={searchPlaceholder}
            value={searchValue ?? ''}
            onChange={(e) => onSearchChange(e.target.value)}
          />
        </div>
      )}

      {/* Filter Pills / Tabs */}
      {filterOptions.length > 0 && onFilterChange && (
        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', alignItems: 'center' }}>
          {filterOptions.map((opt) => {
            const isActive = activeFilter === opt.key;
            return (
              <button
                key={opt.key}
                type="button"
                className={`btn btn-sm ${isActive ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => onFilterChange(opt.key)}
                style={
                  isActive && opt.color
                    ? { backgroundColor: opt.color, borderColor: opt.color, color: opt.textColor || '#fff' }
                    : {}
                }
              >
                {opt.label}
                {opt.count !== undefined && (
                  <span style={{ opacity: 0.85, fontSize: '0.75rem', marginLeft: '2px' }}>
                    ({opt.count})
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}

      {/* Extra children and summary */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginLeft: 'auto', flexWrap: 'wrap' }}>
        {children}
        {summaryText && (
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            {summaryText}
          </span>
        )}
      </div>
    </div>
  );
};

export default FilterBar;
