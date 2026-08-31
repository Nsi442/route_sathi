import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { errorMessage } from '../../api/client';
import { facilityApi, reportApi } from '../../api/endpoints';
import MapView, { facilityMarker, reportMarker, userMarker } from '../../components/MapView';
import UserShell from '../../components/UserShell';
import { Alert } from '../../components/Ui';
import { useToast } from '../../context/ToastContext';
import { DEFAULT_CENTER, getCurrentLocation } from '../../lib/geolocation';

const FACILITY_FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'Ramp', label: 'Ramps' },
  { key: 'Entrance', label: 'Entrances' },
  { key: 'Toilet', label: 'Toilets' },
  { key: 'Parking', label: 'Parking' },
  { key: 'Crossing', label: 'Crossings' },
  { key: 'Pathway', label: 'Pathways' },
];

/**
 * Full-screen accessibility map.
 *
 * Shows the user's position, accessible facilities and open issue reports.
 * No routes are drawn - discovery and visualisation only.
 */
export default function AccessibilityMap() {
  const navigate = useNavigate();
  const toast = useToast();
  const [params, setParams] = useSearchParams();

  const [center, setCenter] = useState(null);
  const [location, setLocation] = useState(null);
  const [facilities, setFacilities] = useState([]);
  const [reports, setReports] = useState([]);
  const [radius, setRadius] = useState(1500);
  const [error, setError] = useState('');

  const typeFilter = params.get('type') || 'all';
  const showIssues = params.get('layer') !== 'facilities';

  const locate = useCallback(async ({ silent = false } = {}) => {
    try {
      const coords = await getCurrentLocation();
      setLocation(coords);
      setCenter(coords);
      return coords;
    } catch (err) {
      if (!silent) toast.error(err.message);
      setCenter((current) => current || DEFAULT_CENTER);
      return null;
    }
  }, [toast]);

  useEffect(() => {
    locate({ silent: true });
  }, [locate]);

  useEffect(() => {
    if (!center) return;
    let active = true;
    setError('');

    const facilityRequest = facilityApi.nearby({
      latitude: center.latitude,
      longitude: center.longitude,
      radius,
      type: typeFilter === 'all' ? undefined : typeFilter,
      limit: 200,
    });

    const reportRequest = showIssues
      ? reportApi.mapPins({
          latitude: center.latitude,
          longitude: center.longitude,
          radius,
          only_open: true,
          limit: 200,
        })
      : Promise.resolve([]);

    Promise.all([facilityRequest, reportRequest])
      .then(([facilityData, reportData]) => {
        if (!active) return;
        setFacilities(facilityData);
        setReports(reportData);
      })
      .catch((err) => {
        if (active) setError(errorMessage(err, 'Could not load the map data.'));
      });

    return () => {
      active = false;
    };
  }, [center, radius, typeFilter, showIssues]);

  const markers = useMemo(() => {
    const items = [
      ...facilities.map((facility) => facilityMarker(facility, { onView: true })),
      ...reports.map((report) => reportMarker(report, { onView: true })),
    ];
    if (location) items.push(userMarker(location));
    return items;
  }, [facilities, reports, location]);

  function setType(nextType) {
    const next = new URLSearchParams(params);
    if (nextType === 'all') next.delete('type');
    else next.set('type', nextType);
    setParams(next, { replace: true });
  }

  function toggleIssues() {
    const next = new URLSearchParams(params);
    if (showIssues) next.set('layer', 'facilities');
    else next.delete('layer');
    setParams(next, { replace: true });
  }

  function handleMarkerAction(marker) {
    if (marker.kind === 'facility') navigate(`/facility/${marker.id}`);
    else if (marker.kind === 'report') navigate(`/my-reports/${marker.id}`);
  }

  return (
    <UserShell title="Accessibility Map" flush plainHeader back>
      <div className="filter-chips" role="group" aria-label="Filter facilities by category">
        {FACILITY_FILTERS.map((filter) => (
          <button
            key={filter.key}
            type="button"
            className={`chip ${typeFilter === filter.key ? 'is-active' : ''}`.trim()}
            aria-pressed={typeFilter === filter.key}
            onClick={() => setType(filter.key)}
          >
            {filter.label}
          </button>
        ))}
        <button
          type="button"
          className={`chip ${showIssues ? 'is-active' : ''}`.trim()}
          aria-pressed={showIssues}
          onClick={toggleIssues}
          style={showIssues ? { background: 'var(--red-700)', borderColor: 'var(--red-700)' } : undefined}
        >
          Issues
        </button>
      </div>

      <div className="radius-control">
        <label htmlFor="radius" className="strong" style={{ whiteSpace: 'nowrap' }}>
          Radius
        </label>
        <input
          id="radius"
          type="range"
          min={200}
          max={5000}
          step={100}
          value={radius}
          onChange={(event) => setRadius(Number(event.target.value))}
        />
        <span className="strong" style={{ minWidth: 62, textAlign: 'right' }}>
          {radius >= 1000 ? `${(radius / 1000).toFixed(1)} km` : `${radius} m`}
        </span>
      </div>

      {error && (
        <div style={{ padding: '12px 16px' }}>
          <Alert tone="error">{error}</Alert>
        </div>
      )}

      <MapView
        center={center}
        zoom={15}
        markers={markers}
        full
        onMarkerAction={handleMarkerAction}
        onLocate={() => locate()}
      />

      <div style={{ padding: '12px 16px' }} className="row-between small muted">
        <span>
          <strong>{facilities.length}</strong> facilities
          {showIssues && (
            <>
              {' · '}
              <strong>{reports.length}</strong> open issues
            </>
          )}
        </span>
        <span className="tiny">Tap a marker for details</span>
      </div>
    </UserShell>
  );
}
