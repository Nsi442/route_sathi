import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { errorMessage } from '../../api/client';
import { maintenanceApi, reportApi } from '../../api/endpoints';
import Badge, { PriorityBadge } from '../../components/Badge';
import MaintenanceShell from '../../components/MaintenanceShell';
import MapView, { reportMarker } from '../../components/MapView';
import ResolutionImageLink from '../../components/ResolutionImageLink';
import { Alert, Field, Spinner } from '../../components/Ui';
import {
  IconCamera,
  IconCheck,
  IconImage,
  IconUpload,
  IconWrench,
} from '../../components/Icons';
import { useToast } from '../../context/ToastContext';
import { coordinate, formatDateTime } from '../../lib/format';

const MAX_IMAGE_BYTES = 8 * 1024 * 1024;

/**
 * A single maintenance task: the reported problem, status updates, notes and
 * the resolution photo that must be uploaded before the task can be submitted
 * as completed.
 */
export default function TaskDetail() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const fileInput = useRef(null);

  const [task, setTask] = useState(null);
  const [reportImage, setReportImage] = useState('');
  const [notes, setNotes] = useState('');
  const [photo, setPhoto] = useState(null);
  const [preview, setPreview] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await maintenanceApi.task(taskId);
      setTask(data);
      setNotes(data.maintenance_notes || '');
      if (data.report?.has_image) {
        reportApi
          .imageLink(data.report_id)
          .then((link) => setReportImage(link.url))
          .catch(() => {});
      }
    } catch (err) {
      setError(errorMessage(err, 'Could not load this task.'));
    } finally {
      setLoading(false);
    }
  }, [taskId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => () => preview && URL.revokeObjectURL(preview), [preview]);

  function choosePhoto(event) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      toast.error('Choose an image file.');
      return;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      toast.error('That image is larger than 8 MB.');
      return;
    }
    if (preview) URL.revokeObjectURL(preview);
    setPhoto(file);
    setPreview(URL.createObjectURL(file));
  }

  async function run(key, action, message) {
    setBusy(key);
    try {
      await action();
      if (message) toast.success(message);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy('');
    }
  }

  const startWork = () =>
    run(
      'start',
      async () => {
        const updated = await maintenanceApi.setStatus(taskId, {
          status: 'In Progress',
          maintenance_notes: notes.trim() || null,
        });
        setTask(updated);
      },
      'Task marked as in progress.',
    );

  const saveNotes = () =>
    run(
      'notes',
      async () => {
        const updated = await maintenanceApi.setNotes(taskId, {
          maintenance_notes: notes,
        });
        setTask(updated);
      },
      'Notes saved.',
    );

  const uploadResolution = () =>
    run(
      'upload',
      async () => {
        const updated = await maintenanceApi.uploadResolution(taskId, photo, notes.trim());
        setTask(updated);
        if (preview) URL.revokeObjectURL(preview);
        setPhoto(null);
        setPreview('');
      },
      'Resolution photo uploaded.',
    );

  const submitCompletion = () =>
    run(
      'complete',
      async () => {
        const updated = await maintenanceApi.setStatus(taskId, {
          status: 'Completed',
          maintenance_notes: notes.trim() || null,
        });
        setTask(updated);
      },
      'Submitted for authority verification.',
    );

  if (loading) {
    return (
      <MaintenanceShell title="Task">
        <Spinner label="Loading task" />
      </MaintenanceShell>
    );
  }

  if (error || !task) {
    return (
      <MaintenanceShell title="Task">
        <Alert tone="error">{error || 'Task not found.'}</Alert>
        <button
          type="button"
          className="btn btn-secondary mt-3"
          onClick={() => navigate('/maintenance')}
        >
          Back to my tasks
        </button>
      </MaintenanceShell>
    );
  }

  const closed = task.status === 'Verified';
  const hasResolution = task.has_resolution_image;

  return (
    <MaintenanceShell
      title={`Task ${task.task_id}`}
      subtitle={`${task.report?.issue_type || 'Repair'} · ${
        task.report?.location_text || 'Location not provided'
      }`}
      actions={
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => navigate('/maintenance')}
        >
          Back to my tasks
        </button>
      }
    >
      <div className="split-2">
        {/* --- The reported problem ------------------------------------- */}
        <div className="stack">
          <div className="card">
            <div className="card-header">
              <div>
                <h2>Reported Problem</h2>
                <div className="card-title-sub">Report {task.report_id}</div>
              </div>
              <div className="row">
                <Badge value={task.report?.severity} dot />
                <PriorityBadge
                  predicted={task.report?.predicted_priority}
                  final={task.report?.final_priority}
                />
              </div>
            </div>
            <div className="card-body">
              <dl className="detail-list">
                <div className="detail-row">
                  <dt>Issue type</dt>
                  <dd className="strong">{task.report?.issue_type || '—'}</dd>
                </div>
                <div className="detail-row">
                  <dt>Description</dt>
                  <dd>{task.report?.description || '—'}</dd>
                </div>
                <div className="detail-row">
                  <dt>Location</dt>
                  <dd>
                    {task.report?.location_text || '—'}
                    {task.report && (
                      <div className="tiny muted mono">
                        {coordinate(task.report.latitude)}, {coordinate(task.report.longitude)}
                      </div>
                    )}
                  </dd>
                </div>
                <div className="detail-row">
                  <dt>Reported</dt>
                  <dd>{formatDateTime(task.report?.timestamp)}</dd>
                </div>
                <div className="detail-row">
                  <dt>Assigned to</dt>
                  <dd>
                    {task.assigned_team}
                    {task.assigned_to ? ` · ${task.assigned_to}` : ' (unclaimed)'}
                  </dd>
                </div>
                <div className="detail-row">
                  <dt>Assigned at</dt>
                  <dd>{formatDateTime(task.assigned_at)}</dd>
                </div>
              </dl>
            </div>
          </div>

          {reportImage && (
            <div className="card">
              <div className="card-header">
                <h2>Citizen Evidence</h2>
                <IconImage width={17} height={17} />
              </div>
              <div className="card-body">
                <img
                  src={reportImage}
                  alt={`Evidence submitted with report ${task.report_id}`}
                  className="evidence-image"
                />
              </div>
            </div>
          )}

          {task.report && (
            <div className="card">
              <div className="card-header">
                <h2>Site Location</h2>
              </div>
              <div className="card-body">
                <MapView
                  center={{
                    latitude: task.report.latitude,
                    longitude: task.report.longitude,
                  }}
                  zoom={17}
                  height="map-height-md"
                  showLegend={false}
                  markers={[reportMarker(task.report)]}
                />
              </div>
            </div>
          )}
        </div>

        {/* --- Work actions -------------------------------------------- */}
        <div className="stack">
          <div className="card">
            <div className="card-header">
              <h2>Task Status</h2>
              <Badge value={task.status} dot />
            </div>
            <div className="card-body">
              {closed ? (
                <Alert tone="success">
                  This task was verified by {task.verified_by} on{' '}
                  {formatDateTime(task.verified_at)} and is now closed.
                </Alert>
              ) : task.status === 'Completed' ? (
                <Alert tone="info">
                  Submitted on {formatDateTime(task.completed_at)}. Waiting for an authority
                  reviewer to verify the repair.
                </Alert>
              ) : (
                <>
                  {task.verification_notes && (
                    <div className="mb-3">
                      <Alert tone="warn">
                        Sent back by the authority: {task.verification_notes}
                      </Alert>
                    </div>
                  )}
                  {task.status === 'Assigned' && (
                    <button
                      type="button"
                      className="btn btn-primary btn-block mb-3"
                      disabled={Boolean(busy)}
                      onClick={startWork}
                    >
                      <IconWrench width={16} height={16} />
                      {busy === 'start' ? 'Saving…' : 'Start work on this task'}
                    </button>
                  )}
                </>
              )}
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <h2>Maintenance Notes</h2>
            </div>
            <div className="card-body">
              <Field htmlFor="maintenance-notes" hint="Visible to the authority reviewer.">
                <textarea
                  id="maintenance-notes"
                  className="textarea"
                  value={notes}
                  disabled={closed}
                  maxLength={2000}
                  onChange={(event) => setNotes(event.target.value)}
                  placeholder="What was found on site and what work was done…"
                />
              </Field>
              <button
                type="button"
                className="btn btn-secondary btn-block"
                disabled={closed || Boolean(busy)}
                onClick={saveNotes}
              >
                {busy === 'notes' ? 'Saving…' : 'Save notes'}
              </button>
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <div>
                <h2>Resolution Photo</h2>
                <div className="card-title-sub">Required before completion</div>
              </div>
              <IconCamera width={17} height={17} />
            </div>
            <div className="card-body">
              {hasResolution && (
                <div className="mb-3">
                  <ResolutionImageLink
                    taskId={task.task_id}
                    label="Load the uploaded photo"
                    inline
                  />
                </div>
              )}

              {!closed && (
                <>
                  {preview && (
                    <img
                      src={preview}
                      alt="Preview of the resolution photo"
                      className="mb-3"
                  className="evidence-image"
                    />
                  )}

                  <button
                    type="button"
                    className="btn btn-secondary btn-block mb-2"
                    onClick={() => fileInput.current?.click()}
                  >
                    <IconCamera width={16} height={16} />
                    {hasResolution ? 'Replace the photo' : 'Choose a photo'}
                  </button>
                  <input
                    ref={fileInput}
                    type="file"
                    accept="image/*"
                    capture="environment"
                    hidden
                    onChange={choosePhoto}
                  />

                  <button
                    type="button"
                    className="btn btn-primary btn-block"
                    disabled={!photo || Boolean(busy)}
                    onClick={uploadResolution}
                  >
                    <IconUpload width={16} height={16} />
                    {busy === 'upload' ? 'Uploading…' : 'Upload resolution photo'}
                  </button>
                  <p className="hint">
                    Stored in Amazon S3 as evidence that the barrier was cleared.
                  </p>
                </>
              )}
            </div>
          </div>

          {!closed && task.status !== 'Completed' && (
            <div className="card">
              <div className="card-header">
                <h2>Submit for Verification</h2>
              </div>
              <div className="card-body">
                <p className="small muted mb-3">
                  Once submitted, an authority reviewer checks the photo and notes before the
                  citizen&apos;s report is marked resolved.
                </p>
                <button
                  type="button"
                  className="btn btn-success btn-block"
                  disabled={!hasResolution || Boolean(busy)}
                  onClick={submitCompletion}
                >
                  <IconCheck width={16} height={16} />
                  {busy === 'complete' ? 'Submitting…' : 'Submit as completed'}
                </button>
                {!hasResolution && (
                  <p className="hint">Upload a resolution photo to enable this.</p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </MaintenanceShell>
  );
}
