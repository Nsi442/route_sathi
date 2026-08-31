"""Bulk report import from a CSV file uploaded by an authority user.

Contract (see docs/CSV.md):

    report_id,user_id,issue_type,location,latitude,longitude,severity,
    description,image_url,timestamp,validation_status,status,source

Rules enforced here:

* every column above except ``image_url`` is required and validated
* latitude in [-90, 90], longitude in [-180, 180]
* severity in {Low, Medium, High}
* validation_status in {Needs Review, Valid, Invalid}
* status in {Submitted, Under Review, Assigned, In Progress, Resolved}
* duplicate ``report_id`` values are rejected - both against rows already in
  the database and against earlier rows in the same file
* ``image_url`` is stored verbatim as TEXT.  No S3 upload, no image
  processing and no priority prediction happen during CSV import.

The import is all-or-nothing per row: valid rows are committed, invalid rows
are reported back with the row number and the reason.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.constants import (
    REPORT_SOURCES,
    REPORT_STATUSES,
    SEVERITIES,
    VALIDATION_STATUSES,
    normalise_issue_type,
    title_match,
)
from backend.models.entities import Report
from backend.utils.datetimes import parse_timestamp, utcnow

REQUIRED_COLUMNS = (
    "report_id",
    "user_id",
    "issue_type",
    "latitude",
    "longitude",
    "severity",
    "description",
    "timestamp",
    "validation_status",
    "status",
    "source",
)

# ``location`` in the CSV maps to ``location_text`` on the model.
COLUMN_ALIASES = {
    "location": "location_text",
    "location_text": "location_text",
    "lat": "latitude",
    "lng": "longitude",
    "lon": "longitude",
    "long": "longitude",
    "reportid": "report_id",
    "userid": "user_id",
    "issuetype": "issue_type",
    "imageurl": "image_url",
    "validationstatus": "validation_status",
}

MAX_ROWS = 5000


class CsvFormatError(ValueError):
    """Raised when the uploaded file is not a usable CSV."""


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise CsvFormatError("The file could not be decoded as text.")


def _normalise_header(name: str) -> str:
    cleaned = (name or "").strip().lower().replace(" ", "_").replace("-", "_")
    return COLUMN_ALIASES.get(cleaned, COLUMN_ALIASES.get(cleaned.replace("_", ""), cleaned))


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _validate_row(row: dict[str, str]) -> tuple[dict[str, Any] | None, str | None]:
    """Return ``(payload, error)`` for a single CSV row."""
    report_id = _clean(row.get("report_id"))
    if not report_id:
        return None, "Missing report_id"

    user_id = _clean(row.get("user_id"))
    if not user_id:
        return None, "Missing user_id"

    issue_type = normalise_issue_type(_clean(row.get("issue_type")))
    if not issue_type:
        return None, f"Unknown issue_type '{_clean(row.get('issue_type'))}'"

    lat_raw = _clean(row.get("latitude"))
    try:
        latitude = float(lat_raw)
    except ValueError:
        return None, "Invalid latitude"
    if not -90.0 <= latitude <= 90.0:
        return None, "Invalid latitude"

    lng_raw = _clean(row.get("longitude"))
    try:
        longitude = float(lng_raw)
    except ValueError:
        return None, "Invalid longitude"
    if not -180.0 <= longitude <= 180.0:
        return None, "Invalid longitude"

    severity = title_match(_clean(row.get("severity")), SEVERITIES)
    if not severity:
        return None, f"severity must be one of {', '.join(SEVERITIES)}"

    description = _clean(row.get("description"))
    if not description:
        return None, "Missing description"

    timestamp = parse_timestamp(_clean(row.get("timestamp")))
    if timestamp is None:
        return None, "Invalid or missing timestamp"

    validation_status = title_match(_clean(row.get("validation_status")), VALIDATION_STATUSES)
    if not validation_status:
        return None, f"validation_status must be one of {', '.join(VALIDATION_STATUSES)}"

    status = title_match(_clean(row.get("status")), REPORT_STATUSES)
    if not status:
        return None, f"status must be one of {', '.join(REPORT_STATUSES)}"

    source = _clean(row.get("source"))
    if not source:
        return None, "Missing source"
    source = title_match(source, REPORT_SOURCES) or source

    payload = {
        "report_id": report_id,
        "user_id": user_id,
        "issue_type": issue_type,
        "location_text": _clean(row.get("location_text")) or None,
        "latitude": latitude,
        "longitude": longitude,
        "description": description,
        "severity": severity,
        # image_url is optional and stored verbatim as TEXT.
        "image_url": _clean(row.get("image_url")) or None,
        "timestamp": timestamp,
        "validation_status": validation_status,
        "status": status,
        "source": source,
    }
    return payload, None


def import_reports(db: Session, raw: bytes) -> dict[str, Any]:
    """Parse, validate and persist a CSV upload."""
    text = _decode(raw)
    if not text.strip():
        raise CsvFormatError("The uploaded CSV file is empty.")

    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise CsvFormatError("The uploaded CSV file has no header row.")

    header_map = {name: _normalise_header(name) for name in reader.fieldnames}
    present = set(header_map.values())
    missing = [column for column in REQUIRED_COLUMNS if column not in present]
    if missing:
        raise CsvFormatError(
            "CSV is missing required column(s): " + ", ".join(missing)
        )

    existing_ids = set(db.execute(select(Report.report_id)).scalars().all())
    seen_in_file: set[str] = set()

    total = 0
    inserted: list[str] = []
    errors: list[dict[str, Any]] = []

    for index, raw_row in enumerate(reader, start=2):  # row 1 is the header
        if total >= MAX_ROWS:
            errors.append(
                {
                    "row": index,
                    "reportId": None,
                    "reason": f"File exceeds the {MAX_ROWS} row import limit",
                }
            )
            break

        row = {header_map.get(k, k): v for k, v in raw_row.items() if k is not None}
        if not any(_clean(v) for v in row.values()):
            continue  # skip blank lines
        total += 1

        payload, error = _validate_row(row)
        if error:
            errors.append(
                {"row": index, "reportId": _clean(row.get("report_id")) or None, "reason": error}
            )
            continue

        report_id = payload["report_id"]
        if report_id in existing_ids:
            errors.append(
                {"row": index, "reportId": report_id, "reason": "Duplicate report_id (already imported)"}
            )
            continue
        if report_id in seen_in_file:
            errors.append(
                {"row": index, "reportId": report_id, "reason": "Duplicate report_id within the file"}
            )
            continue

        now = utcnow()
        db.add(Report(created_at=now, updated_at=now, **payload))
        seen_in_file.add(report_id)
        inserted.append(report_id)

    if inserted:
        db.flush()

    return {
        "totalRows": total,
        "successfulRows": len(inserted),
        "failedRows": len(errors),
        "errors": errors,
        "inserted": inserted,
    }
