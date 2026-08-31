/**
 * Client-side great-circle distance, used only to label how far a facility is
 * from the viewer when the value did not come back from the API.
 *
 * This is a straight-line distance, not a walking route: the MVP has no
 * routing engine by design.
 */
const EARTH_RADIUS_M = 6371008.8;

export function haversine(lat1, lng1, lat2, lng2) {
  const toRad = (value) => (value * Math.PI) / 180;
  const phi1 = toRad(lat1);
  const phi2 = toRad(lat2);
  const dPhi = toRad(lat2 - lat1);
  const dLambda = toRad(lng2 - lng1);
  const a =
    Math.sin(dPhi / 2) ** 2 +
    Math.cos(phi1) * Math.cos(phi2) * Math.sin(dLambda / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(a)));
}
