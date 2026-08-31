/**
 * Browser Geolocation wrapper.
 *
 * Resolves to `{ latitude, longitude, accuracy, timestamp }` where timestamp is
 * an ISO-8601 string, matching the shape the API expects.
 */

export const DEFAULT_CENTER = { latitude: 22.5726, longitude: 88.3639 }; // Kolkata

export function getCurrentLocation({ timeout = 12000, highAccuracy = true } = {}) {
  return new Promise((resolve, reject) => {
    if (!('geolocation' in navigator)) {
      reject(new Error('Location services are not available in this browser.'));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) =>
        resolve({
          latitude: Number(position.coords.latitude.toFixed(6)),
          longitude: Number(position.coords.longitude.toFixed(6)),
          accuracy: position.coords.accuracy ?? null,
          timestamp: new Date(position.timestamp || Date.now()).toISOString(),
        }),
      (error) => {
        const messages = {
          1: 'Location permission was denied. Enable it to see places near you.',
          2: 'Your location is unavailable right now. Try again in a moment.',
          3: 'Finding your location took too long. Try again.',
        };
        reject(new Error(messages[error.code] || 'Could not determine your location.'));
      },
      { enableHighAccuracy: highAccuracy, timeout, maximumAge: 30000 },
    );
  });
}

/** Metres formatted for display next to a facility. */
export function formatDistance(metres) {
  if (metres === null || metres === undefined) return '';
  if (metres < 1000) return `${Math.round(metres)} m`;
  return `${(metres / 1000).toFixed(metres < 10000 ? 1 : 0)} km`;
}
