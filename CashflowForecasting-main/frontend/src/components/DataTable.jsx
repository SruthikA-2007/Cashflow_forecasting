import React, { useState } from 'react';
import { ChevronLeft, ChevronRight, Search } from 'lucide-react';
import LoadingState from './LoadingState';
import EmptyState from './EmptyState';

/**
 * Reusable DataTable component for financial data grids
 * Supports:
 * - Column definitions
 * - Data input
 * - Loading state
 * - Empty state
 *
 * @param {Array<{ header: string, accessor?: string, render?: Function, align?: string, width?: string }>} columns - Column definitions
 * @param {Array<Object>} data - Data rows input
 * @param {boolean} isLoading - Loading state flag
 * @param {string} loadingMessage - Optional text when loading
 * @param {string} emptyTitle - Headline for empty state
 * @param {string} emptyMessage - Details for empty state
 * @param {React.ComponentType} emptyIcon - Custom empty icon
 * @param {React.ReactNode} emptyAction - Action button in empty state
 * @param {boolean} searchable - Whether to render built-in search input
 * @param {string|Function} searchKey - Property key or accessor function for search matching
 * @param {string} searchPlaceholder - Placeholder text for search
 * @param {number} pageSize - Number of rows per page
 * @param {boolean} pagination - Whether pagination is enabled
 * @param {Function} renderActions - Action column render function: (row: Object) => React.ReactNode
 * @param {Function} onRowClick - Optional row click handler: (row: Object) => void
 */
export const DataTable = ({
  columns = [],
  data = [],
  isLoading = false,
  loadingMessage = 'Loading records...',
  emptyTitle = 'No records found',
  emptyMessage = 'There are no records matching the specified criteria.',
  emptyIcon,
  emptyAction,
  searchable = false,
  searchKey = 'name',
  searchPlaceholder = 'Search records...',
  pageSize = 6,
  pagination = true,
  renderActions,
  onRowClick,
  className = '',
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);

  // Filter records if search is active
  const filteredData = React.useMemo(() => {
    if (!searchable || !searchTerm) return data;
    return data.filter((item) => {
      const valueToSearch =
        typeof searchKey === 'function' ? searchKey(item) : item[searchKey];
      if (valueToSearch === undefined || valueToSearch === null) return false;
      return String(valueToSearch).toLowerCase().includes(searchTerm.toLowerCase());
    });
  }, [data, searchable, searchTerm, searchKey]);

  const totalPages = Math.ceil(filteredData.length / pageSize) || 1;
  const startIndex = (currentPage - 1) * pageSize;
  const paginatedData = pagination
    ? filteredData.slice(startIndex, startIndex + pageSize)
    : filteredData;

  const handleSearchChange = (e) => {
    setSearchTerm(e.target.value);
    setCurrentPage(1);
  };

  return (
    <div className={`datatable-root ${className}`} style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
      {/* Optional Integrated Search */}
      {searchable && (
        <div className="filter-bar">
          <div className="search-input-wrapper">
            <Search className="search-icon" />
            <input
              type="text"
              className="search-input"
              placeholder={searchPlaceholder}
              value={searchTerm}
              onChange={handleSearchChange}
            />
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Showing <strong>{paginatedData.length}</strong> of <strong>{filteredData.length}</strong> records
          </div>
        </div>
      )}

      {/* Main Table Container */}
      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              {columns.map((col, idx) => (
                <th
                  key={idx}
                  style={{
                    textAlign: col.align || 'left',
                    width: col.width,
                  }}
                >
                  {col.header}
                </th>
              ))}
              {renderActions && <th style={{ textAlign: 'right' }}>Actions</th>}
            </tr>
          </thead>

          <tbody>
            {/* 1. Loading State */}
            {isLoading ? (
              <tr>
                <td colSpan={columns.length + (renderActions ? 1 : 0)} style={{ padding: 0 }}>
                  <LoadingState type="table" rows={pageSize || 4} message={loadingMessage} />
                </td>
              </tr>
            ) : filteredData.length === 0 ? (
              /* 2. Empty State */
              <tr>
                <td colSpan={columns.length + (renderActions ? 1 : 0)} style={{ padding: 0 }}>
                  <EmptyState
                    title={emptyTitle}
                    description={emptyMessage}
                    icon={emptyIcon}
                    action={emptyAction}
                  />
                </td>
              </tr>
            ) : (
              /* 3. Data Rows */
              paginatedData.map((row, rowIdx) => (
                <tr
                  key={row.id || rowIdx}
                  onClick={() => onRowClick && onRowClick(row)}
                  style={{ cursor: onRowClick ? 'pointer' : 'default' }}
                >
                  {columns.map((col, colIdx) => (
                    <td key={colIdx} style={{ textAlign: col.align || 'left' }}>
                      {col.render ? col.render(row) : row[col.accessor]}
                    </td>
                  ))}
                  {renderActions && (
                    <td style={{ textAlign: 'right' }}>{renderActions(row)}</td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Controls */}
      {!isLoading && pagination && totalPages > 1 && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '0.8rem',
            color: 'var(--text-secondary)',
            marginTop: '0.25rem',
          }}
        >
          <span>Page {currentPage} of {totalPages}</span>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => setCurrentPage((p) => Math.max(p - 1, 1))}
              disabled={currentPage === 1}
              style={{ opacity: currentPage === 1 ? 0.5 : 1 }}
            >
              <ChevronLeft size={16} /> Previous
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => setCurrentPage((p) => Math.min(p + 1, totalPages))}
              disabled={currentPage === totalPages}
              style={{ opacity: currentPage === totalPages ? 0.5 : 1 }}
            >
              Next <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default DataTable;
