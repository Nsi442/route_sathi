import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { errorMessage } from '../../api/client';
import { facilityApi, reportApi } from '../../api/endpoints';
import MapView, { facilityMarker, reportMarker, userMarker } from '../../components/MapView';
import UserShell from '../../components/UserShell';
import { Alert } from '../../components/Ui';
import { IconChevronLeft, IconSearch, IconX } from '../../components/Icons';
import { useToast } from '../../context/ToastContext';
import { DEFAULT_CENTER, getCurrentLocation } from '../../lib/geolocation';

const FACILITY_TYPES = ['Ramp', 'Entrance', 'Toilet', 'Parking', 'Crossing', 'Pathway'];

/** Plural labels, because "Parkings" is not a word. */
const TYPE_LABELS = {
  Ramp: 'Ramps',
  Entrance: 'Entrances',
  Toilet: 'Toilets',
  Parking: 'Parking',
  Crossing: 'Crossings',
  Pathway: 'Pathways',
};

/** Facility statuses, with the marker colour each one maps to. */
const STATUSES = [
  { key: 'Verified', label: 'Verified', colour: '#15803d' },
  { key: 'Available', label: 'Available', colour: '#15803d' },
  { key: 'Under Review', label: 'Under Review', colour: '#d97706' },
  { key: 'Blocked', label: 'Blocked', colour: '#dc2626' },
];

const DEFAULT_FILTERS = {
  types: [...FACILITY_TYPES],
  statuses: STATUSES.map((s) => s.key),
  issues: true,
  radius: 1500,
};

/**
 * Full-screen accessibility map.
 *
 * Shows what is accessible around the user's current location, filtered by
 * facility category and status. Facilities the authority has confirmed as
 * unusable show red; once a repair is verified they turn green, so the map
 * reflects the current state of the street rather than a static survey.
 *
 * Markers only - this MVP has no routing engine, so no path is ever drawn.
 */
