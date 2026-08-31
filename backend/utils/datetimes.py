"""Timestamp parsing/serialisation helpers.

All timestamps are normalised to timezone-aware UTC on the way in and
serialised as ISO-8601 on the way out.  Naive input is interpreted as IST
(Asia/Kolkata), which is the deployment locale for the MVP.
"""

from __future__ import annotations

import datetime as dt

IST = dt.timezone(dt.timedelta(hours=5, minutes=30), name="IST")

_FORMATS = (
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H:%M:%S%z",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%d-%m-%Y %H:%M",
    "%d-%m-%Y",
)


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def parse_timestamp(value) -> dt.datetime | None:
    """Parse a timestamp from a CSV cell, form field or ISO string."""
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return ensure_utc(value)
    if isinstance(value, dt.date):
        return dt.datetime(value.year, value.month, value.day, tzinfo=IST).astimezone(
            dt.timezone.utc
        )

    raw = str(value).strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"

    try:
        return ensure_utc(dt.datetime.fromisoformat(raw))
    except ValueError:
        pass

    for fmt in _FORMATS:
        try:
            return ensure_utc(dt.datetime.strptime(raw, fmt))
        except ValueError:
            continue
    return None


def ensure_utc(value: dt.datetime | None) -> dt.datetime | None:
    """Attach UTC to naive datetimes read back from the database."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=IST).astimezone(dt.timezone.utc)
    return value.astimezone(dt.timezone.utc)


def iso(value: dt.datetime | None) -> str | None:
    value = ensure_utc(value)
    return value.isoformat() if value else None
