"""User notification inbox."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from backend.core.deps import get_current_user
from backend.db.session import get_db
from backend.models.entities import Notification, User
from backend.schemas.common import Message, Page
from backend.schemas.notifications import NotificationCount, NotificationOut
from backend.services.serializers import notification_out

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=Page[NotificationOut])
def list_notifications(
    unread_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Notification).where(Notification.user_id == current_user.user_id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))

    total = int(db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one())
    rows = (
        db.execute(
            stmt.order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return {
        "items": [notification_out(n) for n in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


@router.get("/count", response_model=NotificationCount)
def counts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    total = int(
        db.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == current_user.user_id)
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
    return {"total": total, "unread": unread}


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notification = db.execute(
        select(Notification).where(
            Notification.notification_id == notification_id,
            Notification.user_id == current_user.user_id,
        )
    ).scalar_one_or_none()
    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found."
        )
    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification_out(notification)


@router.post("/read-all", response_model=Message)
def mark_all_read(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    result = db.execute(
        update(Notification)
        .where(
            Notification.user_id == current_user.user_id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True)
    )
    db.commit()
    return {"detail": f"{result.rowcount or 0} notification(s) marked as read."}
