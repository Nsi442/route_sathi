import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { errorMessage } from '../../api/client';
import { authorityApi } from '../../api/endpoints';
import AuthorityShell from '../../components/AuthorityShell';
import Badge from '../../components/Badge';
import { Alert, EmptyState, Modal, Pagination, SearchInput, Spinner } from '../../components/Ui';
import ResolutionImageLink from '../../components/ResolutionImageLink';
import { IconWrench } from '../../components/Icons';
import { useToast } from '../../context/ToastContext';
import { formatDateTime } from '../../lib/format';

const TASK_STATUSES = ['', 'Assigned', 'In Progress', 'Completed', 'Verified', 'Rejected'];

/** Authority view of every maintenance task, with resolution verification. */
export default function Maintenance() {
  const toast = useToast();
  const [data, setData] = useState({ items: [], total: 0, page: 1, pages: 1, page_size: 20 });
  const [status, setStatus] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [verifying, setVerifying] = useState(null);
  const [verifyNote, setVerifyNote] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setData(
        await authorityApi.tasks({
          status: status || undefined,
          search: search.trim() || undefined,
          page,
          page_size: 20,
        }),
      );
    } catch (err) {
      setError(errorMessage(err, 'Could not load maintenance tasks.'));
    } finally {
      setLoading(false);
    }
  }, [status, search, page]);

  useEffect(() => {
    const timer = setTimeout(load, search ? 300 : 0);
    return () => clearTimeout(timer);
  }, [load, search]);

  async function submitVerification(approved) {
    setBusy(true);
    try {
      await authorityApi.verify(verifying.task_id, {
        approved,
        notes: verifyNote.trim() || null,
      });
      toast.success(approved ? 'Resolution verified.' : 'Task sent back for rework.');
      setVerifying(null);
      setVerifyNote('');
      await load();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthorityShell
      title="Maintenance Overview"
      subtitle={`${data.total} task${data.total === 1 ? '' : 's'} in the current view`}
    >
      <div className="filter-bar mb-4">
        <SearchInput
          value={search}
          onChange={(value) => {
            setSearch(value);
            setPage(1);
          }}
          placeholder="Search task ID, report ID or team…"
          aria-label="Search maintenance tasks"
        />
        <div>
          <label className="tiny muted" htmlFor="task-status">
            Task status
          </label>
          <select
            id="task-status"
            className="select"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
          >
            {TASK_STATUSES.map((value) => (
              <option key={value || 'all'} value={value}>
                {value || 'All statuses'}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div className="mb-4">
          <Alert tone="error">{error}</Alert>
        </div>
      )}

      <div className="card">
        {loading ? (
          <Spinner label="Loading tasks" />
        ) : data.items.length === 0 ? (
          <EmptyState
            icon={<IconWrench />}
            title="No maintenance tasks"
            description="Assign a validated report to a team to create the first task."
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
                    <th>Team</th>
                    <th>Assigned</th>
                    <th>Status</th>
                    <th>Evidence</th>
                    <th style={{ textAlign: 'right' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((task) => (
                    <tr key={task.task_id}>
                      <td className="mono">{task.task_id}</td>
                      <td className="mono">
                        <Link to={`/authority/reports/${task.report_id}`}>{task.report_id}</Link>
                      </td>
                      <td className="cell-primary">{task.report?.issue_type || '—'}</td>
                      <td>
                        {task.assigned_team}
                        {task.assigned_to && (
                          <div className="tiny muted">{task.assigned_to}</div>
                        )}
                      </td>
                      <td className="tiny">{formatDateTime(task.assigned_at)}</td>
                      <td>
                        <Badge value={task.status} dot />
                      </td>
                      <td>
                        {task.has_resolution_image ? (
                          <ResolutionImageLink taskId={task.task_id} label="View" />
                        ) : (
                          <span className="muted tiny">None</span>
                        )}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        {task.status === 'Completed' ? (
                          <button
                            type="button"
                            className="btn btn-primary btn-sm"
                            onClick={() => {
                              setVerifying(task);
                              setVerifyNote('');
                            }}
                          >
                            Verify
                          </button>
                        ) : (
                          <Link
                            to={`/authority/reports/${task.report_id}`}
                            className="btn btn-secondary btn-sm"
                          >
                            Open
                          </Link>
                        )}
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

      {verifying && (
        <Modal title={`Verify ${verifying.task_id}`} onClose={() => setVerifying(null)}>
          <p className="small muted mb-3">
            Report {verifying.report_id} — {verifying.report?.issue_type}. Confirm the repair
            was completed to standard, or send it back with a reason.
          </p>

          {verifying.maintenance_notes && (
            <div className="alert alert-info mb-3">{verifying.maintenance_notes}</div>
          )}

          {verifying.has_resolution_image && (
            <div className="mb-3">
              <ResolutionImageLink
                taskId={verifying.task_id}
                label="Load the resolution photo"
                inline
              />
            </div>
          )}

          <label className="label" htmlFor="verify-notes">
            Verification notes
          </label>
          <textarea
            id="verify-notes"
            className="textarea"
            value={verifyNote}
            onChange={(event) => setVerifyNote(event.target.value)}
            placeholder="What did you check?"
          />

          <div className="stack-sm mt-3">
            <button
              type="button"
              className="btn btn-success btn-block"
              disabled={busy}
              onClick={() => submitVerification(true)}
            >
              {busy ? 'Saving…' : 'Approve and mark the report resolved'}
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-block"
              disabled={busy}
              onClick={() => submitVerification(false)}
            >
              Send back for rework
            </button>
          </div>
        </Modal>
      )}
    </AuthorityShell>
  );
}
