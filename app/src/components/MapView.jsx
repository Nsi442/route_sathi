import { useEffect, useMemo, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

/**
 * Shared Leaflet map.
 *
 * Deliberately marker-only: this MVP has no routing engine, so the map never
 * draws a path, polyline or navigation overlay.  It shows where the user is,
 * where accessible facilities are, where issues are, and lets a reporter pick
 * a point.
 *
 * Marker colours follow the product spec:
 *   blue   - the current user
 *   green  - verified / available facility
 *   orange - under review
 *   red    - an active accessibility problem
 */

const TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

function markerVariant(item) {
  if (item.kind === 'user') return 'is-user';
  if (item.kind === 'selected') return 'is-selected';
  if (item.kind === 'report') return 'is-issue';
  if (item.status === 'Under Review') return 'is-review';
  if (item.status === 'Blocked' || item.status === 'Inactive') return 'is-issue';
  return 'is-verified';
}

function markerGlyph(item) {
  if (item.kind === 'user') return '';
  if (item.kind === 'selected') return '+';
  if (item.kind === 'report') return '!';
  return (item.type || '?').slice(0, 1).toUpperCase();
}

function buildIcon(item) {
  const variant = markerVariant(item);
  const pulse = item.kind === 'user' ? '<span class="rs-user-pulse"></span>' : '';
  return L.divIcon({
    className: 'rs-marker-wrap',
    html: `<div class="rs-marker ${variant}">${pulse}<span>${markerGlyph(item)}</span></div>`,
    iconSize: [26, 26],
    iconAnchor: item.kind === 'user' ? [13, 13] : [13, 26],
    popupAnchor: [0, item.kind === 'user' ? -14 : -26],
  });
}

function popupHtml(item) {
  const title = item.title || item.name || item.report_id || 'Location';
  const lines = [];
  if (item.subtitle) lines.push(item.subtitle);
  if (item.status) lines.push(item.status);
  if (item.distanceLabel) lines.push(item.distanceLabel);
  return `<div class="map-popup">
    <div class="popup-title">${escapeHtml(title)}</div>
    <div class="popup-meta">${escapeHtml(lines.filter(Boolean).join(' · '))}</div>
    ${item.actionLabel ? `<div class="popup-link" data-marker-action="${escapeHtml(item.id)}">${escapeHtml(item.actionLabel)}</div>` : ''}
  </div>`;
}

function escapeHtml(value) {
  return String(value ?? '').replace(
    /[&<>"']/g,
    (character) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character],
  );
}

export default function MapView({
  center,
  zoom = 15,
  markers = [],
  height = 'map-height-md',
  full = false,
  onMarkerAction,
  onMapClick,
  pickerHint,
  showLegend = true,
  onLocate,
  fitToMarkers = false,
  className = '',
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);
  const clickRef = useRef(onMapClick);
  const actionRef = useRef(onMarkerAction);

  clickRef.current = onMapClick;
  actionRef.current = onMarkerAction;

  const centerKey = center ? `${center.latitude},${center.longitude}` : '';
  const markerKey = useMemo(
    () =>
      markers
        .map((m) => `${m.id}:${m.latitude}:${m.longitude}:${m.kind || ''}:${m.status || ''}`)
        .join('|'),
    [markers],
  );

  // Create the map once.
  useEffect(() => {
    if (mapRef.current || !containerRef.current) return undefined;
    const map = L.map(containerRef.current, {
      center: center ? [center.latitude, center.longitude] : [22.5726, 88.3639],
      zoom,
      zoomControl: true,
      attributionControl: true,
    });
    L.tileLayer(TILE_URL, { attribution: TILE_ATTRIBUTION, maxZoom: 19 }).addTo(map);
    layerRef.current = L.layerGroup().addTo(map);
    map.on('click', (event) => {
      if (clickRef.current) {
        clickRef.current({
          latitude: Number(event.latlng.lat.toFixed(6)),
          longitude: Number(event.latlng.lng.toFixed(6)),
        });
      }
    });
    mapRef.current = map;
    // Leaflet needs a size recalculation once the container has been laid out.
    setTimeout(() => map.invalidateSize(), 120);
    return () => {
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Recentre when the caller moves the view.
  useEffect(() => {
    if (!mapRef.current || !center) return;
    mapRef.current.setView([center.latitude, center.longitude], zoom, { animate: true });
  }, [centerKey, zoom]); // eslint-disable-line react-hooks/exhaustive-deps

  // Redraw markers.
  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;
    layer.clearLayers();

    markers.forEach((item) => {
      if (item.latitude === null || item.longitude === null) return;
      const marker = L.marker([item.latitude, item.longitude], {
        icon: buildIcon(item),
        title: item.title || item.name || '',
        keyboard: true,
        alt: item.title || item.name || 'Map marker',
      });
      marker.bindPopup(popupHtml(item));
      marker.on('popupopen', (event) => {
        const node = event.popup.getElement()?.querySelector('[data-marker-action]');
        if (node && actionRef.current) {
          node.addEventListener('click', () => actionRef.current(item), { once: true });
        }
      });
      marker.addTo(layer);
    });

    if (fitToMarkers && markers.length > 1) {
      const bounds = L.latLngBounds(markers.map((m) => [m.latitude, m.longitude]));
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 16 });
    }
  }, [markerKey, fitToMarkers]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className={`map-shell ${full ? 'is-full' : height} ${className}`.trim()}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      {pickerHint && <div className="map-picker-hint">{pickerHint}</div>}
      {showLegend && (
        <div className="map-legend" aria-hidden="true">
          <span className="key">
            <span className="swatch" style={{ background: '#2563eb' }} /> You
          </span>
          <span className="key">
            <span className="swatch" style={{ background: '#15803d' }} /> Accessible
          </span>
          <span className="key">
            <span className="swatch" style={{ background: '#d97706' }} /> Under review
          </span>
          <span className="key">
            <span className="swatch" style={{ background: '#dc2626' }} /> Issue
          </span>
        </div>
      )}
      {onLocate && (
        <button
          type="button"
          className="map-locate"
          onClick={onLocate}
          aria-label="Centre the map on my location"
          title="Centre on my location"
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="7" />
            <circle cx="12" cy="12" r="2" />
            <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
          </svg>
        </button>
      )}
    </div>
  );
}

/** Convert an API facility into a MapView marker. */
export function facilityMarker(facility, { onView } = {}) {
  return {
    id: facility.facility_id,
    kind: 'facility',
    latitude: facility.latitude,
    longitude: facility.longitude,
    title: facility.name,
    subtitle: facility.type,
    status: facility.status,
    type: facility.type,
    distanceLabel:
      facility.distance !== undefined && facility.distance !== null
        ? `${Math.round(facility.distance)} m away`
        : undefined,
    actionLabel: onView ? 'View details' : undefined,
    raw: facility,
  };
}

/** Convert an API report pin into a MapView marker. */
export function reportMarker(report, { onView } = {}) {
  return {
    id: report.report_id,
    kind: 'report',
    latitude: report.latitude,
    longitude: report.longitude,
    title: report.issue_type,
    subtitle: `${report.report_id} · ${report.severity} severity`,
    status: report.status,
    actionLabel: onView ? 'Open report' : undefined,
    raw: report,
  };
}

export function userMarker(location) {
  return {
    id: 'me',
    kind: 'user',
    latitude: location.latitude,
    longitude: location.longitude,
    title: 'Your location',
    subtitle: location.accuracy ? `Accurate to ~${Math.round(location.accuracy)} m` : undefined,
  };
}
