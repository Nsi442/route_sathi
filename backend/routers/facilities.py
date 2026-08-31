"""Accessibility facility discovery.

The map is used for discovery only - there is no routing engine, no
turn-by-turn navigation and no walking-distance calculation in this MVP.
``distance`` is always the straight-line (great-circle) distance in metres.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.core.constants import FACILITY_STATUSES, FACILITY_TYPES, title_match
from backend.core.deps import get_current_user, require_authority
from backend.db.geo import nearby
from backend.db.session import get_db
from backend.models.entities import AccessibilityFacility, User
from backend.schemas.common import Page
from backend.schemas.facilities import (
    FacilityCreate,
    FacilityNearby,
    FacilityOut,
    FacilityUpdate,
)
from backend.services import audit
from backend.utils.datetimes import utcnow
from backend.utils.ids import new_facility_id

router = APIRouter(prefix="/facilities", tags=["facilities"])

NEARBY_COLUMNS = [
    "facility_id",
    "name",
    "type",
    "description",
    "address",
    "latitude",
    "longitude",
    "status",
    "source",
    "last_updated",
]


@router.get("/types", response_model=dict)
def facility_types():
    """Categories and statuses used by the filter sheet on the map screen."""
    return {"types": list(FACILITY_TYPES), "statuses": list(FACILITY_STATUSES)}


@router.get("/nearby", response_model=list[FacilityNearby])
def nearby_facilities(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius: int = Query(default=500, ge=25, le=20000, description="Search radius in metres"),
    type: str | None = Query(default=None, description="Facility category filter"),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Radius search backed by PostGIS ``ST_DWithin`` / ``ST_Distance``.

    Results are filtered by category, ordered nearest-to-farthest and carry the
    straight-line distance in metres.
    """
    facility_type = None
    if type:
        facility_type = title_match(type, FACILITY_TYPES)
        if not facility_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"type must be one of {', '.join(FACILITY_TYPES)}",
            )

    facility_status = None
    if status_filter:
        facility_status = title_match(status_filter, FACILITY_STATUSES)
        if not facility_status:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"status must be one of {', '.join(FACILITY_STATUSES)}",
            )

    rows = nearby(
        db,
        table="accessibility_facilities",
        columns=NEARBY_COLUMNS,
        latitude=latitude,
        longitude=longitude,
        radius_m=radius,
        limit=limit,
        filters={"type": facility_type, "status": facility_status},
        extra_sql="" if facility_status else "status <> 'Inactive'",
    )
    return [
        {**row, "distance": round(float(row.pop("distance_m") or 0.0), 1)} for row in rows
    ]


@router.get("", response_model=Page[FacilityOut])
def list_facilities(
    type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(AccessibilityFacility)
    if type:
        stmt = stmt.where(AccessibilityFacility.type == title_match(type, FACILITY_TYPES))
    if status_filter:
        stmt = stmt.where(
            AccessibilityFacility.status == title_match(status_filter, FACILITY_STATUSES)
        )
    if search:
        needle = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(AccessibilityFacility.name).like(needle),
                func.lower(AccessibilityFacility.address).like(needle),
                func.lower(AccessibilityFacility.facility_id).like(needle),
            )
        )

    total = int(
        db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    )
    rows = (
        db.execute(
            stmt.order_by(AccessibilityFacility.name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return {
        "items": [FacilityOut.model_validate(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


@router.get("/{facility_id}", response_model=FacilityOut)
def facility_details(
    facility_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    facility = db.execute(
        select(AccessibilityFacility).where(
            AccessibilityFacility.facility_id == facility_id
        )
    ).scalar_one_or_none()
    if facility is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Facility not found."
        )
    return FacilityOut.model_validate(facility)


@router.post("", response_model=FacilityOut, status_code=status.HTTP_201_CREATED)
def create_facility(
    payload: FacilityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authority),
):
    facility = AccessibilityFacility(
        facility_id=new_facility_id(db),
        last_updated=utcnow(),
        **payload.model_dump(),
    )
    db.add(facility)
    db.flush()
    audit.record(
        db,
        user_id=current_user.user_id,
        role=current_user.role,
        action="facility.create",
        entity_type="facility",
        entity_id=facility.facility_id,
        metadata={"type": facility.type, "status": facility.status},
    )
    db.commit()
    db.refresh(facility)
    return FacilityOut.model_validate(facility)


@router.patch("/{facility_id}", response_model=FacilityOut)
def update_facility(
    facility_id: str,
    payload: FacilityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authority),
):
    """Authority update of an accessibility status (the status-update feature)."""
    facility = db.execute(
        select(AccessibilityFacility).where(
            AccessibilityFacility.facility_id == facility_id
        )
    ).scalar_one_or_none()
    if facility is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Facility not found."
        )

    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in changes.items():
        setattr(facility, field, value)
    facility.last_updated = utcnow()
    db.flush()
    audit.record(
        db,
        user_id=current_user.user_id,
        role=current_user.role,
        action="facility.update",
        entity_type="facility",
        entity_id=facility.facility_id,
        metadata=changes,
    )
    db.commit()
    db.refresh(facility)
    return FacilityOut.model_validate(facility)
