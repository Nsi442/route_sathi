import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { errorMessage } from '../../api/client';
import { analyticsApi } from '../../api/endpoints';
import AuthorityShell from '../../components/AuthorityShell';
import MapView, { reportMarker } from '../../components/MapView';
import { Alert, BarList, Spinner, StatCard } from '../../components/Ui';
import { IconChart, IconClock, IconList } from '../../components/Icons';
import { formatDate } from '../../lib/format';

const RANGES = [7, 30, 90];

/**
 * Map & Analytics.
 *
 * Aggregations come from `GET /api/analytics`; the map plots every report as a
 * marker.  Nothing here draws a route.
 */
export default function Analytics() {
  const navigate = useNavigate();
  const [days, setDays] = useState(30);
  const [onlyOpen, setOnlyOpen] = useState(false);
  const [summary, setSummary] = useState(null);
  const [pins, setPins] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [summaryData, mapData] = await Promise.all([
        analyticsApi.summary({ days }),
        analyticsApi.map({ only_open: onlyOpen, limit: 500 }),
      ]);
      setSummary(summaryData);
      setPins(mapData);
    } catch (err) {
      setError(errorMessage(err, 'Could not load analytics.'));
    } finally {
      setLoading(false);
    }
  }, [days, onlyOpen]);

  useEffect(() => {
    load();
  }, [load]);

  const markers = useMemo(
    () => pins.map((pin) => reportMarker(pin, { onView: true })),
    [pins],
  );

  const maxTrend = useMemo(() => {
    if (!summary?.trend?.length) return 1;
    return Math.max(
      ...summary.trend.map((point) => Math.max(point.submitted, point.resolved)),
      1,
    );
  }, [summary]);

  return (
    <AuthorityShell
      title="Map & Analytics"
      subtitle="Where accessibility barriers are, and how quickly they are cleared"
      actions={
        <div className="row">
          {RANGES.map((value) => (
            <button
              key={value}
              type="button"
              className={`btn btn-sm ${days === value ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setDays(value)}
            >
              {value}d
            </button>
          ))}
        </div>
      }
    >
      {error && (
        <div className="mb-4">
          <Alert tone="error">{error}</Alert>
        </div>
      )}

      {loading && !summary ? (
        <Spinner label="Loading analytics" />
      ) : (
        <>
          <div className="stat-grid mb-4">
            <StatCard
              label="Total Reports"
              value={summary?.total_reports ?? 0}
              accent="teal"
              icon={<IconList width={17} height={17} />}
            />
            <StatCard
              label="Mapped Locations"
              value={pins.length}
              accent="blue"
              icon={<IconChart width={17} height={17} />}
            />
            <StatCard
              label="Avg. Resolution Time"
              value={
                summary?.average_resolution_hours
                  ? `${summary.average_resolution_hours} h`
                  : '—'
              }
              accent="violet"
              icon={<IconClock width={17} height={17} />}
              hint="From report to verified repair"
            />
          </div>

          <div className="card mb-4">
            <div className="card-header">
              <div>
                <h2>Report Map</h2>
                <div className="card-title-sub">
                  Every report as a marker — discovery and visualisation only
                </div>
              </div>
              <label className="row small" style={{ gap: 7 }}>
                <input
                  type="checkbox"
                  checked={onlyOpen}
                  onChange={(event) => setOnlyOpen(event.target.checked)}
                />
                Open reports only
              </label>
            </div>
            <div className="card-body">
              <MapView
                center={
                  markers.length
                    ? { latitude: markers[0].latitude, longitude: markers[0].longitude }
                    : undefined
                }
                zoom={12}
                height="map-height-lg"
                markers={markers}
                fitToMarkers
                onMarkerAction={(marker) => navigate(`/authority/reports/${marker.id}`)}
              />
            </div>
          </div>

          <div className="card mb-4">
            <div className="card-header">
              <div>
                <h2>Submissions and Resolutions</h2>
                <div className="card-title-sub">Last {days} days</div>
              </div>
              <div className="legend">
                <span className="key">
                  <span className="swatch" style={{ background: 'var(--teal-500)' }} /> Submitted
                </span>
                <span className="key">
                  <span className="swatch" style={{ background: 'var(--navy-700)' }} /> Resolved
                </span>
              </div>
            </div>
            <div className="card-body">
              <div className="trend-chart">
                {summary?.trend?.map((point) => (
                  <div
                    className="trend-col"
                    key={point.date}
                    title={`${formatDate(point.date)} — ${point.submitted} submitted, ${
                      point.resolved
                    } resolved`}
                  >
                    <span
                      className="trend-bar resolved"
                      style={{ height: `${(point.resolved / maxTrend) * 45}%` }}
                    />
                    <span
                      className="trend-bar submitted"
                      style={{ height: `${(point.submitted / maxTrend) * 45}%` }}
                    />
                  </div>
                ))}
              </div>
              <div className="row-between tiny muted mt-2">
                <span>{summary?.trend?.[0] && formatDate(summary.trend[0].date)}</span>
                <span>
                  {summary?.trend?.length
                    ? formatDate(summary.trend[summary.trend.length - 1].date)
                    : ''}
                </span>
              </div>
            </div>
          </div>

          <div className="split-3">
            <Panel title="By Issue Type" items={summary?.by_issue_type} />
            <Panel title="By Severity" items={summary?.by_severity} />
            <Panel title="By Status" items={summary?.by_status} />
            <Panel title="By Validation" items={summary?.by_validation} />
            <Panel title="By Confirmed Priority" items={summary?.by_priority} />
            <Panel title="By Source" items={summary?.by_source} />
            <Panel title="Top Locations" items={summary?.by_location} />
          </div>
        </>
      )}
    </AuthorityShell>
  );
}

function Panel({ title, items }) {
  return (
    <div className="card">
      <div className="card-header">
        <h3>{title}</h3>
      </div>
      <div className="card-body">
        <BarList items={items} />
      </div>
    </div>
  );
}
