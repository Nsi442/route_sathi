import { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { errorMessage } from '../../api/client';
import { facilityApi } from '../../api/endpoints';
import Badge from '../../components/Badge';
import UserShell from '../../components/UserShell';
import { Alert, EmptyState, SearchInput, Spinner } from '../../components/Ui';
import { facilityIcon, IconNear } from '../../components/Icons';
import { DEFAULT_CENTER, formatDistance, getCurrentLocation } from '../../lib/geolocation';

const CATEGORIES = ['Ramp', 'Entrance', 'Toilet', 'Parking', 'Crossing', 'Pathway', 'Other'];
const RADII = [100, 300, 500, 1000, 2000, 5000];

/**
 * Nearby facility search.
 *
 * Sends `GET /api/facilities/nearby?latitude=&longitude=&radius=&type=`, which
 * runs a PostGIS radius query and returns results ordered nearest-first with a
 * straight-line distance in metres.
 */
export default function Nearby() {
  const [params, setParams] = useSearchParams();
  const [location, setLocation] = useState(null);
  const [locationError, setLocationError] = useState('');
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState(params.get('q') || '');

  const type = params.get('type') || '';
  const radius = Number(params.get('radius') || 300);

  useEffect(() => {
    let active = true;
    getCurrentLocation()
      .then((coords) => active && setLocation(coords))
      .catch((err) => {
        if (!active) return;
        setLocationError(err.message);
        setLocation(DEFAULT_CENTER);
      });
    return () => {
      active = false;
    };
  }, []);

  const search = useCallback(async () => {
    if (!location) return;
    setLoading(true);
    setError('');
    try {
      const data = await facilityApi.nearby({
        latitude: location.latitude,
        longitude: location.longitude,
        radius,
        type: type || undefined,
        limit: 100,
      });
      setItems(data);
    } catch (err) {
      setError(errorMessage(err, 'Could not search for nearby facilities.'));
    } finally {
      setLoading(false);
    }
  }, [location, radius, type]);

  useEffect(() => {
    search();
  }, [search]);

  function update(key, value) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  }

  const visible = query.trim()
    ? items.filter((item) =>
        `${item.name} ${item.type} ${item.address || ''}`
          .toLowerCase()
          .includes(query.trim().toLowerCase()),
      )
    : items;

  return (
    <UserShell title="Nearby Facilities" back plainHeader>
      <div className="mb-3">
        <SearchInput
          value={query}
          onChange={setQuery}
          placeholder="Filter these results…"
          aria-label="Filter nearby facilities"
        />
      </div>

      <div className="card card-pad mb-3">
        <div className="label">Facility type</div>
        <div className="filter-chips" style={{ padding: 0, border: 'none', background: 'none' }}>
          <button
            type="button"
            className={`chip ${!type ? 'is-active' : ''}`.trim()}
            onClick={() => update('type', '')}
            aria-pressed={!type}
          >
            All
          </button>
          {CATEGORIES.map((category) => (
            <button
              key={category}
              type="button"
              className={`chip ${type === category ? 'is-active' : ''}`.trim()}
              onClick={() => update('type', category)}
              aria-pressed={type === category}
            >
              {category}
            </button>
          ))}
        </div>

        <div className="label mt-3">Search radius</div>
        <div className="filter-chips" style={{ padding: 0, border: 'none', background: 'none' }}>
          {RADII.map((value) => (
            <button
              key={value}
              type="button"
              className={`chip ${radius === value ? 'is-active' : ''}`.trim()}
              onClick={() => update('radius', String(value))}
              aria-pressed={radius === value}
            >
              {value >= 1000 ? `${value / 1000} km` : `${value} m`}
            </button>
          ))}
        </div>
      </div>

      {locationError && (
        <div className="mb-3">
          <Alert tone="warn">{locationError} Searching around central Kolkata instead.</Alert>
        </div>
      )}
      {error && (
        <div className="mb-3">
          <Alert tone="error">{error}</Alert>
        </div>
      )}

      {loading ? (
        <Spinner label="Searching nearby" />
      ) : visible.length === 0 ? (
        <EmptyState
          icon={<IconNear />}
          title="Nothing found in this radius"
          description={`No ${type ? type.toLowerCase() : 'accessible'} facilities within ${
            radius >= 1000 ? `${radius / 1000} km` : `${radius} m`
          }. Try widening the search.`}
        />
      ) : (
        <>
          <p className="small muted mb-2">
            {visible.length} facilit{visible.length === 1 ? 'y' : 'ies'} · nearest first
          </p>
          <div className="stack is-responsive-grid">
            {visible.map((facility) => (
              <Link
                key={facility.facility_id}
                to={`/facility/${facility.facility_id}`}
                className="list-row"
              >
                <span className="row-icon">
                  {facilityIcon(facility.type, { width: 19, height: 19 })}
                </span>
                <div className="grow">
                  <div className="row-title">{facility.name}</div>
                  <div className="row-meta truncate">
                    {facility.type}
                    {facility.address ? ` · ${facility.address}` : ''}
                  </div>
                </div>
                <div className="row-end">
                  <span className="distance-chip">{formatDistance(facility.distance)}</span>
                  <Badge value={facility.status} />
                </div>
              </Link>
            ))}
          </div>
        </>
      )}
    </UserShell>
  );
}
