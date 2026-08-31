"""Schema bootstrap.

Creates the relational tables via SQLAlchemy metadata and, on PostgreSQL,
installs the PostGIS extension, the ``GEOGRAPHY(Point, 4326)`` columns, the
GiST indexes and the triggers that keep the geometry in sync with the
latitude/longitude columns written by the application.

The bootstrap is idempotent and cheap: it is guarded by a module-level flag so
a warm serverless container only pays for it once.
"""

from __future__ import annotations

import logging
import threading

from sqlalchemy import inspect, text

from backend.core.config import settings
from backend.db.base import Base
from backend.db.session import engine
from backend.models import entities  # noqa: F401  (registers the models)

logger = logging.getLogger("routesathi.db")

_lock = threading.Lock()
_initialised = False

GEO_TABLES = ("accessibility_facilities", "reports")

POSTGIS_BOOTSTRAP = """
CREATE EXTENSION IF NOT EXISTS postgis;
"""

# Per-table statements: add the geography column, backfill it, index it and
# keep it in sync with the plain lat/lng columns.
GEO_TABLE_SQL = """
ALTER TABLE {table}
    ALTER COLUMN location_point TYPE geography(Point, 4326)
    USING CASE
        WHEN location_point IS NULL OR location_point = '' THEN NULL
        ELSE ST_GeogFromText(location_point)
    END;

CREATE INDEX IF NOT EXISTS ix_{table}_location_point
    ON {table} USING GIST (location_point);

CREATE OR REPLACE FUNCTION routesathi_sync_{table}_point()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.latitude IS NOT NULL AND NEW.longitude IS NOT NULL THEN
        NEW.location_point := ST_SetSRID(
            ST_MakePoint(NEW.longitude, NEW.latitude), 4326
        )::geography;
    ELSE
        NEW.location_point := NULL;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_{table}_sync_point ON {table};
CREATE TRIGGER trg_{table}_sync_point
    BEFORE INSERT OR UPDATE OF latitude, longitude ON {table}
    FOR EACH ROW EXECUTE FUNCTION routesathi_sync_{table}_point();

UPDATE {table}
   SET location_point = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography
 WHERE location_point IS NULL
   AND latitude IS NOT NULL
   AND longitude IS NOT NULL;
"""


def _run_script(connection, script: str) -> None:
    for statement in _split_statements(script):
        connection.execute(text(statement))


def _split_statements(script: str) -> list[str]:
    """Split a SQL script on ';' while respecting $$-quoted function bodies."""
    statements: list[str] = []
    buffer: list[str] = []
    in_dollar = False
    for line in script.splitlines():
        if line.count("$$") % 2 == 1:
            in_dollar = not in_dollar
        buffer.append(line)
        if not in_dollar and line.rstrip().endswith(";"):
            statement = "\n".join(buffer).strip().rstrip(";").strip()
            if statement:
                statements.append(statement)
            buffer = []
    tail = "\n".join(buffer).strip().rstrip(";").strip()
    if tail:
        statements.append(tail)
    return statements


def _bootstrap_postgis() -> None:
    """Install PostGIS support.  Failures are logged, never fatal."""
    try:
        with engine.begin() as connection:
            _run_script(connection, POSTGIS_BOOTSTRAP)
    except Exception as exc:  # pragma: no cover - depends on Neon privileges
        logger.warning("PostGIS extension unavailable (%s); using haversine fallback", exc)
        return

    for table in GEO_TABLES:
        try:
            with engine.begin() as connection:
                _run_script(connection, GEO_TABLE_SQL.format(table=table))
        except Exception as exc:  # pragma: no cover
            logger.warning("PostGIS setup skipped for %s: %s", table, exc)


def has_postgis() -> bool:
    """True when PostGIS is installed and the geography columns are usable."""
    if not settings.is_postgres:
        return False
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = 'reports' AND column_name = 'location_point' "
                    "AND udt_name = 'geography'"
                )
            ).first()
        return row is not None
    except Exception:  # pragma: no cover
        return False


def init_db(force: bool = False) -> None:
    """Create tables and spatial objects.  Safe to call on every cold start."""
    global _initialised
    if _initialised and not force:
        return
    with _lock:
        if _initialised and not force:
            return
        Base.metadata.create_all(bind=engine)
        if settings.is_postgres:
            _bootstrap_postgis()
        _initialised = True
        logger.info(
            "database ready (%s)",
            "postgresql+postgis" if has_postgis() else settings.database_url.split("://")[0],
        )


def table_names() -> list[str]:
    return sorted(inspect(engine).get_table_names())
