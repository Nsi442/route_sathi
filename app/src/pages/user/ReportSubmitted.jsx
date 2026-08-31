import { Link, Navigate, useLocation } from 'react-router-dom';
import Badge from '../../components/Badge';
import UserShell from '../../components/UserShell';
import { IconCheck } from '../../components/Icons';
import { formatDateTime } from '../../lib/format';

/** Confirmation screen shown straight after a successful submission. */
export default function ReportSubmitted() {
  const { state } = useLocation();
  const report = state?.report;

  if (!report) return <Navigate to="/my-reports" replace />;

  return (
    <UserShell title="Report Submitted" plainHeader hideTabs>
      <div className="card card-pad center mb-3">
        <span
          className="empty-icon"
          style={{
            margin: '4px auto 12px',
            width: 64,
            height: 64,
            background: 'var(--green-100)',
            color: 'var(--green-700)',
          }}
        >
          <IconCheck width={30} height={30} />
        </span>
        <h2>Thank you</h2>
        <p className="small muted mt-2">
          Your report has been sent to the municipal accessibility team. You will be
          notified as it moves through review and repair.
        </p>
      </div>

      <dl className="detail-list mb-3">
        <div className="detail-row">
          <dt>Report ID</dt>
          <dd className="strong">{report.report_id}</dd>
        </div>
        <div className="detail-row">
          <dt>Issue type</dt>
          <dd>{report.issue_type}</dd>
        </div>
        <div className="detail-row">
          <dt>Severity</dt>
          <dd>
            <Badge value={report.severity} dot />
          </dd>
        </div>
        <div className="detail-row">
          <dt>Submitted</dt>
          <dd>{formatDateTime(report.timestamp)}</dd>
        </div>
        <div className="detail-row">
          <dt>Status</dt>
          <dd>
            <Badge value={report.status} dot />
          </dd>
        </div>
        <div className="detail-row">
          <dt>Validation</dt>
          <dd>
            <Badge value={report.validation_status} dot />
          </dd>
        </div>
      </dl>

      <Link to={`/my-reports/${report.report_id}`} className="btn btn-primary btn-block mb-2">
        Track this report
      </Link>
      <Link to="/home" className="btn btn-secondary btn-block">
        Back to home
      </Link>
    </UserShell>
  );
}
