"""Citizen report submission, listing and evidence-image access."""

from __future__ import annotations

import datetime as dt

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.constants import (
    ISSUE_TYPES,
    REPORT_STATUSES,
    SEVERITIES,
    normalise_issue_type,
    title_match,
)
from backend.core.deps import (
    bearer_scheme,
    get_current_user,
    require_user,
    resolve_media_principal,
)
from backend.core.security import create_media_token
from backend.db.geo import nearby
from backend.db.session import get_db
from backend.models.entities import MaintenanceTask, Report, User
from backend.schemas.common import Page
from backend.schemas.reports import (
    ImageAccess,
    ReportCreate,
    ReportMapPin,
    ReportOut,
)
from backend.services import audit, notifications, storage
from backend.services.serializers import report_out
from backend.utils.errors import first_error_message
from backend.utils.datetimes import parse_timestamp, utcnow
from backend.utils.ids import new_report_id

router = APIRouter(tags=["reports"])

OPEN_STATUSES = ("Submitted", "Under Review", "Assigned", "In Progress")


def _latest_task(db: Session, report_id: str) -> MaintenanceTask | None:
    return db.execute(
        select(MaintenanceTask)
        .where(MaintenanceTask.report_id == report_id)
        .order_by(MaintenanceTask.id.desc())
        .limit(1)
    ).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------
