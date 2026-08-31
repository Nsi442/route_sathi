"""Human-readable, collision-resistant identifier generation."""

from __future__ import annotations

import random
import string

from sqlalchemy import func, select
from sqlalchemy.orm import Session

_ALPHABET = string.ascii_uppercase + string.digits


def _random_suffix(length: int = 4) -> str:
    return "".join(random.choices(_ALPHABET, k=length))


def next_sequential_id(db: Session, model, column, prefix: str, start: int) -> str:
    """Return the next ``PREFIX-N`` identifier for ``model``.

    Falls back to a random suffix if a race produced a collision, so the caller
    never has to retry.
    """
    highest = start - 1
    rows = db.execute(select(column).where(column.like(f"{prefix}-%"))).scalars().all()
    for value in rows:
        tail = value.rsplit("-", 1)[-1]
        if tail.isdigit():
            highest = max(highest, int(tail))
    candidate = f"{prefix}-{highest + 1}"
    exists = db.execute(
        select(func.count()).select_from(model).where(column == candidate)
    ).scalar_one()
    if exists:
        return f"{prefix}-{highest + 1}{_random_suffix(3)}"
    return candidate


def new_report_id(db: Session) -> str:
    from backend.models.entities import Report

    return next_sequential_id(db, Report, Report.report_id, "RS", 1001)


def new_task_id(db: Session) -> str:
    from backend.models.entities import MaintenanceTask

    return next_sequential_id(db, MaintenanceTask, MaintenanceTask.task_id, "MT", 5001)


def new_user_id(db: Session, role: str) -> str:
    from backend.models.entities import User

    prefix = {"USER": "U", "AUTHORITY": "AU", "MAINTENANCE": "MN"}.get(role.upper(), "U")
    start = {"U": 1001, "AU": 101, "MN": 201}[prefix]
    return next_sequential_id(db, User, User.user_id, prefix, start)


def new_facility_id(db: Session) -> str:
    from backend.models.entities import AccessibilityFacility

    return next_sequential_id(
        db, AccessibilityFacility, AccessibilityFacility.facility_id, "FAC", 1
    )


def new_notification_id(db: Session) -> str:
    from backend.models.entities import Notification

    return next_sequential_id(db, Notification, Notification.notification_id, "NT", 1)
