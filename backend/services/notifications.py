"""In-app notification fan-out."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.models.entities import Notification
from backend.utils.datetimes import utcnow
from backend.utils.ids import new_notification_id


def push(
    db: Session,
    *,
    user_id: str,
    message: str,
    type: str = "system",
    title: str | None = None,
    report_id: str | None = None,
) -> Notification:
    """Create a notification for a single user.  Caller owns the transaction."""
    notification = Notification(
        notification_id=new_notification_id(db),
        user_id=user_id,
        report_id=report_id,
        title=title,
        message=message,
        type=type,
        is_read=False,
        created_at=utcnow(),
    )
    db.add(notification)
    db.flush()
    return notification


def unread_count(db: Session, user_id: str) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        ).scalar_one()
    )


# --- canned messages -------------------------------------------------------
def report_submitted(db: Session, user_id: str, report_id: str, issue_type: str) -> None:
    push(
        db,
        user_id=user_id,
        report_id=report_id,
        type="report_submitted",
        title="Report submitted",
        message=(
            f"Your report {report_id} about \"{issue_type}\" has been submitted "
            "and is waiting for review."
        ),
    )


def report_validated(db: Session, user_id: str, report_id: str, validation_status: str) -> None:
    wording = {
        "Valid": "has been verified by the authority",
        "Invalid": "was reviewed and marked invalid",
        "Needs Review": "has been sent back for further review",
    }.get(validation_status, "has been reviewed")
    push(
        db,
        user_id=user_id,
        report_id=report_id,
        type="report_validated",
        title=f"Report {validation_status.lower()}",
        message=f"Your report {report_id} {wording}.",
    )


def report_assigned(db: Session, user_id: str, report_id: str, team: str) -> None:
    push(
        db,
        user_id=user_id,
        report_id=report_id,
        type="report_assigned",
        title="Maintenance assigned",
        message=f"Report {report_id} has been assigned to {team} for repair.",
    )


def report_in_progress(db: Session, user_id: str, report_id: str) -> None:
    push(
        db,
        user_id=user_id,
        report_id=report_id,
        type="report_in_progress",
        title="Work started",
        message=f"A maintenance team has started work on report {report_id}.",
    )


def report_resolved(db: Session, user_id: str, report_id: str) -> None:
    push(
        db,
        user_id=user_id,
        report_id=report_id,
        type="report_resolved",
        title="Issue resolved",
        message=(
            f"Report {report_id} has been resolved and verified. "
            "Thank you for making the city more accessible."
        ),
    )


def task_assigned(db: Session, user_id: str, report_id: str, task_id: str) -> None:
    push(
        db,
        user_id=user_id,
        report_id=report_id,
        type="task_assigned",
        title="New task assigned",
        message=f"Task {task_id} for report {report_id} has been assigned to you.",
    )


def task_verified(db: Session, user_id: str, report_id: str, task_id: str) -> None:
    push(
        db,
        user_id=user_id,
        report_id=report_id,
        type="task_verified",
        title="Resolution verified",
        message=f"Your completion of task {task_id} was verified by the authority.",
    )


def task_rejected(db: Session, user_id: str, report_id: str, task_id: str, reason: str | None) -> None:
    tail = f" Reason: {reason}" if reason else ""
    push(
        db,
        user_id=user_id,
        report_id=report_id,
        type="task_rejected",
        title="Resolution sent back",
        message=f"Task {task_id} was sent back for rework.{tail}",
    )
