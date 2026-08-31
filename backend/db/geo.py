"""Spatial querying.

On PostgreSQL with PostGIS the radius search uses ``ST_DWithin`` against the
``GEOGRAPHY(Point, 4326)`` column and ``ST_Distance`` for the metre distance,
which is index-accelerated by the GiST index created in ``init_db``.

When PostGIS is not available (the SQLite development fallback, or a Neon
project where the extension has not been enabled) the same API is served by an
equivalent great-circle (haversine) expression evaluated in SQL, with a
bounding-box pre-filter so the plain lat/lng index is still used.
"""

from __future__ import annotations

import math
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.db.init_db import has_postgis

EARTH_RADIUS_M = 6_371_008.8

_POSTGIS_SQL = """
SELECT {columns},
       ST_Distance(location_point, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography)
           AS distance_m
  FROM {table}
 WHERE location_point IS NOT NULL
   AND ST_DWithin(location_point, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radius)
   {extra}
 ORDER BY distance_m ASC
 LIMIT :limit
"""

# Haversine in raw SQL.  The bounding box narrows the candidate set first.
_HAVERSINE_SQL = """
SELECT {columns},
       (:earth_radius * 2 * ASIN(MIN(1.0, SQRT(
            POWER(SIN(RADIANS(latitude - :lat) / 2), 2) +
            COS(RADIANS(:lat)) * COS(RADIANS(latitude)) *
            POWER(SIN(RADIANS(longitude - :lng) / 2), 2)
       )))) AS distance_m
  FROM {table}
 WHERE latitude BETWEEN :min_lat AND :max_lat
   AND longitude BETWEEN :min_lng AND :max_lng
   {extra}
   AND (:earth_radius * 2 * ASIN(MIN(1.0, SQRT(
            POWER(SIN(RADIANS(latitude - :lat) / 2), 2) +
            COS(RADIANS(:lat)) * COS(RADIANS(latitude)) *
            POWER(SIN(RADIANS(longitude - :lng) / 2), 2)
       )))) <= :radius
 ORDER BY distance_m ASC
 LIMIT :limit
"""


def bounding_box(lat: float, lng: float, radius_m: float) -> dict[str, float]:
    """Return the lat/lng envelope enclosing a circle of ``radius_m``."""
    lat_delta = math.degrees(radius_m / EARTH_RADIUS_M)
    cos_lat = max(math.cos(math.radians(lat)), 1e-6)
    lng_delta = math.degrees(radius_m / (EARTH_RADIUS_M * cos_lat))
    return {
        "min_lat": max(lat - lat_delta, -90.0),
        "max_lat": min(lat + lat_delta, 90.0),
        "min_lng": max(lng - lng_delta, -180.0),
        "max_lng": min(lng + lng_delta, 180.0),
    }


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres between two WGS-84 points."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def nearby(
    db: Session,
    *,
    table: str,
    columns: list[str],
    latitude: float,
    longitude: float,
    radius_m: float,
    limit: int = 200,
    filters: dict[str, Any] | None = None,
    extra_sql: str = "",
) -> list[dict[str, Any]]:
    """Radius search returning rows ordered nearest-first with ``distance_m``.

    ``filters`` maps a column name to a required value (``None`` values and
    empty strings are ignored, so callers can pass optional query parameters
    straight through).
    """
    filters = {k: v for k, v in (filters or {}).items() if v not in (None, "")}
    conditions = "".join(f" AND {column} = :flt_{column}" for column in filters)
    if extra_sql:
        conditions += f" AND ({extra_sql})"

    params: dict[str, Any] = {
        "lat": float(latitude),
        "lng": float(longitude),
        "radius": float(radius_m),
        "limit": int(limit),
    }
    params.update({f"flt_{k}": v for k, v in filters.items()})

    column_sql = ", ".join(columns)
    if has_postgis():
        sql = _POSTGIS_SQL.format(table=table, columns=column_sql, extra=conditions)
    else:
        params.update(bounding_box(float(latitude), float(longitude), float(radius_m)))
        params["earth_radius"] = EARTH_RADIUS_M
        sql = _HAVERSINE_SQL.format(table=table, columns=column_sql, extra=conditions)

    rows = db.execute(text(sql), params).mappings().all()
    return [dict(row) for row in rows]


def spatial_backend() -> str:
    """Human readable description of the active spatial backend."""
    return "postgis" if has_postgis() else "haversine"
