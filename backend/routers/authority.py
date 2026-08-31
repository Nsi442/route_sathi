"""Authority portal: dashboard, CSV import, validation, priority, assignment."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.core.constants import (
    ISSUE_TYPES,
    MAINTENANCE_TEAMS,
    PRIORITIES,
    REPORT_SOURCES,
    REPORT_STATUSES,
    SEVERITIES,
    TASK_STATUSES,
    VALIDATION_STATUSES,
    title_match,
)
from backend.core.deps import require_authority
from backend.db.session import get_db
from backend.ml import priority as ml_priority
from backend.models.entities import (
    AccessibilityFacility,
    MaintenanceTask,
    Report,
    User,
)
from backend.schemas.analytics import DashboardOverview
from backend.schemas.common import AuditEntry, Message, Page
from backend.schemas.maintenance import AssignRequest, TaskOut, VerifyRequest
from backend.schemas.reports import (
    CsvImportResult,
    PriorityConfirmRequest,
    PriorityPrediction,
    ReportOut,
    StatusUpdateRequest,
    ValidationRequest,
)
from backend.services import audit, facility_lifecycle, notifications
from backend.services.csv_import import CsvFormatError, import_reports
from backend.services.serializers import report_out, task_out
from backend.utils.datetimes import utcnow
from backend.utils.ids import new_task_id

router = APIRouter(prefix="/authority", tags=["authority"])

OPEN_STATUSES = ("Submitted", "Under Review", "Assigned", "In Progress")
MAX_CSV_BYTES = 5 * 1024 * 1024


def _get_report(db: Session, report_id: str) -> Report:
    report = db.execute(
        select(Report).where(Report.report_id == report_id)
    ).scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found."
        )
    return report


def _latest_task(db: Session, report_id: str) -> MaintenanceTask | None:
    return db.execute(
        select(MaintenanceTask)
        .where(MaintenanceTask.report_id == report_id)
        .order_by(MaintenanceTask.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def _reporter_name(db: Session, user_id: str) -> str | None:
    return db.execute(select(User.name).where(User.user_id == user_id)).scalar_one_or_none()


def _count(db: Session, *conditions) -> int:
    return int(
        db.execute(select(func.count()).select_from(Report).where(*conditions)).scalar_one()
    )


# ---------------------------------------------------------------------------
# 1. Dashboard overview
# ---------------------------------------------------------------------------
@router.get("/overview", response_model=DashboardOverview)
def overview(db: Session = Depends(get_db), current_user: User = Depends(require_authority)):
    """Live counters for the dashboard cards, computed from PostgreSQL."""
    total = _count(db)
    resolved = _count(db, Report.status == "Resolved")
    task_counts = dict(
        db.execute(
            select(MaintenanceTask.status, func.count()).group_by(MaintenanceTask.status)
        ).all()
    )
    return {
        "total_reports": total,
        "new_reports": _count(db, Report.status == "Submitted"),
        "under_review": _count(db, Report.validation_status == "Needs Review"),
        "valid_reports": _count(db, Report.validation_status == "Valid"),
        "invalid_reports": _count(db, Report.validation_status == "Invalid"),
        "assigned_tasks": int(task_counts.get("Assigned", 0)),
        "in_progress": int(task_counts.get("In Progress", 0)),
        "resolved": resolved,
        "high_severity_open": _count(
            db, Report.severity == "High", Report.status.in_(OPEN_STATUSES)
        ),
        "awaiting_verification": int(task_counts.get("Completed", 0)),
        "total_facilities": int(
            db.execute(
                select(func.count()).select_from(AccessibilityFacility)
            ).scalar_one()
        ),
        "resolution_rate": round((resolved / total) * 100, 1) if total else 0.0,
    }


@router.get("/filters", response_model=dict)
def filter_options(current_user: User = Depends(require_authority)):
    """Values used to populate the reports-page filter dropdowns."""
    return {
        "issue_types": list(ISSUE_TYPES),
        "severities": list(SEVERITIES),
        "validation_statuses": list(VALIDATION_STATUSES),
        "statuses": list(REPORT_STATUSES),
        "priorities": list(PRIORITIES),
        "sources": list(REPORT_SOURCES),
        "teams": list(MAINTENANCE_TEAMS),
        "task_statuses": list(TASK_STATUSES),
    }


# ---------------------------------------------------------------------------
# 2. CSV bulk import (lives on the dashboard, not the reports page)
# ---------------------------------------------------------------------------
@router.post("/reports/upload", response_model=CsvImportResult)
async def upload_reports_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authority),
):
    """Bulk-load reports from a CSV export.

    No S3 upload, no image processing and no priority prediction happen here -
    ``image_url`` is stored verbatim as TEXT and priority stays empty until an
    authority reviewer requests a recommendation.
    """
    if file.filename and not file.filename.lower().endswith((".csv", ".txt")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please upload a .csv file.",
        )
    raw = await file.read()
    if len(raw) > MAX_CSV_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="CSV file is larger than the 5 MB limit.",
        )

    try:
        result = import_reports(db, raw)
    except CsvFormatError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    audit.record(
        db,
        user_id=current_user.user_id,
        role=current_user.role,
        action="report.csv_import",
        entity_type="report",
        entity_id=None,
        metadata={
            "filename": file.filename,
            "totalRows": result["totalRows"],
            "successfulRows": result["successfulRows"],
            "failedRows": result["failedRows"],
        },
    )
    db.commit()
    return result


# ---------------------------------------------------------------------------
# 3. Reports list & details
# ---------------------------------------------------------------------------
@router.get("/reports", response_model=Page[ReportOut])
def list_reports(
    issue_type: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    validation_status: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    priority: str | None = Query(default=None),
    source: str | None = Query(default=None),
    location: str | None = Query(default=None),
    date_from: dt.date | None = Query(default=None),
    date_to: dt.date | None = Query(default=None),
    search: str | None = Query(default=None),
    sort: str = Query(default="timestamp_desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authority),
):
    stmt = select(Report)

    if issue_type:
        stmt = stmt.where(Report.issue_type == issue_type)
    if severity:
        stmt = stmt.where(Report.severity == title_match(severity, SEVERITIES))
    if validation_status:
        stmt = stmt.where(
            Report.validation_status == title_match(validation_status, VALIDATION_STATUSES)
        )
    if status_filter:
        stmt = stmt.where(Report.status == title_match(status_filter, REPORT_STATUSES))
    if priority:
        matched = title_match(priority, PRIORITIES)
        stmt = stmt.where(
            or_(Report.final_priority == matched, Report.predicted_priority == matched)
        )
    if source:
        stmt = stmt.where(Report.source == source)
    if location:
        stmt = stmt.where(func.lower(Report.location_text).like(f"%{location.strip().lower()}%"))
    if date_from:
        stmt = stmt.where(
            Report.timestamp
            >= dt.datetime.combine(date_from, dt.time.min, tzinfo=dt.timezone.utc)
        )
    if date_to:
        stmt = stmt.where(
            Report.timestamp
            <= dt.datetime.combine(date_to, dt.time.max, tzinfo=dt.timezone.utc)
        )
    if search:
        needle = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Report.report_id).like(needle),
                func.lower(Report.location_text).like(needle),
                func.lower(Report.issue_type).like(needle),
                func.lower(Report.description).like(needle),
                func.lower(Report.user_id).like(needle),
            )
        )

    ordering = {
        "timestamp_desc": (Report.timestamp.desc(), Report.id.desc()),
        "timestamp_asc": (Report.timestamp.asc(), Report.id.asc()),
        "severity_desc": (Report.severity.desc(), Report.timestamp.desc()),
        "report_id_asc": (Report.report_id.asc(),),
    }.get(sort, (Report.timestamp.desc(), Report.id.desc()))

    total = int(db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one())
    rows = (
        db.execute(stmt.order_by(*ordering).offset((page - 1) * page_size).limit(page_size))
        .scalars()
        .all()
    )
    return {
        "items": [
            report_out(
                r,
                reporter_name=_reporter_name(db, r.user_id),
                task=_latest_task(db, r.report_id),
            )
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


@router.get("/reports/{report_id}", response_model=ReportOut)
def report_detail(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authority),
):
    report = _get_report(db, report_id)
    return report_out(
        report,
        reporter_name=_reporter_name(db, report.user_id),
        task=_latest_task(db, report.report_id),
    )


@router.get("/reports/{report_id}/audit", response_model=list[AuditEntry])
def report_audit(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authority),
):
    return audit.recent(db, limit=100, entity_id=report_id)


# ---------------------------------------------------------------------------
# 4. Manual validation
# ---------------------------------------------------------------------------
@router.post("/reports/{report_id}/validate", response_model=ReportOut)
def validate_report(
    report_id: str,
    payload: ValidationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authority),
):
    """Record the reviewer's manual validation decision."""
    report = _get_report(db, report_id)
    report.validation_status = payload.validation_status
    report.validated_by = current_user.user_id
    report.validated_at = utcnow()

    if payload.validation_status == "Valid" and report.status == "Submitted":
        report.status = "Under Review"
    elif payload.validation_status == "Invalid":
        report.status = "Under Review"
    report.updated_at = utcnow()
    db.flush()

    # A confirmed barrier takes the facility at that place off the map as
    # usable, so citizens stop being routed to something that does not work.
    blocked = None
    if payload.validation_status == "Valid":
        blocked = facility_lifecycle.mark_blocked_from_report(db, report)

    notifications.report_validated(db, report.user_id, report.report_id, payload.validation_status)
    audit.record(
        db,
        user_id=current_user.user_id,
        role=current_user.role,
        action="report.validate",
        entity_type="report",
        entity_id=report.report_id,
        metadata={
            "validation_status": payload.validation_status,
            "note": payload.note,
            "facility_blocked": blocked.facility_id if blocked else None,
        },
    )
    db.commit()
    db.refresh(report)
    return report_out(
        report,
        reporter_name=_reporter_name(db, report.user_id),
        task=_latest_task(db, report.report_id),
    )