@router.get("/reports/options", response_model=dict)
def report_options():
    """Enumerations used by the 'Report an Issue' screens."""
    return {
        "issue_types": list(ISSUE_TYPES),
        "severities": list(SEVERITIES),
        "statuses": list(REPORT_STATUSES),
    }


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------
@router.post(
    "/user/reports", response_model=ReportOut, status_code=status.HTTP_201_CREATED
)
async def create_report(
    issue_type: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    severity: str = Form(...),
    description: str | None = Form(default=None),
    location_text: str | None = Form(default=None),
    timestamp: str | None = Form(default=None),
    photo: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    """Submit an accessibility issue report.

    Sent as ``multipart/form-data`` so the camera/gallery photo can travel with
    the report.  The image is streamed to Amazon S3 and only the object key is
    persisted; the report id, user id, validation status and status are all
    assigned by the backend, never by the client.
    """
    # The form fields are validated through the same model as the JSON body so
    # both entry points enforce identical rules; a failure here is a client
    # error, not a server error.
    try:
        payload = ReportCreate(
            issue_type=issue_type,
            latitude=latitude,
            longitude=longitude,
            severity=severity,
            description=description,
            location_text=location_text,
            timestamp=parse_timestamp(timestamp),
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=first_error_message(exc),
        ) from exc

    report_id = new_report_id(db)
    reported_at = payload.timestamp or utcnow()
    now = utcnow()

    object_key = None
    if photo is not None and photo.filename:
        data = await photo.read()
        try:
            extension = storage.extension_for(photo.content_type, photo.filename)
            object_key = storage.put_object(
                db,
                object_key=storage.unique_object_key("reports", report_id, extension),
                data=data,
                content_type=photo.content_type or "image/jpeg",
            )
        except storage.StorageError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc

    report = Report(
        report_id=report_id,
        user_id=current_user.user_id,
        issue_type=payload.issue_type,
        location_text=payload.location_text,
        latitude=payload.latitude,
        longitude=payload.longitude,
        description=payload.description,
        severity=payload.severity,
        image_object_key=object_key,
        timestamp=reported_at,
        validation_status="Needs Review",
        status="Submitted",
        source="Citizen App",
        created_at=now,
        updated_at=now,
    )
    db.add(report)
    db.flush()

    notifications.report_submitted(
        db, current_user.user_id, report.report_id, report.issue_type
    )
    audit.record(
        db,
        user_id=current_user.user_id,
        role=current_user.role,
        action="report.create",
        entity_type="report",
        entity_id=report.report_id,
        metadata={
            "issue_type": report.issue_type,
            "severity": report.severity,
            "has_image": bool(object_key),
        },
    )
    db.commit()
    db.refresh(report)
    return report_out(report, reporter_name=current_user.name)


@router.post(
    "/user/reports/json", response_model=ReportOut, status_code=status.HTTP_201_CREATED
)
def create_report_json(
    payload: ReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    """JSON variant of report creation for clients without photo evidence."""
    report_id = new_report_id(db)
    now = utcnow()
    report = Report(
        report_id=report_id,
        user_id=current_user.user_id,
        issue_type=payload.issue_type,
        location_text=payload.location_text,
        latitude=payload.latitude,
        longitude=payload.longitude,
        description=payload.description,
        severity=payload.severity,
        timestamp=payload.timestamp or now,
        validation_status="Needs Review",
        status="Submitted",
        source="Citizen App",
        created_at=now,
        updated_at=now,
    )
    db.add(report)
    db.flush()
    notifications.report_submitted(
        db, current_user.user_id, report.report_id, report.issue_type
    )
    audit.record(
        db,
        user_id=current_user.user_id,
        role=current_user.role,
        action="report.create",
        entity_type="report",
        entity_id=report.report_id,
    )
    db.commit()
    db.refresh(report)
    return report_out(report, reporter_name=current_user.name)


# ---------------------------------------------------------------------------
# My Reports
# ---------------------------------------------------------------------------
@router.get("/user/reports", response_model=Page[ReportOut])
def my_reports(
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    stmt = select(Report).where(Report.user_id == current_user.user_id)
    if status_filter:
        matched = title_match(status_filter, REPORT_STATUSES)
        if not matched:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"status must be one of {', '.join(REPORT_STATUSES)}",
            )
        stmt = stmt.where(Report.status == matched)
    if search:
        needle = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Report.report_id).like(needle),
                func.lower(Report.issue_type).like(needle),
                func.lower(Report.location_text).like(needle),
            )
        )

    total = int(db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one())
    rows = (
        db.execute(
            stmt.order_by(Report.timestamp.desc(), Report.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    items = [
        report_out(
            r, reporter_name=current_user.name, task=_latest_task(db, r.report_id)
        )
        for r in rows
    ]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


@router.get("/user/reports/{report_id}", response_model=ReportOut)
def my_report_detail(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    report = db.execute(
        select(Report).where(
            Report.report_id == report_id, Report.user_id == current_user.user_id
        )
    ).scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found."
        )
    return report_out(
        report, reporter_name=current_user.name, task=_latest_task(db, report.report_id)
    )


# ---------------------------------------------------------------------------
# Map pins
# ---------------------------------------------------------------------------
@router.get("/reports/map", response_model=list[ReportMapPin])
def report_pins(
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    radius: int = Query(default=3000, ge=50, le=50000),
    only_open: bool = Query(default=True),
    limit: int = Query(default=300, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Report markers for the accessibility map (visualisation only, no routes)."""
    open_clause = (
        "status IN ('Submitted', 'Under Review', 'Assigned', 'In Progress') "
        "AND validation_status <> 'Invalid'"
    )
    columns = [
        "report_id",
        "issue_type",
        "latitude",
        "longitude",
        "severity",
        "status",
        "validation_status",
        "timestamp",
    ]

    if latitude is not None and longitude is not None:
        rows = nearby(
            db,
            table="reports",
            columns=columns,
            latitude=latitude,
            longitude=longitude,
            radius_m=radius,
            limit=limit,
            extra_sql=open_clause if only_open else "",
        )
        return [{k: row[k] for k in columns} for row in rows]

    stmt = select(Report)
    if only_open:
        stmt = stmt.where(
            Report.status.in_(OPEN_STATUSES), Report.validation_status != "Invalid"
        )
    rows = (
        db.execute(stmt.order_by(Report.timestamp.desc()).limit(limit)).scalars().all()
    )
    return [
        {
            "report_id": r.report_id,
            "issue_type": r.issue_type,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "severity": r.severity,
            "status": r.status,
            "validation_status": r.validation_status,
            "timestamp": r.timestamp,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Evidence images
# ---------------------------------------------------------------------------
def _authorise_image(db: Session, report_id: str, user: User) -> Report:
    report = db.execute(
        select(Report).where(Report.report_id == report_id)
    ).scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found."
        )
    # Citizens may only view evidence attached to their own reports; authority
    # and maintenance staff may view any report they work on.
    if user.role == "USER" and report.user_id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this evidence image.",
        )
    return report


@router.get("/reports/{report_id}/image", response_model=ImageAccess)
def report_image_link(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a short-lived link to the evidence image.

    S3 objects stay private: this issues a presigned GET url valid for
    ``S3_PRESIGN_EXPIRY`` seconds.  Reports imported from CSV carry an
    external ``image_url`` instead, which is returned verbatim.
    """
    report = _authorise_image(db, report_id, current_user)

    if report.image_object_key:
        url = storage.presigned_url(report.image_object_key)
        if url:
            return {
                "url": url,
                "expires_in": settings.s3_presign_expiry,
                "storage": "s3",
                "external": False,
            }
        # No S3 configured: hand back a URL carrying a short-lived, single
        # resource media token, since a browser cannot attach the bearer
        # header to an <img> element.
        token, expires_in = create_media_token(
            subject=current_user.user_id,
            role=current_user.role,
            resource=f"report:{report_id}",
        )
        return {
            "url": f"/api/reports/{report_id}/image/raw?token={token}",
            "expires_in": expires_in,
            "storage": storage.backend_name(),
            "external": False,
        }

    if report.image_url:
        return {
            "url": report.image_url,
            "expires_in": 0,
            "storage": "external-url",
            "external": True,
        }

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="This report has no evidence image.",
    )


@router.get("/reports/{report_id}/image/raw")
def report_image_raw(
    report_id: str,
    token: str | None = Query(default=None, description="Short-lived media token"),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    """Stream the evidence image (S3 redirect, or the development fallback).

    Accepts either an ``Authorization`` header or a scoped ``token`` query
    parameter so the URL can be used directly as an image source.
    """
    current_user = resolve_media_principal(
        db,
        resource=f"report:{report_id}",
        credentials=credentials,
        token=token,
    )
    report = _authorise_image(db, report_id, current_user)
    if not report.image_object_key:
        if report.image_url:
            return RedirectResponse(report.image_url, status_code=307)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This report has no evidence image.",
        )

    url = storage.presigned_url(report.image_object_key)
    if url:
        return RedirectResponse(url, status_code=307)

    blob = storage.fetch_fallback(db, report.image_object_key)
    if blob is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Image data is unavailable."
        )
    data, content_type = blob
    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=300"},
    )
