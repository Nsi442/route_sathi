"""Citizen-facing profile and home-screen endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.deps import get_current_user, require_user
from backend.core.security import hash_password, verify_password
from backend.db.geo import nearby
from backend.db.session import get_db
from backend.models.entities import Notification, Report, User
from backend.schemas.analytics import UserHomeSummary
from backend.schemas.auth import PasswordChange, ProfileUpdate, UserPublic
from backend.schemas.common import Message
from backend.utils.datetimes import iso

router = APIRouter(prefix="/user", tags=["user"])

# Issue statuses that still represent an unresolved accessibility problem.
OPEN_STATUSES = ("Submitted", "Under Review", "Assigned", "In Progress")


@router.get("/profile", response_model=UserPublic)
def get_profile(current_user: User = Depends(get_current_user)):
    return UserPublic.model_validate(current_user)


@router.patch("/profile", response_model=UserPublic)
def update_profile(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.name is not None:
        current_user.name = payload.name.strip()
    if payload.phone is not None:
        current_user.phone = payload.phone.strip() or None
    db.commit()
    db.refresh(current_user)
    return UserPublic.model_validate(current_user)


@router.post("/password", response_model=Message)
def change_password(
    payload: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your current password is incorrect.",
        )
    current_user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"detail": "Password updated."}


@router.get("/home", response_model=UserHomeSummary)
def home_summary(
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    radius: int = Query(default=1000, ge=50, le=20000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    """Counts and latest updates for the 'Accessibility Around You' home card.

    When coordinates are supplied the counts are restricted to the radius;
    otherwise they are city-wide so the screen is still useful before the
    browser grants geolocation permission.
    """
    counts = {"ramps": 0, "entrances": 0, "toilets": 0, "parking": 0, "issues": 0}

    if latitude is not None and longitude is not None:
        facility_rows = nearby(
            db,
            table="accessibility_facilities",
            columns=["type", "status"],
            latitude=latitude,
            longitude=longitude,
            radius_m=radius,
            limit=1000,
            extra_sql="status <> 'Inactive'",
        )
        for row in facility_rows:
            key = {
                "Ramp": "ramps",
                "Entrance": "entrances",
                "Toilet": "toilets",
                "Parking": "parking",
            }.get(row["type"])
            if key:
                counts[key] += 1

        issue_rows = nearby(
            db,
            table="reports",
            columns=["report_id"],
            latitude=latitude,
            longitude=longitude,
            radius_m=radius,
            limit=1000,
            extra_sql=(
                "status IN ('Submitted', 'Under Review', 'Assigned', 'In Progress') "
                "AND validation_status <> 'Invalid'"
            ),
        )
        counts["issues"] = len(issue_rows)
    else:
        from backend.models.entities import AccessibilityFacility

        for facility_type, key in (
            ("Ramp", "ramps"),
            ("Entrance", "entrances"),
            ("Toilet", "toilets"),
            ("Parking", "parking"),
        ):
            counts[key] = int(
                db.execute(
                    select(func.count())
                    .select_from(AccessibilityFacility)
                    .where(
                        AccessibilityFacility.type == facility_type,
                        AccessibilityFacility.status != "Inactive",
                    )
                ).scalar_one()
            )
        counts["issues"] = int(
            db.execute(
                select(func.count())
                .select_from(Report)
                .where(
                    Report.status.in_(OPEN_STATUSES),
                    Report.validation_status != "Invalid",
                )
            ).scalar_one()
        )

    my_reports = int(
        db.execute(
            select(func.count()).select_from(Report).where(Report.user_id == current_user.user_id)
        ).scalar_one()
    )
    unread = int(
        db.execute(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.user_id == current_user.user_id,
                Notification.is_read.is_(False),
            )
        ).scalar_one()
    )

    latest = (
        db.execute(
            select(Report)
            .order_by(Report.updated_at.desc(), Report.id.desc())
            .limit(5)
        )
        .scalars()
        .all()
    )

    return {
        "name": current_user.name,
        **counts,
        "my_reports": my_reports,
        "unread_notifications": unread,
        "radius": radius,
        "latest_updates": [
            {
                "report_id": r.report_id,
                "issue_type": r.issue_type,
                "location_text": r.location_text,
                "status": r.status,
                "severity": r.severity,
                "timestamp": iso(r.timestamp) or "",
            }
            for r in latest
        ],
    }
