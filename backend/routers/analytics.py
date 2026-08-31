"""Analytics for the authority Map & Analytics page."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.deps import require_authority
from backend.db.session import get_db
from backend.models.entities import MaintenanceTask, Report, User
from backend.schemas.analytics import AnalyticsResponse
from backend.schemas.reports import ReportMapPin
from backend.utils.datetimes import ensure_utc, utcnow

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _group(db: Session, column, where=None) -> list[dict]:
    stmt = select(column, func.count()).group_by(column).order_by(func.count().desc())
    if where is not None:
        stmt = stmt.where(where)
    return [
        {"key": key or "Unspecified", "count": int(count)}
        for key, count in db.execute(stmt).all()
    ]


@router.get("", response_model=AnalyticsResponse)
def analytics(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authority),
):
    """Aggregate breakdowns and a submitted/resolved trend line."""
    since = utcnow() - dt.timedelta(days=days)

    total = int(db.execute(select(func.count()).select_from(Report)).scalar_one())

    # Trend: bucket by calendar day in Python so the query stays portable
    # across PostgreSQL and the SQLite development fallback.
    buckets: dict[str, dict[str, int]] = {}
    for offset in range(days - 1, -1, -1):
        day = (utcnow() - dt.timedelta(days=offset)).date().isoformat()
        buckets[day] = {"submitted": 0, "resolved": 0}

    recent = (
        db.execute(select(Report).where(Report.timestamp >= since)).scalars().all()
    )
    for report in recent:
        key = ensure_utc(report.timestamp).date().isoformat()
        if key in buckets:
            buckets[key]["submitted"] += 1

    verified_tasks = (
        db.execute(
            select(MaintenanceTask).where(
                MaintenanceTask.verified_at.is_not(None),
                MaintenanceTask.verified_at >= since,
            )
        )
        .scalars()
        .all()
    )
    durations: list[float] = []
    for task in verified_tasks:
        key = ensure_utc(task.verified_at).date().isoformat()
        if key in buckets:
            buckets[key]["resolved"] += 1
        report = db.execute(
            select(Report).where(Report.report_id == task.report_id)
        ).scalar_one_or_none()
        if report is not None:
            delta = ensure_utc(task.verified_at) - ensure_utc(report.timestamp)
            hours = delta.total_seconds() / 3600.0
            if hours >= 0:
                durations.append(hours)

    return {
        "by_issue_type": _group(db, Report.issue_type),
        "by_severity": _group(db, Report.severity),
        "by_status": _group(db, Report.status),
        "by_validation": _group(db, Report.validation_status),
        "by_priority": _group(db, Report.final_priority),
        "by_source": _group(db, Report.source),
        "by_location": _group(db, Report.location_text)[:10],
        "trend": [{"date": day, **counts} for day, counts in buckets.items()],
        "average_resolution_hours": (
            round(sum(durations) / len(durations), 1) if durations else None
        ),
        "total_reports": total,
    }


@router.get("/map", response_model=list[ReportMapPin])
def analytics_map(
    only_open: bool = Query(default=False),
    limit: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authority),
):
    """Every report as a map marker for the authority map view."""
    stmt = select(Report)
    if only_open:
        stmt = stmt.where(
            Report.status.in_(("Submitted", "Under Review", "Assigned", "In Progress"))
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
