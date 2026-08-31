"""Keeping the accessibility map in step with the report lifecycle.

A report is not just a ticket — it is a statement about a place. When an
authority confirms that a ramp is blocked, the map should stop showing that
ramp as usable. When a maintenance team clears it and the authority verifies
the fix, that place becomes a verified accessible facility.

So the two ends of the workflow move the map:

    report validated as Valid   ->  the facility there becomes "Blocked"
                                    (red on the map)

    resolution verified         ->  the facility there becomes "Verified"
                                    (green on the map), created if it did not
                                    exist before

Matching is spatial: a facility of the same kind within ``MATCH_RADIUS_M`` of
the report is treated as the same place, so repeated reports about one ramp
update a single facility instead of littering the map with duplicates.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.geo import nearby
from backend.models.entities import AccessibilityFacility, Report
from backend.utils.datetimes import utcnow
from backend.utils.ids import new_facility_id

logger = logging.getLogger("routesathi.facilities")

# How close a facility must be to a report to count as the same place.
MATCH_RADIUS_M = 40

# What kind of accessible facility each issue is really about.
ISSUE_TO_FACILITY_TYPE = {
    "Ramp Blocked": "Ramp",
    "Stairs / No Ramp": "Ramp",
    "No Accessible Entrance": "Entrance",
    "Blocked Crossing": "Crossing",
    "Footpath Damaged": "Pathway",
    "Waterlogging": "Pathway",
    "Other": "Other",
}

# A resolved report of this kind means the facility now exists and works.
RESOLVED_STATUS = "Verified"
# A confirmed report of this kind means the facility is currently unusable.
BLOCKED_STATUS = "Blocked"


def facility_type_for(issue_type: str) -> str:
    return ISSUE_TO_FACILITY_TYPE.get(issue_type, "Other")


def _default_name(report: Report, facility_type: str) -> str:
    place = (report.location_text or "").strip()
    if place:
        # "College Street, Kolkata" -> "College Street Ramp"
        head = place.split(",")[0].strip()
        if head:
            return f"{head} {facility_type}"
    return f"{facility_type} near {report.latitude:.4f}, {report.longitude:.4f}"


def find_matching_facility(
    db: Session, *, latitude: float, longitude: float, facility_type: str
) -> AccessibilityFacility | None:
    """Nearest facility of the same type within the match radius, if any."""
    rows = nearby(
        db,
        table="accessibility_facilities",
        columns=["facility_id"],
        latitude=latitude,
        longitude=longitude,
        radius_m=MATCH_RADIUS_M,
        limit=1,
        filters={"type": facility_type},
    )
    if not rows:
        return None
    return db.execute(
        select(AccessibilityFacility).where(
            AccessibilityFacility.facility_id == rows[0]["facility_id"]
        )
    ).scalar_one_or_none()


def mark_blocked_from_report(db: Session, report: Report) -> AccessibilityFacility | None:
    """A confirmed barrier makes the facility at that place unusable.

    Returns the facility that changed, or ``None`` when there is no known
    facility there yet — an unbuilt ramp has nothing to mark as blocked, and
    the open report already shows on the map as a red issue marker.
    """
    facility_type = facility_type_for(report.issue_type)
    facility = find_matching_facility(
        db,
        latitude=report.latitude,
        longitude=report.longitude,
        facility_type=facility_type,
    )
    if facility is None:
        return None
    if facility.status == BLOCKED_STATUS:
        return facility

    facility.status = BLOCKED_STATUS
    facility.description = (
        f"Reported unusable in {report.report_id}: {report.issue_type}."
        + (f" {report.description}" if report.description else "")
    )[:2000]
    facility.last_updated = utcnow()
    db.flush()
    logger.info("facility %s marked blocked by %s", facility.facility_id, report.report_id)
    return facility


def promote_report_to_facility(
    db: Session, report: Report, *, verified_by: str | None = None
) -> tuple[AccessibilityFacility, bool]:
    """A verified repair makes that place a verified accessible facility.

    Returns ``(facility, created)`` — ``created`` is True when the repair put
    a new facility on the map rather than restoring an existing one.
    """
    facility_type = facility_type_for(report.issue_type)
    facility = find_matching_facility(
        db,
        latitude=report.latitude,
        longitude=report.longitude,
        facility_type=facility_type,
    )
    now = utcnow()
    description = (
        f"Repaired and verified after report {report.report_id} "
        f"({report.issue_type})."
    )

    if facility is not None:
        facility.status = RESOLVED_STATUS
        facility.description = description
        facility.last_updated = now
        if verified_by:
            facility.source = f"Verified repair · {report.report_id}"
        db.flush()
        logger.info(
            "facility %s restored to Verified by %s", facility.facility_id, report.report_id
        )
        return facility, False

    facility = AccessibilityFacility(
        facility_id=new_facility_id(db),
        name=_default_name(report, facility_type),
        type=facility_type,
        description=description,
        address=report.location_text,
        latitude=report.latitude,
        longitude=report.longitude,
        status=RESOLVED_STATUS,
        source=f"Verified repair · {report.report_id}",
        last_updated=now,
        created_at=now,
        updated_at=now,
    )
    db.add(facility)
    db.flush()
    logger.info("facility %s created from resolved %s", facility.facility_id, report.report_id)
    return facility, True
