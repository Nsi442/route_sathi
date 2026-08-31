import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { errorMessage } from '../../api/client';
import { userApi } from '../../api/endpoints';
import Badge from '../../components/Badge';
import UserShell from '../../components/UserShell';
import { Alert, SearchInput, Spinner } from '../../components/Ui';
import {
  IconDoor,
  IconList,
  IconMap,
  IconNear,
  IconPin,
  IconRamp,
  IconReport,
  IconToilet,
} from '../../components/Icons';
import { useAuth } from '../../context/AuthContext';
import { getCurrentLocation } from '../../lib/geolocation';
import { timeAgo } from '../../lib/format';

/**
 * Citizen home screen.
 *
 * Every number on this screen comes from `GET /api/user/home`, which counts
 * rows in PostgreSQL within the requested radius - nothing is hard-coded.
 */
export default function Home() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [summary, setSummary] = useState(null);
  const [location, setLocation] = useState(null);
  const [locationError, setLocationError] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');

  const load = useCallback(async (coords) => {
    setLoading(true);
    setError('');
    try {
      const data = await userApi.home(
        coords
          ? { latitude: coords.latitude, longitude: coords.longitude, radius: 1000 }
          : undefined,
      );
      setSummary(data);
    } catch (err) {
      setError(errorMessage(err, 'Could not load your home screen.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    getCurrentLocation()
      .then((coords) => {
        if (!active) return;
        setLocation(coords);
        load(coords);
      })
      .catch((err) => {
        if (!active) return;
        setLocationError(err.message);
        load(null);
      });
    return () => {
      active = false;
    };
  }, [load]);

  function handleSearch(event) {
    event.preventDefault();
    navigate(`/nearby?q=${encodeURIComponent(query.trim())}`);
  }

  return (
    <UserShell title="RouteSathi">
      <section className="home-hero">
        <div className="greeting">Hi, {user?.name?.split(' ')[0] || 'there'}</div>
        <div className="location">
          <IconPin width={15} height={15} />
          {location
            ? `${location.latitude.toFixed(4)}, ${location.longitude.toFixed(4)}${
                location.accuracy ? ` · ±${Math.round(location.accuracy)} m` : ''
              }`
            : locationError
              ? 'Location unavailable'
              : 'Finding your location…'}
        </div>
        <form className="mt-3" onSubmit={handleSearch}>
          <SearchInput
            value={query}
            onChange={setQuery}
            placeholder="Search accessibility near you…"
            aria-label="Search accessibility near you"
          />
        </form>
      </section>

      {locationError && (
        <div className="mb-3">
          <Alert tone="warn">{locationError} Showing city-wide counts instead.</Alert>
        </div>
      )}
      {error && (
        <div className="mb-3">
          <Alert tone="error">{error}</Alert>
        </div>
      )}

      <div className="quick-grid">
        <Link className="quick-tile" to="/map">
          <span className="quick-icon">
            <IconMap />
          </span>
          Accessibility Map
          <span className="quick-sub">See what is around you</span>
        </Link>
        <Link className="quick-tile" to="/nearby">
          <span className="quick-icon">
            <IconNear />
          </span>
          Nearby Facilities
          <span className="quick-sub">Search by category</span>
        </Link>
        <Link className="quick-tile" to="/report">
          <span className="quick-icon">
            <IconReport />
          </span>
          Report Issue
          <span className="quick-sub">Photo, place, severity</span>
        </Link>
        <Link className="quick-tile" to="/my-reports">
          <span className="quick-icon">
            <IconList />
          </span>
          My Reports
          <span className="quick-sub">
            {summary ? `${summary.my_reports} submitted` : 'Track your reports'}
          </span>
        </Link>
      </div>

      <div className="section-title">
        <h2>Accessibility Around You</h2>
        <span className="tiny muted">
          {location ? 'Within 1 km' : 'City-wide'}
        </span>
      </div>

      {loading ? (
        <Spinner label="Loading nearby accessibility" />
      ) : (
        <div className="around-grid">
          <AroundTile
            icon={<IconRamp width={17} height={17} />}
            count={summary?.ramps ?? 0}
            label="Ramps"
            to="/nearby?type=Ramp"
          />
          <AroundTile
            icon={<IconDoor width={17} height={17} />}
            count={summary?.entrances ?? 0}
            label="Entrances"
            to="/nearby?type=Entrance"
          />
          <AroundTile
            icon={<IconToilet width={17} height={17} />}
            count={summary?.toilets ?? 0}
            label="Toilets"
            to="/nearby?type=Toilet"
          />
          <AroundTile
            icon={<IconReport width={17} height={17} />}
            count={summary?.issues ?? 0}
            label="Issues"
            to="/map?layer=issues"
            issues
          />
        </div>
      )}

      <div className="section-title">
        <h2>Latest Updates</h2>
        <Link to="/my-reports" className="tiny">
          View all
        </Link>
      </div>

      <div className="stack is-responsive-grid">
        {loading && <Spinner label="Loading updates" />}
        {!loading && !summary?.latest_updates?.length && (
          <div className="card card-pad muted small center">
            No accessibility updates have been published yet.
          </div>
        )}
        {summary?.latest_updates?.map((item) => (
          <div className="list-row" key={item.report_id} style={{ cursor: 'default' }}>
            <span className="row-icon">
              <IconReport width={18} height={18} />
            </span>
            <div className="grow">
              <div className="row-title">{item.issue_type}</div>
              <div className="row-meta truncate">
                {item.location_text || 'Location not provided'} · {timeAgo(item.timestamp)}
              </div>
            </div>
            <div className="row-end">
              <Badge value={item.status} dot />
            </div>
          </div>
        ))}
      </div>
    </UserShell>
  );
}

function AroundTile({ icon, count, label, to, issues = false }) {
  return (
    <Link to={to} className={`around-tile ${issues ? 'is-issues' : ''}`.trim()}>
      <span style={{ color: issues ? 'var(--red-700)' : 'var(--teal-700)' }}>{icon}</span>
      <span className="count">{count}</span>
      <span className="label">{label}</span>
    </Link>
  );
}
