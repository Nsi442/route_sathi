import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { errorMessage } from '../../api/client';
import { authorityApi } from '../../api/endpoints';
import AuthorityShell from '../../components/AuthorityShell';
import Badge from '../../components/Badge';
import CsvUpload from '../../components/CsvUpload';
import { Alert, Spinner, StatCard } from '../../components/Ui';
import {
  IconCheck,
  IconClock,
  IconList,
  IconReport,
  IconShield,
  IconSpark,
  IconWrench,
} from '../../components/Icons';
import { useAuth } from '../../context/AuthContext';
import { formatDateTime, timeAgo } from '../../lib/format';

/**
 * Authority dashboard - the first page of the portal.
 *
 * The CSV importer lives here (not on the reports page), and every counter is
 * computed from PostgreSQL by `GET /api/authority/overview`.
 */
export default function Dashboard() {
  const { user } = useAuth();
  const [overview, setOverview] = useState(null);
  const [recent, setRecent] = useState([]);
  const [audit, setAudit] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [overviewData, reportData, auditData] = await Promise.all([
        authorityApi.overview(),
        authorityApi.reports({ page_size: 8, sort: 'timestamp_desc' }),
        authorityApi.audit({ limit: 8 }),
      ]);
      setOverview(overviewData);
      setRecent(reportData.items);
      setAudit(auditData);
    } catch (err) {
      setError(errorMessage(err, 'Could not load the dashboard.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <AuthorityShell
      title="Dashboard Overview"
      subtitle={user?.organisation || 'Municipal accessibility management'}
      actions={
        <Link to="/authority/reports" className="btn btn-secondary btn-sm">
          View all reports
        </Link>
      }
    >
      {error && (
        <div className="mb-4">
          <Alert tone="error">{error}</Alert>
        </div>
      )}

      {loading && !overview ? (
        <Spinner label="Loading dashboard" />
      ) : (
        <>
          <div className="stat-grid mb-4">
            <StatCard
              label="Total Reports"
              value={overview?.total_reports ?? 0}
              accent="teal"
              icon={<IconList width={17} height={17} />}
            />
            <StatCard
              label="New Reports"
              value={overview?.new_reports ?? 0}
              accent="blue"
              icon={<IconReport width={17} height={17} />}
            />
            <StatCard
              label="Under Review"
              value={overview?.under_review ?? 0}
              accent="amber"
              icon={<IconClock width={17} height={17} />}
            />
            <StatCard
              label="Valid Reports"
              value={overview?.valid_reports ?? 0}
              accent="green"
              icon={<IconShield width={17} height={17} />}
            />
            <StatCard
              label="Assigned Tasks"
              value={overview?.assigned_tasks ?? 0}
              accent="violet"
              icon={<IconWrench width={17} height={17} />}
            />
            <StatCard
              label="In Progress"
              value={overview?.in_progress ?? 0}
              accent="teal"
              icon={<IconSpark width={17} height={17} />}
            />
            <StatCard
              label="Resolved"
              value={overview?.resolved ?? 0}
              accent="green"
              icon={<IconCheck width={17} height={17} />}
              hint={`${overview?.resolution_rate ?? 0}% resolution rate`}
            />
            <StatCard
              label="Awaiting Verification"
              value={overview?.awaiting_verification ?? 0}
              accent="red"
              icon={<IconClock width={17} height={17} />}
            />
          </div>

          <div className="mb-4">
            <CsvUpload onImported={load} />
          </div>

          <div className="split-2">
            <div className="card">
              <div className="card-header">
                <div>
                  <h2>Recent Reports</h2>
                  <div className="card-title-sub">Newest submissions and imports</div>
                </div>
                <Link to="/authority/reports" className="btn btn-ghost btn-sm">
                  See all
                </Link>
              </div>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Report ID</th>
                      <th>Issue Type</th>
                      <th>Severity</th>
                      <th>Validation</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recent.length === 0 && (
                      <tr>
                        <td colSpan={5} className="center muted">
                          No reports yet. Upload a CSV to get started.
                        </td>
                      </tr>
                    )}
                    {recent.map((report) => (
                      <tr key={report.report_id}>
                        <td className="mono">
                          <Link to={`/authority/reports/${report.report_id}`}>
                            {report.report_id}
                          </Link>
                        </td>
                        <td className="cell-primary">{report.issue_type}</td>
                        <td>
                          <Badge value={report.severity} dot />
                        </td>
                        <td>
                          <Badge value={report.validation_status} />
                        </td>
                        <td>
                          <Badge value={report.status} dot />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="card">
              <div className="card-header">
                <div>
                  <h2>Activity</h2>
                  <div className="card-title-sub">Audited authority and maintenance actions</div>
                </div>
              </div>
              <div className="card-body stack">
                {audit.length === 0 && <p className="muted small">No recorded activity yet.</p>}
                {audit.map((entry) => (
                  <div key={entry.id} className="row" style={{ alignItems: 'flex-start' }}>
                    <span
                      className="badge-dot"
                      style={{ background: 'var(--teal-600)', marginTop: 7 }}
                    />
                    <div className="grow">
                      <div className="small strong">{describeAction(entry)}</div>
                      <div className="tiny muted">
                        {entry.user_id} · {timeAgo(entry.timestamp)} ·{' '}
                        {formatDateTime(entry.timestamp)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </AuthorityShell>
  );
}

function describeAction(entry) {
  const labels = {
    'report.csv_import': `Imported ${entry.metadata?.successfulRows ?? 0} report(s) from ${
      entry.metadata?.filename || 'a CSV file'
    }`,
    'report.validate': `Marked ${entry.entity_id} as ${entry.metadata?.validation_status}`,
    'report.priority_predict': `Requested a priority recommendation for ${entry.entity_id}`,
    'report.priority_confirm': `Confirmed priority ${entry.metadata?.final_priority} for ${entry.entity_id}`,
    'report.status': `Moved ${entry.entity_id} to ${entry.metadata?.to}`,
    'report.create': `New citizen report ${entry.entity_id}`,
    'report.delete': `Deleted report ${entry.entity_id}`,
    'task.assign': `Assigned ${entry.metadata?.report_id} to ${entry.metadata?.team}`,
    'task.status': `Task ${entry.entity_id} moved to ${entry.metadata?.to}`,
    'task.notes': `Maintenance notes updated on ${entry.entity_id}`,
    'task.resolution_upload': `Resolution photo uploaded for ${entry.metadata?.report_id}`,
    'task.verify': `Verified the resolution of ${entry.metadata?.report_id}`,
    'task.reject': `Sent ${entry.metadata?.report_id} back for rework`,
    'facility.create': `Added facility ${entry.entity_id}`,
    'facility.update': `Updated facility ${entry.entity_id}`,
    'user.login': 'Signed in',
    'user.signup': 'Created an account',
  };
  return labels[entry.action] || `${entry.action} ${entry.entity_id || ''}`.trim();
}