@router.post("/reports/{report_id}/status", response_model=ReportOut)
def update_report_status(
    report_id: str,
    payload: StatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authority),
):
    report = _get_report(db, report_id)
    previous = report.status
    report.status = payload.status
    report.updated_at = utcnow()
    db.flush()
    audit.record(
        db,
        user_id=current_user.user_id,
        role=current_user.role,
        action="report.status",
        entity_type="report",
        entity_id=report.report_id,
        metadata={"from": previous, "to": payload.status},
    )
    db.commit()
    db.refresh(report)
    return report_out(
        report,
        reporter_name=_reporter_name(db, report.user_id),
        task=_latest_task(db, report.report_id),
    )


# ---------------------------------------------------------------------------
# 5. Priority recommendation + confirmation
# ---------------------------------------------------------------------------
@router.post("/reports/{report_id}/priority/predict", response_model=PriorityPrediction)
def predict_priority(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authority),
):
    """Ask the XGBoost model for a priority recommendation.

    The recommendation is stored on the report but is never treated as final -
    an authority reviewer must confirm or override it.
    """
    report = _get_report(db, report_id)
    prediction = ml_priority.predict(
        issue_type=report.issue_type,
        severity=report.severity,
        source=report.source,
        description=report.description,
        has_image=bool(report.image_object_key or report.image_url),
        timestamp=report.timestamp,
        validation_status=report.validation_status,
    )
    report.predicted_priority = prediction["priority"]
    report.prediction_confidence = prediction["confidence"]
    report.updated_at = utcnow()
    db.flush()
    audit.record(
        db,
        user_id=current_user.user_id,
        role=current_user.role,
        action="report.priority_predict",
        entity_type="report",
        entity_id=report.report_id,
        metadata={
            "predicted_priority": prediction["priority"],
            "confidence": prediction["confidence"],
            "model": prediction["model"],
        },
    )
    db.commit()
    return {
        "report_id": report.report_id,
        "predicted_priority": prediction["priority"],
        "confidence": prediction["confidence"],
        "model": prediction["model"],
        "rationale": prediction["rationale"],
        "probabilities": prediction["probabilities"],
    }


