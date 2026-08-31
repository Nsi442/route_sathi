import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { errorMessage } from '../../api/client';
import { authorityApi, reportApi } from '../../api/endpoints';
import AuthorityShell from '../../components/AuthorityShell';
import Badge, { PriorityBadge } from '../../components/Badge';
import MapView, { reportMarker } from '../../components/MapView';
import ResolutionImageLink from '../../components/ResolutionImageLink';
import { Alert, Field, Spinner } from '../../components/Ui';
import {
  IconCheck,
  IconImage,
  IconShield,
  IconSpark,
  IconWrench,
  IconX,
} from '../../components/Icons';
import { useToast } from '../../context/ToastContext';
import { coordinate, formatDateTime } from '../../lib/format';

const PRIORITIES = ['Low', 'Medium', 'High', 'Critical'];

/**
 * Report details, manual validation, priority recommendation and assignment.
 *
 * The map shows a single marker for the report location - no route is drawn.
 */
export default function ReportDetail() {
  const { reportId } = useParams();
  const navigate = useNavigate();
  const toast = useToast();

  const [report, setReport] = useState(null);
  const [imageUrl, setImageUrl] = useState('');
  const [imageError, setImageError] = useState('');
  const [teams, setTeams] = useState({ teams: [], members: [] });
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');

  const [validationNote, setValidationNote] = useState('');
  const [chosenPriority, setChosenPriority] = useState('');
  const [team, setTeam] = useState('');
  const [assignee, setAssignee] = useState('');
  const [assignNote, setAssignNote] = useState('');
  const [verifyNote, setVerifyNote] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await authorityApi.report(reportId);
      setReport(data);
      setChosenPriority(data.final_priority || data.predicted_priority || '');
      if (data.has_image) {
        reportApi
          .imageLink(data.report_id)
          .then((link) => setImageUrl(link.url))
          .catch((err) => setImageError(errorMessage(err, 'Evidence image unavailable.')));
      }
    } catch (err) {
      setError(errorMessage(err, 'Could not load this report.'));
    } finally {
      setLoading(false);
    }
  }, [reportId]);

  useEffect(() => {
    load();
    authorityApi
      .teams()
      .then((data) => {
        setTeams(data);
        setTeam((current) => current || data.teams[0] || '');
      })
      .catch(() => {});
  }, [load]);

  async function run(key, action, successMessage) {
    setBusy(key);
    try {
      const result = await action();
      if (successMessage) toast.success(successMessage);
      return result;
    } catch (err) {
      toast.error(errorMessage(err));
      return null;
    } finally {
      setBusy('');
    }
  }

  const validate = (validationStatus) =>
    run(
      `validate-${validationStatus}`,
      async () => {
        const updated = await authorityApi.validate(reportId, {
          validation_status: validationStatus,
          note: validationNote.trim() || null,
        });
        setReport(updated);
        setValidationNote('');
        return updated;
      },
      `Report marked ${validationStatus}.`,
    );

  const predict = () =>
    run('predict', async () => {
      const result = await authorityApi.predictPriority(reportId);
      setPrediction(result);
      setChosenPriority(result.predicted_priority);
      setReport((current) => ({
        ...current,
        predicted_priority: result.predicted_priority,
        prediction_confidence: result.confidence,
      }));
      return result;
    });

  const confirmPriority = () =>
    run(
      'confirm',
      async () => {
        const updated = await authorityApi.confirmPriority(reportId, {
          final_priority: chosenPriority,
        });
        setReport(updated);
        return updated;
      },
      `Priority confirmed as ${chosenPriority}.`,
    );

  const assign = () =>
    run(
      'assign',
      async () => {
        await authorityApi.assign(reportId, {
          assigned_team: team,
          assigned_to: assignee || null,
          note: assignNote.trim() || null,
        });
        setAssignNote('');
        await load();
      },
      `Assigned to ${team}.`,
    );

  const verify = (approved) =>
    run(
      `verify-${approved}`,
      async () => {
        await authorityApi.verify(report.task.task_id, {
          approved,
          notes: verifyNote.trim() || null,
        });
        setVerifyNote('');
        await load();
      },
      approved ? 'Resolution verified and the report is closed.' : 'Sent back for rework.',
    );

  if (loading) {
    return (
      <AuthorityShell title="Report Details">
        <Spinner label="Loading report" />
      </AuthorityShell>
    );
  }

  if (error || !report) {
    return (
      <AuthorityShell title="Report Details">
        <Alert tone="error">{error || 'Report not found.'}</Alert>
        <button
          type="button"
          className="btn btn-secondary mt-3"
          onClick={() => navigate('/authority/reports')}
        >
          Back to reports
        </button>
      </AuthorityShell>
    );
  }

  const canAssign =
    report.validation_status !== 'Invalid' &&
    (!report.task || ['Verified', 'Rejected'].includes(report.task.status));

  return (
    <AuthorityShell
      title={`Report ${report.report_id}`}
      subtitle={`${report.issue_type} · ${report.location_text || 'Location not provided'}`}
      actions={
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => navigate('/authority/reports')}
        >
          Back to reports
        </button>
      }
    >
      <div className="split-2">
        {/* --- Left column: the report itself --------------------------- */}
        <div className="stack">
          <div className="card">
            <div className="card-header">
              <div>
                <h2>Report Details</h2>
                <div className="card-title-sub">Submitted evidence and metadata</div>
              </div>
              <div className="row">
                <Badge value={report.validation_status} />
                <Badge value={report.status} dot />
              </div>
            </div>
            <div className="card-body">
              <dl className="detail-list">
                <div className="detail-row">
                  <dt>Report ID</dt>
                  <dd className="strong">{report.report_id}</dd>
                </div>
                <div className="detail-row">
                  <dt>User ID</dt>
                  <dd>
                    {report.user_id}
                    {report.reporter_name ? ` · ${report.reporter_name}` : ''}
                  </dd>
                </div>
                <div className="detail-row">
                  <dt>Issue type</dt>
                  <dd>{report.issue_type}</dd>
                </div>
                <div className="detail-row">
                  <dt>Location</dt>
                  <dd>{report.location_text || '—'}</dd>
                </div>
                <div className="detail-row">
                  <dt>Latitude</dt>
                  <dd className="mono">{coordinate(report.latitude)}</dd>
                </div>
                <div className="detail-row">
                  <dt>Longitude</dt>
                  <dd className="mono">{coordinate(report.longitude)}</dd>
                </div>
                <div className="detail-row">
                  <dt>Description</dt>
                  <dd>{report.description || '—'}</dd>
                </div>
                <div className="detail-row">
                  <dt>Severity</dt>
                  <dd>
                    <Badge value={report.severity} dot />
                  </dd>
                </div>
                <div className="detail-row">
                  <dt>Timestamp</dt>
                  <dd>{formatDateTime(report.timestamp)}</dd>
                </div>
                <div className="detail-row">
                  <dt>Source</dt>
                  <dd>{report.source || '—'}</dd>
                </div>
                <div className="detail-row">
                  <dt>Validation status</dt>
                  <dd>
                    <Badge value={report.validation_status} />
                    {report.validated_by && (
                      <div className="tiny muted mt-2">
                        by {report.validated_by} · {formatDateTime(report.validated_at)}
                      </div>
                    )}
                  </dd>
                </div>
                <div className="detail-row">
                  <dt>Status</dt>
                  <dd>
                    <Badge value={report.status} dot />
                  </dd>
                </div>
              </dl>
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <h2>Evidence Image</h2>
              <IconImage width={17} height={17} />
            </div>
            <div className="card-body">
              {imageUrl ? (
                <img
                  src={imageUrl}
                  alt={`Evidence submitted with report ${report.report_id}`}
                  className="evidence-image"
                  onError={() =>
                    setImageError('The linked image could not be loaded from its source.')
                  }
                />
              ) : (
                <p className="muted small">
                  {imageError || 'No evidence image was attached to this report.'}
                </p>
              )}
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <h2>Location</h2>
              <span className="tiny muted">Marker only — no route</span>
            </div>
            <div className="card-body">
              <MapView
                center={{ latitude: report.latitude, longitude: report.longitude }}
                zoom={17}
                height="map-height-md"
                showLegend={false}
                markers={[reportMarker(report)]}
              />
            </div>
          </div>
        </div>

        {/* --- Right column: authority actions -------------------------- */}
        <div className="stack">
          <div className="card">
            <div className="card-header">
              <h2>Manual Validation</h2>
              <IconShield width={17} height={17} />
            </div>
            <div className="card-body">
              <p className="small muted mb-3">
                Check the issue type, description, location, timestamp, severity and evidence
                before deciding.
              </p>
              <Field label="Reviewer note" htmlFor="validation-note" hint="Optional. Recorded in the audit log.">
                <textarea
                  id="validation-note"
                  className="textarea"
                  style={{ minHeight: 72 }}
                  value={validationNote}
                  onChange={(event) => setValidationNote(event.target.value)}
                  placeholder="What did you check?"
                />
              </Field>
              <div className="stack-sm">
                <button
                  type="button"
                  className="btn btn-success btn-block"
                  disabled={Boolean(busy)}
                  onClick={() => validate('Valid')}
                >
                  <IconCheck width={16} height={16} />
                  {busy === 'validate-Valid' ? 'Saving…' : 'Mark Valid'}
                </button>
                <button
                  type="button"
                  className="btn btn-danger btn-block"
                  disabled={Boolean(busy)}
                  onClick={() => validate('Invalid')}
                >
                  <IconX width={16} height={16} />
                  {busy === 'validate-Invalid' ? 'Saving…' : 'Mark Invalid'}
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-block"
                  disabled={Boolean(busy)}
                  onClick={() => validate('Needs Review')}
                >
                  {busy === 'validate-Needs Review' ? 'Saving…' : 'Needs Review'}
                </button>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <div>
                <h2>Priority</h2>
                <div className="card-title-sub">XGBoost recommendation, confirmed by you</div>
              </div>
              <IconSpark width={17} height={17} />
            </div>
            <div className="card-body">
              <div className="row-between mb-3">
                <span className="small muted">Current</span>
                <PriorityBadge
                  predicted={report.predicted_priority}
                  final={report.final_priority}
                />
              </div>

              <button
                type="button"
                className="btn btn-secondary btn-block mb-3"
                disabled={Boolean(busy)}
                onClick={predict}
              >
                {busy === 'predict' ? 'Analysing…' : 'Get priority recommendation'}
              </button>

              {prediction && (
                <div className="alert alert-info mb-3" style={{ display: 'block' }}>
                  <div className="strong">
                    Recommended: {prediction.predicted_priority} ·{' '}
                    {Math.round(prediction.confidence * 100)}% confidence
                  </div>
                  <div className="tiny mt-2">Model: {prediction.model}</div>
                  <ul className="tiny mt-2" style={{ margin: 0, paddingLeft: 16 }}>
                    {prediction.rationale.map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                </div>
              )}

              <Field label="Confirm final priority" htmlFor="priority-select">
                <select
                  id="priority-select"
                  className="select"
                  value={chosenPriority}
                  onChange={(event) => setChosenPriority(event.target.value)}
                >
                  <option value="">Choose a priority…</option>
                  {PRIORITIES.map((priority) => (
                    <option key={priority} value={priority}>
                      {priority}
                    </option>
                  ))}
                </select>
              </Field>

              <button
                type="button"
                className="btn btn-primary btn-block"
                disabled={!chosenPriority || Boolean(busy)}
                onClick={confirmPriority}
              >
                {busy === 'confirm' ? 'Saving…' : 'Confirm priority'}
              </button>

              {report.priority_confirmed_by && (
                <p className="tiny muted mt-2">
                  Confirmed by {report.priority_confirmed_by} ·{' '}
                  {formatDateTime(report.priority_confirmed_at)}
                </p>
              )}
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <h2>Maintenance</h2>
              <IconWrench width={17} height={17} />
            </div>
            <div className="card-body">
              {report.task && (
                <div className="alert alert-info mb-3" style={{ display: 'block' }}>
                  <div className="row-between">
                    <span className="strong">{report.task.task_id}</span>
                    <Badge value={report.task.status} dot />
                  </div>
                  <div className="tiny mt-2">
                    {report.task.assigned_team} · assigned{' '}
                    {formatDateTime(report.task.assigned_at)}
                  </div>
                  {report.task.maintenance_notes && (
                    <div className="tiny mt-2">Notes: {report.task.maintenance_notes}</div>
                  )}
                </div>
              )}

              {report.task?.status === 'Completed' && (
                <>
                  <p className="small strong mb-2">Verify the resolution</p>
                  {report.task.has_resolution_image && (
                    <div className="mb-2">
                      <ResolutionImageLink taskId={report.task.task_id} />
                    </div>
                  )}
                  <Field htmlFor="verify-note">
                    <textarea
                      id="verify-note"
                      className="textarea"
                      style={{ minHeight: 68 }}
                      value={verifyNote}
                      onChange={(event) => setVerifyNote(event.target.value)}
                      placeholder="Verification notes…"
                    />
                  </Field>
                  <div className="stack-sm">
                    <button
                      type="button"
                      className="btn btn-success btn-block"
                      disabled={Boolean(busy)}
                      onClick={() => verify(true)}
                    >
                      {busy === 'verify-true' ? 'Saving…' : 'Approve and close'}
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary btn-block"
                      disabled={Boolean(busy)}
                      onClick={() => verify(false)}
                    >
                      {busy === 'verify-false' ? 'Saving…' : 'Send back for rework'}
                    </button>
                  </div>
                </>
              )}

              {canAssign && (
                <>
                  {report.task && <hr style={{ border: 'none', borderTop: '1px solid var(--line)', margin: '16px 0' }} />}
                  <Field label="Assign to team" htmlFor="team-select">
                    <select
                      id="team-select"
                      className="select"
                      value={team}
                      onChange={(event) => setTeam(event.target.value)}
                    >
                      {teams.teams.map((name) => (
                        <option key={name} value={name}>
                          {name}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field
                    label="Assign to a person"
                    htmlFor="assignee-select"
                    hint="Optional. Leave blank to let the team pick it up."
                  >
                    <select
                      id="assignee-select"
                      className="select"
                      value={assignee}
                      onChange={(event) => setAssignee(event.target.value)}
                    >
                      <option value="">Whole team</option>
                      {teams.members.map((member) => (
                        <option key={member.user_id} value={member.user_id}>
                          {member.name} ({member.team || 'unassigned'})
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field htmlFor="assign-note">
                    <textarea
                      id="assign-note"
                      className="textarea"
                      style={{ minHeight: 68 }}
                      value={assignNote}
                      onChange={(event) => setAssignNote(event.target.value)}
                      placeholder="Instructions for the maintenance team…"
                    />
                  </Field>
                  <button
                    type="button"
                    className="btn btn-primary btn-block"
                    disabled={!team || Boolean(busy)}
                    onClick={assign}
                  >
                    {busy === 'assign' ? 'Assigning…' : 'Assign maintenance'}
                  </button>
                </>
              )}

              {report.validation_status === 'Invalid' && (
                <p className="small muted mt-2">
                  Invalid reports cannot be assigned for maintenance.
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </AuthorityShell>
  );
}