export default function AccessibilityMap() {
  const navigate = useNavigate();
  const toast = useToast();
  const [params] = useSearchParams();

  const [center, setCenter] = useState(null);
  const [location, setLocation] = useState(null);
  const [facilities, setFacilities] = useState([]);
  const [reports, setReports] = useState([]);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [sheetOpen, setSheetOpen] = useState(false);

  // `filters` is what the map is showing; `draft` is what the sheet is
  // editing. They only converge when the user taps Apply.
  const [filters, setFilters] = useState(() => {
    const type = params.get('type');
    return {
      ...DEFAULT_FILTERS,
      types: type && FACILITY_TYPES.includes(type) ? [type] : DEFAULT_FILTERS.types,
      issues: params.get('layer') !== 'facilities',
    };
  });
  const [draft, setDraft] = useState(filters);

  const locate = useCallback(
    async ({ silent = false } = {}) => {
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
    },
    [toast],
  );

  useEffect(() => {
    locate({ silent: true });
  }, [locate]);

  // Everything within the radius is fetched once, then filtered in the
  // browser, so toggling a category is instant instead of a round trip.
  useEffect(() => {
    if (!center) return undefined;
    let active = true;
    setError('');

    Promise.all([
      facilityApi.nearby({
        latitude: center.latitude,
        longitude: center.longitude,
        radius: filters.radius,
        limit: 300,
      }),
      filters.issues
        ? reportApi.mapPins({
            latitude: center.latitude,
            longitude: center.longitude,
            radius: filters.radius,
            only_open: true,
            limit: 300,
          })
        : Promise.resolve([]),
    ])
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
  }, [center, filters.radius, filters.issues]);

  const visibleFacilities = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return facilities.filter((f) => {
      if (!filters.types.includes(f.type)) return false;
      if (!filters.statuses.includes(f.status)) return false;
      if (needle && !`${f.name} ${f.type} ${f.address || ''}`.toLowerCase().includes(needle)) {
        return false;
      }
      return true;
    });
  }, [facilities, filters.types, filters.statuses, query]);

  const visibleReports = useMemo(() => {
    if (!filters.issues) return [];
    const needle = query.trim().toLowerCase();
    if (!needle) return reports;
    return reports.filter((r) =>
      `${r.issue_type} ${r.report_id}`.toLowerCase().includes(needle),
    );
  }, [reports, filters.issues, query]);

  const markers = useMemo(() => {
    const items = [
      ...visibleFacilities.map((f) => facilityMarker(f, { onView: true })),
      ...visibleReports.map((r) => reportMarker(r, { onView: true })),
    ];
    if (location) items.push(userMarker(location));
    return items;
  }, [visibleFacilities, visibleReports, location]);

  const activeFilterCount =
    (FACILITY_TYPES.length - filters.types.length) +
    (STATUSES.length - filters.statuses.length) +
    (filters.issues ? 0 : 1);

  function openSheet() {
    setDraft(filters);
    setSheetOpen(true);
  }

  function toggleDraft(key, value) {
    setDraft((current) => {
      const list = current[key];
      return {
        ...current,
        [key]: list.includes(value)
          ? list.filter((item) => item !== value)
          : [...list, value],
      };
    });
  }

  function handleMarkerAction(marker) {
    if (marker.kind === 'facility') navigate(`/facility/${marker.id}`);
    else if (marker.kind === 'report') navigate(`/my-reports/${marker.id}`);
  }

  return (
    <UserShell title="Accessibility Map" flush plainHeader hideHeader>
      <div className="map-screen">
        <MapView
          center={center}
          zoom={15}
          markers={markers}
          full
          showLegend
          onMarkerAction={handleMarkerAction}
          onLocate={() => locate()}
        />

        <div className="map-overlay-header">
          <button
            type="button"
            className="map-round-btn"
            onClick={() => navigate(-1)}
            aria-label="Go back"
          >
            <IconChevronLeft />
          </button>

          <div className="map-search">
            <IconSearch width={17} height={17} />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search map…"
              aria-label="Search places on the map"
            />
          </div>

          <button
            type="button"
            className={`map-round-btn ${sheetOpen ? 'is-active' : ''}`.trim()}
            style={{ position: 'relative' }}
            onClick={openSheet}
            aria-label="Filter accessibility"
            aria-expanded={sheetOpen}
          >
            <FunnelIcon />
            {activeFilterCount > 0 && (
              <span className="filter-count">{activeFilterCount}</span>
            )}
          </button>
        </div>

        <div className="map-result-pill">
          {visibleFacilities.length} accessible
          {filters.issues && ` · ${visibleReports.length} issue${visibleReports.length === 1 ? '' : 's'}`}
          {' · '}
          {filters.radius >= 1000
            ? `${(filters.radius / 1000).toFixed(1)} km`
            : `${filters.radius} m`}
        </div>

        {error && (
          <div style={{ position: 'absolute', bottom: 16, left: 16, right: 16, zIndex: 600 }}>
            <Alert tone="error">{error}</Alert>
          </div>
        )}

        {sheetOpen && (
          <>
            <div
              className="sheet-backdrop"
              role="presentation"
              onClick={() => setSheetOpen(false)}
            />
            <div
              className="filter-sheet"
              role="dialog"
              aria-modal="true"
              aria-label="Filter accessibility"
            >
              <div className="sheet-grabber" />
              <div className="sheet-header">
                <h2>Filter Accessibility</h2>
                <button
                  type="button"
                  className="sheet-close"
                  onClick={() => setSheetOpen(false)}
                  aria-label="Close filters"
                >
                  <IconX width={19} height={19} />
                </button>
              </div>

              <div className="sheet-label">Facility Types</div>
              <div className="sheet-chips">
                {FACILITY_TYPES.map((type) => (
                  <button
                    key={type}
                    type="button"
                    className={`sheet-chip ${draft.types.includes(type) ? 'is-on' : ''}`.trim()}
                    aria-pressed={draft.types.includes(type)}
                    onClick={() => toggleDraft('types', type)}
                  >
                    {TYPE_LABELS[type]}
                  </button>
                ))}
              </div>

              <div className="sheet-label">Status</div>
              <div className="sheet-checks">
                {STATUSES.map((status) => (
                  <label className="sheet-check" key={status.key}>
                    <input
                      type="checkbox"
                      checked={draft.statuses.includes(status.key)}
                      onChange={() => toggleDraft('statuses', status.key)}
                    />
                    <span className="swatch" style={{ background: status.colour }} />
                    {status.label}
                  </label>
                ))}
              </div>

              <div className="sheet-label">Reported Issues</div>
              <div className="sheet-checks">
                <label className="sheet-check">
                  <input
                    type="checkbox"
                    checked={draft.issues}
                    onChange={() =>
                      setDraft((current) => ({ ...current, issues: !current.issues }))
                    }
                  />
                  <span className="swatch" style={{ background: '#dc2626' }} />
                  Show open accessibility issues
                </label>
              </div>

              <div className="sheet-label">Search Radius</div>
              <div className="sheet-radius">
                <input
                  type="range"
                  min={200}
                  max={5000}
                  step={100}
                  value={draft.radius}
                  aria-label="Search radius in metres"
                  onChange={(event) =>
                    setDraft((current) => ({
                      ...current,
                      radius: Number(event.target.value),
                    }))
                  }
                />
                <span className="value">
                  {draft.radius >= 1000
                    ? `${(draft.radius / 1000).toFixed(1)} km`
                    : `${draft.radius} m`}
                </span>
              </div>

              <button
                type="button"
                className="sheet-apply"
                onClick={() => {
                  setFilters(draft);
                  setSheetOpen(false);
                }}
              >
                Apply Filters
              </button>
              <button
                type="button"
                className="sheet-reset"
                onClick={() => setDraft(DEFAULT_FILTERS)}
              >
                Reset to all
              </button>
            </div>
          </>
        )}
      </div>
    </UserShell>
  );
}

function FunnelIcon() {
  return (
    <svg
      width="19"
      height="19"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M3 4h18l-7 8v6l-4 2v-8z" />
    </svg>
  );
}
