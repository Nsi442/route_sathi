import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { errorMessage } from '../../api/client';
import { authorityApi } from '../../api/endpoints';
import AuthorityShell from '../../components/AuthorityShell';
import Badge, { PriorityBadge } from '../../components/Badge';
import { Alert, EmptyState, Pagination, SearchInput, Spinner } from '../../components/Ui';
import { IconList } from '../../components/Icons';
import { formatDateTime } from '../../lib/format';

const EMPTY_FILTERS = {
  issue_type: '',
  severity: '',
  validation_status: '',
  status: '',
  source: '',
  location: '',
  date_from: '',
  date_to: '',
};

/**
 * Authority reports table.
 *
 * Filters (issue type, severity, validation, status, source, date, location)
 * and full-text search are all applied server-side so paging stays correct.
 * Priority is shown when present but is never required.
 */
export default function Reports() {
  const [options, setOptions] = useState(null);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [data, setData] = useState({ items: [], total: 0, page: 1, pages: 1, page_size: 20 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    authorityApi
      .filters()
      .then(setOptions)
      .catch(() => setOptions(null));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = { page, page_size: 20, sort: 'timestamp_desc' };
      Object.entries(filters).forEach(([key, value]) => {
        if (value) params[key] = value;
      });
      if (search.trim()) params.search = search.trim();
      setData(await authorityApi.reports(params));
    } catch (err) {
      setError(errorMessage(err, 'Could not load the reports.'));
    } finally {
      setLoading(false);
    }
  }, [filters, search, page]);

  useEffect(() => {
    const timer = setTimeout(load, search ? 300 : 0);
    return () => clearTimeout(timer);
  }, [load, search]);

  function setFilter(key, value) {
    setFilters((current) => ({ ...current, [key]: value }));
    setPage(1);
  }

  const activeCount = Object.values(filters).filter(Boolean).length + (search ? 1 : 0);

  return (
    <AuthorityShell
      title="Reports"
      subtitle={`${data.total} report${data.total === 1 ? '' : 's'} matching the current view`}
      actions={
        activeCount > 0 ? (
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => {
              setFilters(EMPTY_FILTERS);
              setSearch('');
              setPage(1);
            }}
          >
            Clear {activeCount} filter{activeCount === 1 ? '' : 's'}
          </button>
        ) : null
      }
    >
      <div className="filter-bar mb-4">
        <SearchInput
          value={search}
          onChange={(value) => {
            setSearch(value);
            setPage(1);
          }}
          placeholder="Search report ID, location, issue type or description…"
          aria-label="Search reports"
        />

        <Select
          label="Issue type"
          value={filters.issue_type}
          options={options?.issue_types}
          onChange={(value) => setFilter('issue_type', value)}
        />
        <Select
          label="Severity"
          value={filters.severity}
          options={options?.severities}
          onChange={(value) => setFilter('severity', value)}
        />
        <Select
          label="Validation"
          value={filters.validation_status}
          options={options?.validation_statuses}
          onChange={(value) => setFilter('validation_status', value)}
        />
        <Select
          label="Status"
          value={filters.status}
          options={options?.statuses}
          onChange={(value) => setFilter('status', value)}
        />
        <Select
          label="Source"
          value={filters.source}
          options={options?.sources}
          onChange={(value) => setFilter('source', value)}
        />

        <div>
          <label className="tiny muted" htmlFor="filter-location">
            Location
          </label>
          <input
            id="filter-location"
            className="input"
            value={filters.location}
            placeholder="e.g. Park Street"
            onChange={(event) => setFilter('location', event.target.value)}
          />
        </div>
        <div>
          <label className="tiny muted" htmlFor="filter-from">
            From date
          </label>
          <input
            id="filter-from"
            className="input"
            type="date"
            value={filters.date_from}
            onChange={(event) => setFilter('date_from', event.target.value)}
          />
        </div>
        <div>
          <label className="tiny muted" htmlFor="filter-to">
            To date
          </label>
          <input
            id="filter-to"
            className="input"
            type="date"
            value={filters.date_to}
            onChange={(event) => setFilter('date_to', event.target.value)}
          />
        </div>
      </div>

      {error && (
        <div className="mb-4">
          <Alert tone="error">{error}</Alert>
        </div>
      )}

      <div className="card">
        {loading ? (
          <Spinner label="Loading reports" />
        ) : data.items.length === 0 ? (
          <EmptyState
            icon={<IconList />}
            title="No reports match these filters"
            description="Adjust the filters, or import reports from the dashboard."
          />
        ) : (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Report ID</th>
                    <th>Issue Type</th>
                    <th>Location</th>
                    <th>Severity</th>
                    <th>Timestamp</th>
                    <th>Validation</th>
                    <th>Status</th>
                    <th>Priority</th>
                    <th style={{ textAlign: 'right' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((report) => (
                    <tr key={report.report_id}>
                      <td className="mono">{report.report_id}</td>
                      <td className="cell-primary">{report.issue_type}</td>
                      <td className="truncate" style={{ maxWidth: 200 }}>
                        {report.location_text || '—'}
                      </td>
                      <td>
                        <Badge value={report.severity} dot />
                      </td>
                      <td className="tiny">{formatDateTime(report.timestamp)}</td>
                      <td>
                        <Badge value={report.validation_status} />
                      </td>
                      <td>
                        <Badge value={report.status} dot />
                      </td>
                      <td>
                        <PriorityBadge
                          predicted={report.predicted_priority}
                          final={report.final_priority}
                        />
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <Link
                          to={`/authority/reports/${report.report_id}`}
                          className="btn btn-secondary btn-sm"
                        >
                          Review
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              page={data.page}
              pages={data.pages}
              total={data.total}
              pageSize={data.page_size}
              onChange={setPage}
            />
          </>
        )}
      </div>
    </AuthorityShell>
  );
}

function Select({ label, value, options, onChange }) {
  const id = `filter-${label.toLowerCase().replace(/\s+/g, '-')}`;
  return (
    <div>
      <label className="tiny muted" htmlFor={id}>
        {label}
      </label>
      <select
        id={id}
        className="select"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">All</option>
        {(options || []).map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </div>
  );
}
