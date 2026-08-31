import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { errorMessage } from '../../api/client';
import { facilityApi } from '../../api/endpoints';
import Badge from '../../components/Badge';
import MapView, { facilityMarker, userMarker } from '../../components/MapView';
import UserShell from '../../components/UserShell';
import { Alert, Spinner } from '../../components/Ui';
import { facilityIcon } from '../../components/Icons';
import { formatDateTime } from '../../lib/format';
import { formatDistance, getCurrentLocation } from '../../lib/geolocation';
import { haversine } from '../../lib/distance';

export default function FacilityDetail() {
  const { facilityId } = useParams();
  const navigate = useNavigate();

  const [facility, setFacility] = useState(null);
  const [location, setLocation] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    facilityApi
      .detail(facilityId)
      .then((data) => active && setFacility(data))
      .catch((err) => active && setError(errorMessage(err, 'Could not load this facility.')))
      .finally(() => active && setLoading(false));
    getCurrentLocation()
      .then((coords) => active && setLocation(coords))
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [facilityId]);

  const distance =
    facility && location
      ? haversine(location.latitude, location.longitude, facility.latitude, facility.longitude)
      : null;

  return (
    <UserShell title="Facility Details" back plainHeader>
      {loading && <Spinner label="Loading facility" />}
      {error && <Alert tone="error">{error}</Alert>}

      {facility && (
        <>
          <div className="card card-pad mb-3">
            <div className="row" style={{ alignItems: 'flex-start' }}>
              <span className="choice-icon">{facilityIcon(facility.type)}</span>
              <div className="grow">
                <h2>{facility.name}</h2>
                <p className="small muted">{facility.type}</p>
              </div>
              <Badge value={facility.status} dot />
            </div>

            {facility.description && (
              <p className="small mt-3" style={{ color: 'var(--ink-700)' }}>
                {facility.description}
              </p>
            )}

            {distance !== null && (
              <p className="mt-3">
                <span className="distance-chip">{formatDistance(distance)} from you</span>
              </p>
            )}
          </div>

          <dl className="detail-list mb-3">
            <div className="detail-row">
              <dt>Facility ID</dt>
              <dd>{facility.facility_id}</dd>
            </div>
            <div className="detail-row">
              <dt>Type</dt>
              <dd>{facility.type}</dd>
            </div>
            <div className="detail-row">
              <dt>Status</dt>
              <dd>
                <Badge value={facility.status} />
              </dd>
            </div>
            <div className="detail-row">
              <dt>Location</dt>
              <dd>
                {facility.address || '—'}
                <div className="tiny muted">
                  {facility.latitude.toFixed(5)}, {facility.longitude.toFixed(5)}
                </div>
              </dd>
            </div>
            <div className="detail-row">
              <dt>Source</dt>
              <dd>{facility.source || '—'}</dd>
            </div>
            <div className="detail-row">
              <dt>Last updated</dt>
              <dd>{formatDateTime(facility.last_updated || facility.created_at)}</dd>
            </div>
          </dl>

          <MapView
            center={{ latitude: facility.latitude, longitude: facility.longitude }}
            zoom={17}
            height="map-height-sm"
            showLegend={false}
            markers={[
              facilityMarker(facility),
              ...(location ? [userMarker(location)] : []),
            ]}
          />

          <button
            type="button"
            className="btn btn-primary btn-block mt-3"
            onClick={() =>
              navigate(`/map?type=${encodeURIComponent(facility.type)}`)
            }
          >
            View on Map
          </button>

          <button
            type="button"
            className="btn btn-secondary btn-block mt-2"
            onClick={() =>
              navigate('/report', {
                state: {
                  latitude: facility.latitude,
                  longitude: facility.longitude,
                  locationText: facility.address || facility.name,
                },
              })
            }
          >
            Report a problem here
          </button>
        </>
      )}
    </UserShell>
  );
}
