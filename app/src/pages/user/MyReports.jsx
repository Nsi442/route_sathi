import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { errorMessage } from '../../api/client';
import { userApi } from '../../api/endpoints';
import Badge from '../../components/Badge';
import UserShell from '../../components/UserShell';
import { Alert, EmptyState, Pagination, SearchInput, Spinner } from '../../components/Ui';
import { IconList, IconReport } from '../../components/Icons';
import { timeAgo } from '../../lib/format';

const STATUS_FILTERS = [
  '',
  'Submitted',
  'Under Review',
  'Assigned',
  'In Progress',
  'Resolved',
];

export default function MyReports() {
  const [items, setItems] = useState([]);
  const [meta, setMeta] = useState({ total: 0, page: 1, pages: 1, page_size: 20 });
  const [status, setStatus] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await userApi.reports({
        status: status || undefined,
        search: search.trim() || undefined,
        page,
        page_size: 20,
      });
      setItems(data.items);
      setMeta({
        total: data.total,
        page: data.page,
        pages: data.pages,
        page_size: data.page_size,
      });
    } catch (err) {
      setError(errorMessage(err, 'Could not load your reports.'));
    } finally {
      setLoading(false);
    }
  }, [status, search, page]);

  useEffect(() => {
    const timer = setTimeout(load, search ? 300 : 0);
    return () => clearTimeout(timer);
  }, [load, search]);

  return (
    <UserShell title="My Reports" plainHeader>
      <div className="mb-3">
        <SearchInput
          value={search}
          onChange={(value) => {
            setSearch(value);
            setPage(1);
          }}
          placeholder="Search by ID, issue or place…"
          aria-label="Search your reports"
        />
      </div>

      <div className="filter-chips" style={{ margin: '0 -16px 14px', borderRadius: 0 }}>
        {STATUS_FILTERS.map((value) => (
          <button
            key={value || 'all'}
            type="button"
            className={`chip ${status === value ? 'is-active' : ''}`.trim()}
            aria-pressed={status === value}
            onClick={() => {
              setStatus(value);
              setPage(1);
            }}
          >
            {value || 'All'}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-3">
          <Alert tone="error">{error}</Alert>
        </div>
      )}

      {loading ? (
        <Spinner label="Loading your reports" />
      ) : items.length === 0 ? (
        <EmptyState
          icon={<IconList />}
          title={status ? `No ${status.toLowerCase()} reports` : 'No reports yet'}
          description="When you report an accessibility barrier it will appear here with its live status."
          action={
            <Link to="/report" className="btn btn-primary mt-2">
              Report an issue
            </Link>
          }
        />
      ) : (
        <>
          <div className="stack is-responsive-grid">
            {items.map((report) => (
              <Link
                key={report.report_id}
                to={`/my-reports/${report.report_id}`}
                className="list-row"
              >
                <span className="row-icon">
                  <IconReport width={18} height={18} />
                </span>
                <div className="grow">
                  <div className="row-title">{report.issue_type}</div>
                  <div className="row-meta truncate">
                    {report.report_id} · {report.location_text || 'Location not provided'}
                  </div>
                  <div className="tiny muted mt-2">{timeAgo(report.timestamp)}</div>
                </div>
                <div className="row-end">
                  <Badge value={report.status} dot />
                  <Badge value={report.severity} />
                </div>
              </Link>
            ))}
          </div>

          <div className="card mt-3">
            <Pagination
              page={meta.page}
              pages={meta.pages}
              total={meta.total}
              pageSize={meta.page_size}
              onChange={setPage}
            />
          </div>
        </>
      )}
    </UserShell>
  );
}
