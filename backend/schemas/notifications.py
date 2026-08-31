"""Notification schemas."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

from backend.schemas.common import ORMModel


class NotificationOut(ORMModel):
    id: int
    notification_id: str
    user_id: str
    report_id: str | None = None
    title: str | None = None
    message: str
    type: str
    is_read: bool
    created_at: dt.datetime


class NotificationCount(BaseModel):
    total: int
    unread: int
