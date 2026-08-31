"""ORM models for the RouteSathi MVP.

Geographic columns
------------------
``latitude`` / ``longitude`` are the authoritative values written by the
application.  On PostgreSQL a real ``GEOGRAPHY(Point, 4326)`` column named
``location_point`` is added by :mod:`backend.db.init_db` and kept in sync by a
trigger, which is what the PostGIS radius queries use.  The ORM therefore
declares ``location_point`` as a deferred, read-only text column so the same
models work on both PostgreSQL and the SQLite development fallback.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="USER", index=True)
    # Free-text label shown in the authority/maintenance portals
    organisation: Mapped[str | None] = mapped_column(String(160), nullable=True)
    team: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    reports: Mapped[list["Report"]] = relationship(
        back_populates="reporter",
        primaryjoin="User.user_id == foreign(Report.user_id)",
        viewonly=True,
    )


class AccessibilityFacility(Base, TimestampMixin):
    __tablename__ = "accessibility_facilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    facility_id: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    location_point: Mapped[str | None] = mapped_column(
        Text, nullable=True, deferred=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="Available", index=True
    )
    source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_updated: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_facilities_lat_lng", "latitude", "longitude"),
    )


class Report(Base, TimestampMixin):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    issue_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    location_text: Mapped[str | None] = mapped_column(String(300), nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    location_point: Mapped[str | None] = mapped_column(Text, nullable=True, deferred=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    image_object_key: Mapped[str | None] = mapped_column(String(400), nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    timestamp: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    validation_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="Needs Review", index=True
    )
    validated_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    validated_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    predicted_priority: Mapped[str | None] = mapped_column(String(16), nullable=True)
    prediction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_priority: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    priority_confirmed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    priority_confirmed_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="Submitted", index=True
    )
    source: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)

    reporter: Mapped["User | None"] = relationship(
        back_populates="reports",
        primaryjoin="foreign(Report.user_id) == User.user_id",
        viewonly=True,
    )
    tasks: Mapped[list["MaintenanceTask"]] = relationship(
        back_populates="report",
        primaryjoin="Report.report_id == foreign(MaintenanceTask.report_id)",
        viewonly=True,
        order_by="MaintenanceTask.id.desc()",
    )

    __table_args__ = (
        Index("ix_reports_lat_lng", "latitude", "longitude"),
        Index("ix_reports_status_severity", "status", "severity"),
    )


class MaintenanceTask(Base, TimestampMixin):
    __tablename__ = "maintenance_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    report_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    assigned_team: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    assigned_to: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    assigned_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assigned_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="Assigned", index=True
    )
    maintenance_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_image_object_key: Mapped[str | None] = mapped_column(String(400), nullable=True)
    resolution_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verified_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verified_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verification_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    report: Mapped["Report | None"] = relationship(
        back_populates="tasks",
        primaryjoin="foreign(MaintenanceTask.report_id) == Report.report_id",
        viewonly=True,
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    notification_id: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    report_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(48), nullable=False, default="system")
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(48), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    timestamp: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    # Stored as a JSON string so the column behaves identically on
    # PostgreSQL and the SQLite development fallback.
    audit_metadata: Mapped[str | None] = mapped_column("metadata", Text, nullable=True)


class StoredFile(Base):
    """Development fallback for object storage.

    Used only when Amazon S3 credentials are not configured; see
    ``backend/services/storage.py``.  Production deployments keep every binary
    in S3 and store just the object key on the report row.
    """

    __tablename__ = "stored_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_key: Mapped[str] = mapped_column(String(400), unique=True, index=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    data_base64: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (UniqueConstraint("object_key", name="uq_stored_files_object_key"),)
