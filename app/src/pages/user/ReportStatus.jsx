import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { errorMessage } from '../../api/client';
import { reportApi, userApi } from '../../api/endpoints';
import Badge, { PriorityBadge } from '../../components/Badge';
import MapView, { reportMarker } from '../../components/MapView';
import UserShell from '../../components/UserShell';
import { Alert, Spinner } from '../../components/Ui';
import { formatDateTime } from '../../lib/format';

/** The stages a citizen sees, in order. */
const STAGES = [
  { key: 'Submitted', title: 'Report submitted', body: 'We received your report.' },
  {
    key: 'Under Review',
    title: 'Under review',
    body: 'An authority reviewer is checking the details and evidence.',
  },
  {
    key: 'Assigned',
    title: 'Assigned to a team',
    body: 'A maintenance team has been given this repair.',
  },
  {
    key: 'In Progress',
    title: 'Repair in progress',
    body: 'Work is underway on site.',
  },
  {
    key: 'Resolved',
    title: 'Resolved',
    body: 'The repair was completed and verified by the authority.',
  },
];

export default function ReportStatus() {
  const { reportId } = useParams();
  const [report, setReport] = useState(null);
  const [imageUrl, setImageUrl] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    userApi
      .report(reportId)
      .then((data) => {
        if (!active) return;
        setReport(data);
        if (data.has_image) {
          reportApi
            .imageLink(data.report_id)
            .then((link) => active && setImageUrl(link.url))
            .catch(() => {});
        }
      })
      .catch((err) => active && setError(errorMessage(err, 'Could not load this report.')))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [reportId]);

  const currentIndex = report ? STAGES.findIndex((stage) => stage.key === report.status) : -1;

  return (
    <UserShell title="Report Status" back plainHeader narrow>
      {loading && <Spinner label="Loading report" />}
      {error && <Alert tone="error">{error}</Alert>}

      {report && (
        <>
          <div className="card card-pad mb-3">
            <div className="row-between mb-2">
              <h2>{report.issue_type}</h2>
              <Badge value={report.status} dot />
            </div>
            <p className="small muted">
              {report.report_id} · {formatDateTime(report.timestamp)}
            </p>
            {report.description && (
              <p className="small mt-3" style={{ color: 'var(--ink-700)' }}>
                {report.description}
              </p>
            )}
            <div className="row wrap mt-3">
              <Badge value={report.severity} dot />
              <Badge value={report.validation_status} />
              <PriorityBadge
                predicted={report.predicted_priority}
                final={report.final_priority}
              />
            </div>
          </div>

          <div className="card mb-3">
            <div className="card-header">
              <h3>Progress</h3>
            </div>
            <div className="card-body">
              <div className="timeline">
                {STAGES.map((stage, index) => {
                  const done = currentIndex >= 0 && index < currentIndex;
                  const current = index === currentIndex;
                  return (
                    <div
                      key={stage.key}
                      className={`timeline-item ${done ? 'is-done' : ''} ${
                        current ? 'is-current' : ''
                      }`.trim()}
                    >
                      <div className="timeline-marker">
                        <span className="timeline-dot" />
                        {index < STAGES.length - 1 && <span className="timeline-line" />}
                      </div>
                      <div className="timeline-body">
                        <div
                          className="timeline-title"
                          style={{
                            color: done || current ? 'var(--ink-900)' : 'var(--ink-400)',
                          }}
                        >
                          {stage.title}
                        </div>
                        <div className="timeline-time">{stage.body}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {report.task && (
            <div className="card mb-3">
              <div className="card-header">
                <h3>Maintenance</h3>
                <Badge value={report.task.status} dot />
              </div>
              <div className="card-body">
                <dl className="detail-list">
                  <div className="detail-row">
                    <dt>Team</dt>
                    <dd>{report.task.assigned_team}</dd>
                  </div>
                  <div className="detail-row">
                    <dt>Assigned</dt>
                    <dd>{formatDateTime(report.task.assigned_at)}</dd>
                  </div>
                  {report.task.completed_at && (
                    <div className="detail-row">
                      <dt>Completed</dt>
                      <dd>{formatDateTime(report.task.completed_at)}</dd>
                    </div>
                  )}
                  {report.task.maintenance_notes && (
                    <div className="detail-row">
                      <dt>Notes</dt>
                      <dd>{report.task.maintenance_notes}</dd>
                    </div>
                  )}
                </dl>
              </div>
            </div>
          )}

          {imageUrl && (
            <div className="card mb-3">
              <div className="card-header">
                <h3>Your evidence</h3>
              </div>
              <div className="card-body">
                <img
                  src={imageUrl}
                  alt={`Evidence submitted with report ${report.report_id}`}
                  className="evidence-image"
                />
              </div>
            </div>
          )}

          <MapView
            center={{ latitude: report.latitude, longitude: report.longitude }}
            zoom={17}
            height="map-height-sm"
            showLegend={false}
            markers={[reportMarker(report)]}
          />

          <dl className="detail-list mt-3">
            <div className="detail-row">
              <dt>Location</dt>
              <dd>
                {report.location_text || '—'}
                <div className="tiny muted">
                  {report.latitude.toFixed(5)}, {report.longitude.toFixed(5)}
                </div>
              </dd>
            </div>
            {report.validated_at && (
              <div className="detail-row">
                <dt>Reviewed</dt>
                <dd>{formatDateTime(report.validated_at)}</dd>
              </div>
            )}
            <div className="detail-row">
              <dt>Last updated</dt>
              <dd>{formatDateTime(report.updated_at)}</dd>
            </div>
          </dl>
        </>
      )}
    </UserShell>
  );
}
