import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { errorMessage } from '../../api/client';
import { reportApi, userApi } from '../../api/endpoints';
import MapView, { userMarker } from '../../components/MapView';
import UserShell from '../../components/UserShell';
import { Alert, Field, Spinner } from '../../components/Ui';
import {
  IconCamera,
  IconCheck,
  IconChevronRight,
  IconImage,
  IconPin,
  IconReport,
  IconX,
} from '../../components/Icons';
import { useToast } from '../../context/ToastContext';
import { DEFAULT_CENTER, getCurrentLocation } from '../../lib/geolocation';

const MAX_IMAGE_BYTES = 8 * 1024 * 1024;

/**
 * Two-step reporting flow.
 *
 * Step 1 - choose the issue type.
 * Step 2 - location (current or picked on the map), description, photo
 *          evidence from the camera or gallery, and severity.
 *
 * The report is posted as multipart/form-data so the photo travels with it;
 * the report id, user id and timestamp are all assigned server-side.
 */
export default function ReportIssue() {
  const navigate = useNavigate();
  const routeState = useLocation().state;
  const toast = useToast();

  const cameraInput = useRef(null);
  const galleryInput = useRef(null);

  const [step, setStep] = useState(1);
  const [issueTypes, setIssueTypes] = useState([]);
  const [issueType, setIssueType] = useState('');
  const [severity, setSeverity] = useState('Medium');
  const [description, setDescription] = useState('');
  const [locationText, setLocationText] = useState(routeState?.locationText || '');
  const [coords, setCoords] = useState(
    routeState?.latitude
      ? { latitude: routeState.latitude, longitude: routeState.longitude }
      : null,
  );
  const [locationMode, setLocationMode] = useState(routeState?.latitude ? 'map' : 'current');
  const [locating, setLocating] = useState(false);
  const [photo, setPhoto] = useState(null);
  const [preview, setPreview] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    reportApi
      .options()
      .then((data) => setIssueTypes(data.issue_types))
      .catch(() => setIssueTypes([]));
  }, []);

  useEffect(() => {
    if (coords || locationMode !== 'current') return;
    setLocating(true);
    getCurrentLocation()
      .then((position) => setCoords(position))
      .catch((err) => {
        toast.error(err.message);
        setLocationMode('map');
        setCoords(DEFAULT_CENTER);
      })
      .finally(() => setLocating(false));
  }, [coords, locationMode, toast]);

  useEffect(() => () => preview && URL.revokeObjectURL(preview), [preview]);

  function handlePhoto(event) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      toast.error('Choose an image file (JPEG, PNG, WEBP or HEIC).');
      return;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      toast.error('That image is larger than 8 MB. Choose a smaller one.');
      return;
    }
    if (preview) URL.revokeObjectURL(preview);
    setPhoto(file);
    setPreview(URL.createObjectURL(file));
  }

  function clearPhoto() {
    if (preview) URL.revokeObjectURL(preview);
    setPhoto(null);
    setPreview('');
  }

  async function useCurrentLocation() {
    setLocating(true);
    try {
      const position = await getCurrentLocation();
      setCoords(position);
      setLocationMode('current');
    } catch (err) {
      toast.error(err.message);
    } finally {
      setLocating(false);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');

    if (!coords) {
      setError('Set the location of the issue before submitting.');
      return;
    }
    if (!description.trim()) {
      setError('Describe what is blocking access so the authority can act on it.');
      return;
    }

    const form = new FormData();
    form.append('issue_type', issueType);
    form.append('latitude', String(coords.latitude));
    form.append('longitude', String(coords.longitude));
    form.append('severity', severity);
    form.append('description', description.trim());
    if (locationText.trim()) form.append('location_text', locationText.trim());
    // The timestamp is recorded automatically at the moment of submission.
    form.append('timestamp', new Date().toISOString());
    if (photo) form.append('photo', photo);

    setBusy(true);
    try {
      const created = await userApi.createReport(form);
      navigate('/report/submitted', { replace: true, state: { report: created } });
    } catch (err) {
      setError(errorMessage(err, 'Could not submit your report. Please try again.'));
    } finally {
      setBusy(false);
    }
  }

  // --- Step 1: issue type ---------------------------------------------------
  if (step === 1) {
    return (
      <UserShell title="Report an Issue" plainHeader narrow>
        <p className="small muted mb-3">
          What kind of accessibility barrier did you find?
        </p>

        {issueTypes.length === 0 ? (
          <Spinner label="Loading issue types" />
        ) : (
          <div className="choice-grid">
            {issueTypes.map((type) => (
              <button
                key={type}
                type="button"
                className={`choice ${issueType === type ? 'is-selected' : ''}`.trim()}
                aria-pressed={issueType === type}
                onClick={() => {
                  setIssueType(type);
                  setStep(2);
                }}
              >
                <span className="choice-icon">
                  <IconReport width={19} height={19} />
                </span>
                <span className="grow">{type}</span>
                <IconChevronRight width={17} height={17} />
              </button>
            ))}
          </div>
        )}
      </UserShell>
    );
  }

  // --- Step 2: details ------------------------------------------------------
  return (
    <UserShell title="Report Details" plainHeader narrow>
      <form onSubmit={handleSubmit} noValidate>
        <div className="card card-pad mb-3">
          <div className="row-between">
            <div>
              <div className="tiny muted">Issue type</div>
              <div className="strong">{issueType}</div>
            </div>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setStep(1)}>
              Change
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-3">
            <Alert tone="error">{error}</Alert>
          </div>
        )}

        {/* Location */}
        <div className="card mb-3">
          <div className="card-header">
            <h3>Location</h3>
          </div>
          <div className="card-body">
            <div className="segmented mb-3">
              <button
                type="button"
                className={locationMode === 'current' ? 'is-selected' : ''}
                onClick={useCurrentLocation}
              >
                Current Location
              </button>
              <button
                type="button"
                className={locationMode === 'map' ? 'is-selected' : ''}
                onClick={() => setLocationMode('map')}
              >
                Select on Map
              </button>
            </div>

            {locating && <Spinner label="Finding your location" />}

            <MapView
              center={coords || DEFAULT_CENTER}
              zoom={17}
              height="map-height-sm"
              showLegend={false}
              pickerHint={locationMode === 'map' ? 'Tap the map to place the pin' : undefined}
              markers={
                coords
                  ? [
                      {
                        id: 'picked',
                        kind: locationMode === 'map' ? 'selected' : 'user',
                        latitude: coords.latitude,
                        longitude: coords.longitude,
                        title: 'Issue location',
                      },
                    ]
                  : []
              }
              onMapClick={
                locationMode === 'map'
                  ? (point) => setCoords({ ...point, accuracy: null })
                  : undefined
              }
            />

            <p className="hint row" style={{ marginTop: 10 }}>
              <IconPin width={14} height={14} />
              {coords
                ? `${coords.latitude.toFixed(5)}, ${coords.longitude.toFixed(5)}`
                : 'No location selected yet'}
            </p>

            <Field label="Landmark or address" htmlFor="location-text" hint="Optional but helpful.">
              <input
                id="location-text"
                className="input"
                value={locationText}
                onChange={(event) => setLocationText(event.target.value)}
                placeholder="e.g. College Street, near the north gate"
              />
            </Field>
          </div>
        </div>

        {/* Description */}
        <div className="card mb-3">
          <div className="card-header">
            <h3>Description</h3>
          </div>
          <div className="card-body">
            <Field htmlFor="description" hint="What is blocked, and how does it affect access?">
              <textarea
                id="description"
                className="textarea"
                required
                maxLength={2000}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="Describe the barrier you found…"
              />
            </Field>
          </div>
        </div>

        {/* Photo evidence */}
        <div className="card mb-3">
          <div className="card-header">
            <h3>Photo Evidence</h3>
            <span className="tiny muted">Optional</span>
          </div>
          <div className="card-body">
            {preview ? (
              <div>
                <img
                  src={preview}
                  alt="Preview of the evidence you are about to submit"
                  className="evidence-image"
                />
                <button
                  type="button"
                  className="btn btn-secondary btn-sm btn-block mt-2"
                  onClick={clearPhoto}
                >
                  <IconX width={15} height={15} /> Remove photo
                </button>
              </div>
            ) : (
              <div className="row" style={{ gap: 10 }}>
                <button
                  type="button"
                  className="btn btn-secondary grow"
                  onClick={() => cameraInput.current?.click()}
                >
                  <IconCamera width={17} height={17} /> Camera
                </button>
                <button
                  type="button"
                  className="btn btn-secondary grow"
                  onClick={() => galleryInput.current?.click()}
                >
                  <IconImage width={17} height={17} /> Gallery
                </button>
              </div>
            )}

            <input
              ref={cameraInput}
              type="file"
              accept="image/*"
              capture="environment"
              hidden
              onChange={handlePhoto}
            />
            <input
              ref={galleryInput}
              type="file"
              accept="image/*"
              hidden
              onChange={handlePhoto}
            />
            <p className="hint">Stored securely in Amazon S3 and shared only with reviewers.</p>
          </div>
        </div>

        {/* Severity */}
        <div className="card mb-3">
          <div className="card-header">
            <h3>Severity</h3>
          </div>
          <div className="card-body">
            <div className="segmented severity" role="group" aria-label="Severity">
              {['Low', 'Medium', 'High'].map((level) => (
                <button
                  key={level}
                  type="button"
                  data-value={level}
                  aria-pressed={severity === level}
                  className={severity === level ? 'is-selected' : ''}
                  onClick={() => setSeverity(level)}
                >
                  {level}
                </button>
              ))}
            </div>
            <p className="hint">
              {severity === 'High'
                ? 'Access is completely blocked right now.'
                : severity === 'Medium'
                  ? 'Access is difficult but still possible.'
                  : 'A minor problem worth fixing.'}
            </p>
          </div>
        </div>

        <button type="submit" className="btn btn-primary btn-lg btn-block" disabled={busy}>
          {busy ? 'Submitting…' : (
            <>
              <IconCheck width={18} height={18} /> Submit report
            </>
          )}
        </button>
        <p className="tiny muted center mt-2">
          The submission time is recorded automatically.
        </p>
      </form>
    </UserShell>
  );
}
