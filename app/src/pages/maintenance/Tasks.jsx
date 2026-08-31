import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { errorMessage } from '../../api/client';
import { maintenanceApi } from '../../api/endpoints';
import Badge, { PriorityBadge } from '../../components/Badge';
import MaintenanceShell from '../../components/MaintenanceShell';
import { Alert, EmptyState, Pagination, SearchInput, Spinner, StatCard } from '../../components/Ui';
import { IconCheck, IconClock, IconShield, IconWrench } from '../../components/Icons';
import { useAuth } from '../../context/AuthContext';
import { formatDateTime } from '../../lib/format';

/**
 * Maintenance task list.
 *
 * `filter` selects which slice of the worker's queue is shown; the API only
 * ever returns tasks assigned to this user or to their team.
 */
export default function Tasks({ filter = 'all' }) {
  const { user } = useAuth();
  const [summary, setSummary] = useState(null);
  const [data, setData] = useState({ items: [], total: 0, page: 1, pages: 1, page_size: 20 });
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const statusFilter = { active: 'In Progress', completed: 'Completed' }[filter];

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [summaryData, taskData] = await Promise.all([
        maintenanceApi.summary(),
        maintenanceApi.tasks({
          status: statusFilter,
          search: search.trim() || undefined,
          page,
          page_size: 20,
        }),
      ]);
      setSummary(summaryData);
      setData(taskData);
    } catch (err) {
      setError(errorMessage(err, 'Could not load your tasks.'));
    } finally {
      setLoading(false);
    }
  }, [statusFilter, search, page]);

  useEffect(() => {
    const timer = setTimeout(load, search ? 300 : 0);
    return () => clearTimeout(timer);
  }, [load, search]);

  const titles = {
    all: 'My Tasks',
    active: 'In Progress',
    completed: 'Completed Tasks',
  };

  return (
    <MaintenanceShell
      title={titles[filter]}
      subtitle={`${user?.team || 'Maintenance'} · ${data.total} task${
        data.total === 1 ? '' : 's'
      }`}
    >
      {error && (
        <div className="mb-4">
          <Alert tone="error">{error}</Alert>
        </div>
      )}

      {filter === 'all' && (
        <div className="stat-grid mb-4">
          <StatCard
            label="Assigned"
            value={summary?.assigned ?? 0}
            accent="violet"
            icon={<IconClock width={17} height={17} />}
          />
          <StatCard
            label="In Progress"
            value={summary?.in_progress ?? 0}
            accent="teal"
            icon={<IconWrench width={17} height={17} />}
          />
          <StatCard
            label="Awaiting Verification"
            value={summary?.completed ?? 0}
            accent="amber"
            icon={<IconShield width={17} height={17} />}
          />
          <StatCard
            label="Verified"
            value={summary?.verified ?? 0}
            accent="green"
            icon={<IconCheck width={17} height={17} />}
          />
        </div>
      )}

      <div className="filter-bar mb-4">
        <SearchInput
          value={search}
          onChange={(value) => {
            setSearch(value);
            setPage(1);
          }}
          placeholder="Search task or report ID…"
          aria-label="Search tasks"
        />
      </div>

      <div className="card">
        {loading ? (
          <Spinner label="Loading tasks" />
        ) : data.items.length === 0 ? (
          <EmptyState
            icon={<IconWrench />}
            title="Nothing here right now"
            description={
              filter === 'all'
                ? 'When the authority assigns a repair to you or your team it will appear here.'
                : 'No tasks in this state.'
            }
          />
        ) : (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Task ID</th>
                    <th>Report</th>
                    <th>Issue Type</th>
                    <th>Location</th>
                    <th>Priority</th>
                    <th>Assigned</th>
                    <th>Status</th>
                    <th style={{ textAlign: 'right' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((task) => (
                    <tr key={task.task_id}>
                      <td className="mono">{task.task_id}</td>
                      <td className="mono">{task.report_id}</td>
                      <td className="cell-primary">{task.report?.issue_type || '—'}</td>
                      <td className="truncate" style={{ maxWidth: 200 }}>
                        {task.report?.location_text || '—'}
                      </td>
                      <td>
                        <PriorityBadge
                          predicted={task.report?.predicted_priority}
                          final={task.report?.final_priority}
                        />
                      </td>
                      <td className="tiny">{formatDateTime(task.assigned_at)}</td>
                      <td>
                        <Badge value={task.status} dot />
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <Link
                          to={`/maintenance/tasks/${task.task_id}`}
                          className="btn btn-primary btn-sm"
                        >
                          Open
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
    </MaintenanceShell>
  );
}