@router.post("/reports/{report_id}/priority/confirm", response_model=ReportOut)
def confirm_priority(
    report_id: str,
    payload: PriorityConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authority),
):
    """Human confirmation (or override) of the recommended priority."""
    report = _get_report(db, report_id)
    report.final_priority = payload.final_priority
    report.priority_confirmed_by = current_user.user_id
    report.priority_confirmed_at = utcnow()
    report.updated_at = utcnow()
    db.flush()
    audit.record(
        db,
        user_id=current_user.user_id,
        role=current_user.role,
        action="report.priority_confirm",
        entity_type="report",
        entity_id=report.report_id,
        metadata={
            "final_priority": payload.final_priority,
            "predicted_priority": report.predicted_priority,
            "overridden": report.predicted_priority != payload.final_priority,
        },
    )
    db.commit()
    db.refresh(report)
    return report_out(
        report,
        reporter_name=_reporter_name(db, report.user_id),
        task=_latest_task(db, report.report_id),
    )


# ---------------------------------------------------------------------------
# 6. Maintenance assignment and resolution verification
# ---------------------------------------------------------------------------
@router.post(
    "/reports/{report_id}/assign", response_model=TaskOut, status_code=status.HTTP_201_CREATED
)
def assign_maintenance(
    report_id: str,
    payload: AssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authority),
):
    """Create a maintenance task for a validated report."""
    report = _get_report(db, report_id)
    if report.validation_status == "Invalid":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An invalid report cannot be assigned for maintenance.",
        )

    open_task = db.execute(
        select(MaintenanceTask).where(
            MaintenanceTask.report_id == report_id,
            MaintenanceTask.status.in_(("Assigned", "In Progress", "Completed")),
        )
    ).scalar_one_or_none()
    if open_task is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Report {report_id} already has an open task ({open_task.task_id}).",
        )

    assignee = None
    if payload.assigned_to:
        assignee = db.execute(
            select(User).where(
                User.user_id == payload.assigned_to, User.role == "MAINTENANCE"
            )
        ).scalar_one_or_none()
        if assignee is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The selected assignee is not a maintenance account.",
            )

    now = utcnow()
    task = MaintenanceTask(
        task_id=new_task_id(db),
        report_id=report.report_id,
        assigned_team=payload.assigned_team.strip(),
        assigned_to=assignee.user_id if assignee else None,
        assigned_by=current_user.user_id,
        assigned_at=now,
        status="Assigned",
        maintenance_notes=payload.note,
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    report.status = "Assigned"
    report.updated_at = now
    db.flush()

    notifications.report_assigned(db, report.user_id, report.report_id, task.assigned_team)
    if assignee is not None:
        notifications.task_assigned(db, assignee.user_id, report.report_id, task.task_id)
    else:
        for member in (
            db.execute(
                select(User).where(
                    User.role == "MAINTENANCE", User.team == payload.assigned_team.strip()
                )
            )
            .scalars()
            .all()
        ):
            notifications.task_assigned(db, member.user_id, report.report_id, task.task_id)

    audit.record(
        db,
        user_id=current_user.user_id,
        role=current_user.role,
        action="task.assign",
        entity_type="task",
        entity_id=task.task_id,
        metadata={"report_id": report.report_id, "team": task.assigned_team},
    )
    db.commit()
    db.refresh(task)
    return task_out(task, report)


@router.get("/tasks", response_model=Page[TaskOut])
def list_tasks(
    status_filter: str | None = Query(default=None, alias="status"),
    team: str | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authority),
):
    stmt = select(MaintenanceTask)
    if status_filter:
        stmt = stmt.where(MaintenanceTask.status == title_match(status_filter, TASK_STATUSES))
    if team:
        stmt = stmt.where(MaintenanceTask.assigned_team == team)
    if search:
        needle = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(MaintenanceTask.task_id).like(needle),
                func.lower(MaintenanceTask.report_id).like(needle),
                func.lower(MaintenanceTask.assigned_team).like(needle),
            )
        )

    total = int(db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one())
    rows = (
        db.execute(
            stmt.order_by(MaintenanceTask.assigned_at.desc(), MaintenanceTask.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    items = []
    for task in rows:
        report = db.execute(
            select(Report).where(Report.report_id == task.report_id)
        ).scalar_one_or_none()
        items.append(task_out(task, report))
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


@router.post("/tasks/{task_id}/verify", response_model=TaskOut)
def verify_resolution(
    task_id: str,
    payload: VerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authority),
):
    """Approve a completed repair, or send it back for rework."""
    task = db.execute(
        select(MaintenanceTask).where(MaintenanceTask.task_id == task_id)
    ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    if task.status != "Completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only tasks marked Completed by the maintenance team can be verified.",
        )

    report = db.execute(
        select(Report).where(Report.report_id == task.report_id)
    ).scalar_one_or_none()
    now = utcnow()

    facility = None
    facility_created = False
    if payload.approved:
        task.status = "Verified"
        task.verified_by = current_user.user_id
        task.verified_at = now
        task.verification_notes = payload.notes
        if report is not None:
            report.status = "Resolved"
            report.updated_at = now
            # The barrier is gone, so this place becomes a verified accessible
            # facility: green on the citizen map instead of a red issue.
            facility, facility_created = facility_lifecycle.promote_report_to_facility(
                db, report, verified_by=current_user.user_id
            )
            notifications.report_resolved(db, report.user_id, report.report_id)
        if task.assigned_to:
            notifications.task_verified(db, task.assigned_to, task.report_id, task.task_id)
    else:
        task.status = "In Progress"
        task.completed_at = None
        task.verification_notes = payload.notes
        if report is not None:
            report.status = "In Progress"
            report.updated_at = now
        if task.assigned_to:
            notifications.task_rejected(
                db, task.assigned_to, task.report_id, task.task_id, payload.notes
            )

    task.updated_at = now
    db.flush()
    audit.record(
        db,
        user_id=current_user.user_id,
        role=current_user.role,
        action="task.verify" if payload.approved else "task.reject",
        entity_type="task",
        entity_id=task.task_id,
        metadata={
            "report_id": task.report_id,
            "notes": payload.notes,
            "facility_id": facility.facility_id if facility else None,
            "facility_created": facility_created,
        },
    )
    db.commit()
    db.refresh(task)
    return task_out(task, report)


@router.get("/teams", response_model=dict)
def teams(db: Session = Depends(get_db), current_user: User = Depends(require_authority)):
    """Teams and maintenance accounts available for assignment."""
    members = (
        db.execute(select(User).where(User.role == "MAINTENANCE", User.is_active.is_(True)))
        .scalars()
        .all()
    )
    known = {m.team for m in members if m.team}
    return {
        "teams": sorted(known | set(MAINTENANCE_TEAMS)),
        "members": [
            {"user_id": m.user_id, "name": m.name, "team": m.team} for m in members
        ],
    }


@router.get("/audit", response_model=list[AuditEntry])
def audit_trail(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authority),
):
    return audit.recent(db, limit=limit)


@router.delete("/reports/{report_id}", response_model=Message)
def delete_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authority),
):
    """Remove a report that was imported in error."""
    report = _get_report(db, report_id)
    if _latest_task(db, report_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Reports with maintenance history cannot be deleted.",
        )
    db.delete(report)
    audit.record(
        db,
        user_id=current_user.user_id,
        role=current_user.role,
        action="report.delete",
        entity_type="report",
        entity_id=report_id,
    )
    db.commit()
    return {"detail": f"Report {report_id} deleted."}
